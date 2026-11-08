"""Hold real UI requests across Cancel: late starts must not resurrect a job."""
import json,os,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
import pytest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def site(tmp_path_factory):
    import socket
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    folder=tmp_path_factory.mktemp('cancel-browser')
    with (folder/'server.log').open('w') as log:
        process=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port',str(port),'--data',str(folder/'data')],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUNBUFFERED':'1'})
        try:
            url=f'http://127.0.0.1:{port}'
            for _ in range(120):
                try:urlopen(url+'/montara/version',timeout=1).close();break
                except OSError:time.sleep(.25)
            else:raise AssertionError((folder/'server.log').read_text()[-3000:])
            yield url
        finally:process.terminate();process.wait(timeout=30)


@pytest.mark.parametrize('operation,path',[
    ('make','/api/v1/wizard/prepare'),
    ('render','/api/v1/wizard/review/render'),
    ('captions','/api/v1/wizard/compose'),
])
@pytest.mark.parametrize('late_status',[200,500])
def test_cancel_fences_late_start_responses(site,operation,path,late_status):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.goto(site);page.locator('#mode').wait_for(state='visible')
        held=[];starts=[];cancel=[]
        page.route('**/api/v1/settings/fillers',lambda route:route.fulfill(json={'fillers':[]}))
        page.route('**/api/v1/wizard/status*',lambda route:route.fulfill(json={'status':'cancelled'}))
        page.route('**/api/v1/wizard/start',lambda route:(starts.append(route.request.post_data),route.fulfill(json={})))
        page.route('**/api/v1/wizard/cancel',lambda route:(cancel.append(json.loads(route.request.post_data)),route.fulfill(json={})))
        page.route('**'+path,lambda route:held.append(route))
        page.evaluate("state.files=[];state.projectId=null;state.platform='youtube'")
        if operation=='make':page.evaluate('void make().catch(fail)')
        elif operation=='render':page.evaluate("show('frames');document.querySelector('#renderFrames').click()")
        else:page.evaluate("show('captions');cap.list=[{text:'hello',start:0,end:1}];document.querySelector('#capApply').click()")
        page.locator('#making').wait_for(state='visible')
        page.wait_for_timeout(150);assert len(held)==1
        page.locator('#cancel').click();page.wait_for_timeout(100)
        assert not cancel  # cancel waits for the in-flight start to register
        held[0].fulfill(status=late_status,json={'error':{'message':'late error'}} if late_status==500 else {})
        page.locator('#footage').wait_for(state='visible')
        page.wait_for_timeout(600)
        assert len(cancel)==1 and cancel[0]['if_idle'] is True
        assert starts==[] and page.evaluate('state.polling===null')
        assert page.locator('#failed').is_hidden()
        browser.close()


def test_result_download_uses_project_not_internal_filename(site):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.goto(site);page.locator('#mode').wait_for(state='visible')
        page.evaluate("state.files=[];state.localProject=null;state.platform='show';document.querySelector('#videoName').value='Montara.Notetaker';showResult({result:{url:'/missing.mp4',filename:'job-a849ce59-0001.mp4'}})")
        assert page.locator('#download').get_attribute('download')=='Montara.Notetaker.mp4'
        assert 'download_name=Montara.Notetaker.mp4' in page.locator('#download').get_attribute('href')
        browser.close()


