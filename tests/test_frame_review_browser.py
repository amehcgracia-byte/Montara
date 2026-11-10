"""Slow review responses cannot overlap; ready cards arrive without replacing edits."""
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

WEB=Path(__file__).resolve().parents[1]/'web'


def test_stage_ready_cards_single_request_and_placeholders_without_rebinding():
    entered,release=threading.Event(),threading.Event()
    status={'ready':0,'active':0,'max_active':0,'calls':0,'swaps':0}
    lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def reply(self,data,code=200):
            raw=json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
        def do_POST(self):
            if self.path=='/api/v1/wizard/review/replace':
                status['swaps']+=1;self.reply({'replaced':[]})
            else:self.reply({})
        def do_GET(self):
            if self.path.startswith('/api/v1/wizard/review?'):
                with lock:
                    status['calls']+=1;status['active']+=1;status['max_active']=max(status['max_active'],status['active']);first=status['calls']==1
                if first:entered.set();release.wait(10)
                try:self.reply({'items':[{'index':i,'thumbnail':'/mark.svg' if i<status['ready'] else None,'preview_ready':i<status['ready'],'duration_sec':2,'camera_type':'fixed','candidate_count':2} for i in range(6)]})
                finally:
                    with lock:status['active']-=1
                return
            path=WEB/urlsplit(self.path).path.lstrip('/')
            if path.is_file() and path.resolve().is_relative_to(WEB):
                raw=path.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream');self.end_headers();self.wfile.write(raw)
            elif self.path=='/':
                raw=(WEB/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(raw)
            elif self.path.startswith('/api/v1/edit/timeline'):self.reply({'shots':[],'boundaries':[]})
            elif self.path=='/montara/session/latest':self.reply({},404)
            else:self.reply({})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page()
            page.route('http://127.0.0.1:47820/**',lambda route:route.abort())
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/');page.locator('#mode').wait_for(state='visible')
            page.evaluate("()=>{state.platform='youtube';state.projectId='test';openFrames().catch(fail);}")
            assert entered.wait(3)
            page.evaluate('()=>{for(let i=0;i<4;i++)refreshFrames(false).catch(fail);}')
            page.wait_for_timeout(100)
            assert status['active']==1 and status['calls']==1
            assert page.locator('#making').is_visible() and page.locator('#frameGrid .frame').count()==0
            release.set();page.wait_for_function('framesRequest===null')
            status['ready']=3;page.evaluate('refreshFrames(false)')
            assert page.locator('#frames').is_visible() and page.locator('#frameGrid .frame').count()==6
            assert page.locator('#frameGrid .frame:not(.busy)').count()==3
            page.evaluate('window.firstReadyCard=document.querySelector("#frameGrid .frame")')
            status['ready']=6;page.evaluate('refreshFrames(false)')
            assert page.locator('#frameGrid .frame').count()==6
            assert page.evaluate('firstReadyCard===document.querySelector("#frameGrid .frame")')
            page.locator('.frame .swap').first.click();page.wait_for_function('swapping.size===0')
            assert status['swaps']==1 and status['max_active']==1
            assert not errors,errors
            browser.close()
    finally:
        release.set();server.shutdown();server.server_close()


def test_extra_360_viewpoint_has_its_own_tile_name_and_pose():
    """New viewpoints are actual editable cards, not copies of built-in slots."""
    class StaticHandler(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_GET(self):
            name=urlsplit(self.path).path.lstrip('/') or 'index.html'
            path=WEB/name
            if path.is_file() and path.resolve().is_relative_to(WEB):
                raw=path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
                self.end_headers();self.wfile.write(raw)
            else:
                self.send_response(404);self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),StaticHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch()
            page=browser.new_page()
            page.route('http://127.0.0.1:47820/**',lambda route:route.abort())
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.evaluate("""() => {
              state.platform='youtube';
              state.files=[{kind:'video',name:'camera.small.mp4',path:'/test/camera.small.mp4',cameraType:'360'}];
              show('cameras');renderCameras();
            }""")
            assert page.locator('.sphere .slot').count()==7
            page.locator('.add-point-of-view').click()
            custom=page.locator('.slot[data-slot="custom_1"]')
            assert custom.count()==1
            custom.locator('input[type=text]').fill('Trumpet')
            page.locator('.pano').click(position={'x':50,'y':50})
            assert page.evaluate("state.viewpoints['/test/camera.small.mp4'].custom_1.subject")=='Trumpet'
            assert page.evaluate("state.viewpoints['/test/camera.small.mp4'].custom_1.enabled") is True
            assert page.locator('.sphere .slot').count()==8
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