@pytest.mark.parametrize('rejected',[False,True])
def test_native_cancel_waits_for_late_job_id_and_keeps_shot_bars(site,rejected):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.route('http://127.0.0.1:47820/health',lambda route:route.fulfill(headers={'Access-Control-Allow-Origin':'*'},json={'app':'montara-companion','ffmpeg':True,'local_video':{'engine':'a'*40}}))
        page.goto(site);page.locator('#mode').wait_for(state='visible')
        page.route('**/api/v1/edit/native-recipe*',lambda route:route.fulfill(json={'engine':'a'*40,'revision':'test','sources':[{'key':0,'path':'camera.mp4'}],'segments':[{'source':0}, {'source':0}, {'source':0}]}))
        page.route('**/api/v1/edit/native-master*',lambda route:route.fulfill(body=b'audio'))
        page.evaluate("""() => {
          state.platform='youtube';state.projectId='test';state.localProject={id:'test'};
          state.files=[{kind:'video',path:'camera.mp4',small:true,original:{name:'camera.mp4'}}];
          window.cancelledJobs=[];
          montaraCompanion.locateOriginal=async()=>true;
          montaraCompanion.saveInProject=async()=>{};
          montaraCompanion.startVideo=()=>new Promise((resolve,reject)=>window.releaseNative=bad=>{
            if(bad){const error=new Error('invalid job');error.status=400;reject(error);}else resolve('test-job');
          });
          montaraCompanion.cancelVideo=async id=>cancelledJobs.push(id);
          void finishOriginalVideo({result:{}});
        }""")
        page.wait_for_function('!!window.releaseNative')
        assert page.locator('#renderBars i').count()==3
        assert page.locator('#renderBars').is_visible()
        page.locator('#cancel').click();page.wait_for_timeout(100)
        assert page.evaluate('cancelledJobs.length')==0
        page.evaluate('bad=>releaseNative(bad)',rejected)
        page.locator('#frames').wait_for(state='visible')
        assert page.evaluate("cancelledJobs.includes('test-job')") is not rejected
        assert page.locator('#result').is_hidden()
        browser.close()


def test_session_cancel_aborts_local_mix_without_server_fallback(site):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.goto(site);page.locator('#mode').wait_for(state='visible')
        songs=[{'id':1,'name':'Song','start':0,'end':10,'selected':True}];unexpected=[]
        page.route('**/montara/session/test/songs',lambda route:route.fulfill(json={'songs':songs}))
        page.route('**/montara/session/test/local-plan*',lambda route:route.fulfill(json={'mixer':'a'*40,'tracks':[],'window':[0,10]}))
        page.route('**/montara/session/test/cancel',lambda route:route.fulfill(json={}))
        page.route('**/montara/session/test',lambda route:route.fulfill(json={'status':'review','songs':songs,'results':[]}))
        for path in ('render','local-result'):
            page.route('**/montara/session/test/'+path,lambda route:(unexpected.append(route.request.url),route.fulfill(json={})))
        page.evaluate('''songs=>{
          show('sessionReview');fullSession.id='test';fullSession.mixes={};
          fullSession.data={status:'review',uses_previews:true,songs,results:[],track_files:[]};
          montaraCompanion.detect=async()=>{};montaraCompanion.localMixer=()=> 'a'.repeat(40);
          montaraCompanion.mixSong=(plan,mix,progress,signal)=>new Promise((resolve,reject)=>{
            window.localMixStarted=true;signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')));
          });
          void renderFullSession();
        }''',songs)
        page.wait_for_function('window.localMixStarted===true')
        page.locator('#sessionCancel').click()
        page.wait_for_function('fullSession.cancelling===false && fullSession.busy===false')
        page.wait_for_timeout(500)
        assert unexpected==[]
        assert page.locator('#sessionBack').is_enabled()
        browser.close()


@pytest.mark.parametrize('usage',['asset','camera'])
def test_unused_small_assets_do_not_require_companion(site,usage):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.route('**/api/v1/edit/native-recipe*',lambda route:route.fulfill(json={'engine':'a'*40,'revision':'test','sources':[{'key':1,'path':'full-camera.mp4'}],'segments':[{'source':1}]}))
        page.goto(site);page.locator('#mode').wait_for(state='visible')
        page.evaluate("""usage=>{
          state.platform='youtube';state.projectId='test';state.localProject=null;
          state.files=[{kind:'video',path:'unused.small.mp4',small:true,usage}];
          montaraCompanion.detect=async()=>{throw new Error('Unused asset must not require Companion');};
          showResult({result:{url:'/test-output.mp4'}});
        }""",usage)
        page.locator('#result').wait_for(state='visible')
        assert page.locator('#failed').is_hidden()
        browser.close()
