// All edit modes use the same boundary control. Save once, on release; never render on drag.
let cutLoadToken=0,cutBusy=false,musicTimeline=null,selectedShowCut=null;
function selectShowCut(doc,shot,host){
  selectedShowCut={project:doc.project_id,revision:doc.revision,index:shot.index};
  host.closest('#showEditorTimeline').querySelectorAll('.cut-shot').forEach(button=>{const on=button.dataset.shotIndex===String(shot.index)&&button.dataset.cutKind==='show';button.classList.toggle('selected',on);button.setAttribute('aria-pressed',String(on));});
  const remove=document.querySelector('#showCutToolsHost [data-cut-delete]');if(remove)remove.disabled=false;
  const label=document.querySelector('#showCutToolsHost [data-cut-selection]');if(label)label.textContent=`Shot ${shot.index+1} selected`;
}
function optimisticCutDocument(doc,change){
  const next=structuredClone(doc);let shots=next.shots;
  if(change.op==='split'){
    const at=Math.round(change.at*doc.fps)/doc.fps,index=shots.findIndex(s=>s.start<at&&s.end>at);if(index<0)return doc;
    const old=shots[index];shots.splice(index,1,{...old,end:at},{...old,start:at});
  }else if(change.op==='delete'){
    const removed=shots[change.index];if(!removed||shots.length===1)return doc;const duration=removed.end-removed.start;shots.splice(change.index,1);shots.slice(change.index).forEach(s=>{s.start-=duration;s.end-=duration;});
  }
  shots.forEach((s,i)=>{s.index=i;s.label=s.label.replace(/^Shot \d+/,`Shot ${i+1}`);});
  next.boundaries=shots.slice(1).map((s,i)=>({index:i+1,at:s.start,min:shots[i].start+.2,max:s.end-.2}));return next;
}
async function changeSourceCut(doc,change){
  if(cutBusy)return;cutBusy=true;$('#showSceneVideo').pause();cancelShowAutoPreview();const scene=showEdit.scenes[showEdit.selected],absolute=scene.start+showPlaybackOffset();
  const began=performance.now(),host=$('#showEditorTimeline');host.dataset.pending='true';requestAnimationFrame(()=>host.dataset.feedbackMs=(performance.now()-began).toFixed(1));
  const original=showEdit.timelineCache;showEdit.timelineCache=optimisticCutDocument(doc,change);selectedShowCut=null;renderCutTimelines();$('#showPreviewStatus').textContent='Saving…';
  try{
    const result=await api('/montara/show/cuts',{project_id:doc.project_id,revision:doc.revision,...change});
    host.dataset.saveMs=(performance.now()-began).toFixed(1);host.dataset.serverMs=result.processing_ms;
    showPlaybackState.cache.clear();showEditor.selected=null;
    showPushUndo({type:'cut',operationId:result.operation_id,sceneId:scene.id,change:structuredClone(change)});
    let target=change.op==='split'?Math.round(change.at*doc.fps)/doc.fps:absolute;
    if(change.op==='delete'){const shot=doc.shots[change.index];target=absolute<=shot.start?absolute:absolute<shot.end?shot.start:absolute-result.removed;}
    applyShowEditorData(result.editor,scene.id);const next=showEdit.scenes[showEdit.selected];showEdit.seekAfterEdit=Math.max(0,Math.min(next.end-next.start,target-next.start));showPlaybackState.liveEditing=true;showEdit.skipAutoPreviewOnce=change.op==='split';renderShowScene();
    $('#showPreviewStatus').textContent='Saved';if(change.op!=='split')scheduleShowAutoPreview();
  }catch(error){showEdit.timelineCache=original;$('#showPreviewStatus').textContent=error.message;renderCutTimelines();}finally{cutBusy=false;host.dataset.pending='false';}
}

function cutMenu(event,doc,shot,at,onSelect){
  document.querySelector('.cut-context')?.remove();const menu=document.createElement('div');menu.className='cut-context';menu.setAttribute('role','menu');
  const action=(name,fn)=>{const button=document.createElement('button');button.type='button';button.textContent=name;button.setAttribute('role','menuitem');button.onclick=()=>{menu.remove();fn();};menu.append(button);};
  action('Edit framing',()=>onSelect(shot));action('Split here',()=>changeSourceCut(doc,{op:'split',at}));action('Delete shot',()=>changeSourceCut(doc,{op:'delete',index:shot.index}));
  document.body.append(menu);menu.style.left=Math.min(event.clientX,window.innerWidth-menu.offsetWidth-8)+'px';menu.style.top=Math.min(event.clientY,window.innerHeight-menu.offsetHeight-8)+'px';menu.querySelector('button').focus();
  const close=e=>{if(!menu.contains(e.target)){menu.remove();document.removeEventListener('pointerdown',close,true);}};document.addEventListener('pointerdown',close,true);menu.onkeydown=e=>{if(e.key==='Escape')menu.remove();};
}

function cutKind(){return showModeReview.kind==='podcast'?'podcast':showModeReview.kind==='storytelling'?'story':'show';}
async function cutDocument(kind){if(kind==='show' && showEdit.timelineCache?.project_id===state.projectId)return showEdit.timelineCache;return api('/edit/timeline?kind='+kind);}
function makeCutTrack(doc,scene,label,onSelect){
  const row=document.createElement('div');row.className='cut-track';
  const heading=document.createElement('strong');heading.textContent=label;row.append(heading);
  const scroll=document.createElement('div');scroll.className='cut-scroll';const bed=document.createElement('div');bed.className='cut-bed';scroll.append(bed);row.append(scroll);
  const length=scene.end-scene.start;
  const sourceEditable=doc.kind==='show' && cutKind()==='show';
  const ranges=doc.kind==='show'||doc.kind==='music'?[[scene.start,scene.end]]:scene.segments;
  const toOffset=time=>{let acc=0;for(const [a,b] of ranges){if(time<a)return acc;if(time<=b)return acc+time-a;acc+=b-a;}return acc;};
  const toTime=position=>{let acc=0;for(const [a,b] of ranges){if(position<=acc+b-a)return a+position-acc;acc+=b-a;}return ranges.at(-1)[1];};
  bed.style.minWidth='0';
  const atClick=event=>toTime(Math.max(0,Math.min(length,(event.clientX-bed.getBoundingClientRect().left)/bed.getBoundingClientRect().width*length)));
  if(sourceEditable){
    const tools=document.createElement('div');tools.className='cut-tools';
    const scissors=document.createElement('button');scissors.type='button';scissors.className='btn ghost small';scissors.textContent='✂';scissors.setAttribute('aria-label','Scissors');scissors.title='Split at the white playhead';
    scissors.onclick=()=>{const current=showEdit.scenes[showEdit.selected];changeSourceCut(doc,{op:'split',at:current.start+showPlaybackOffset()});};
    const remove=document.createElement('button');remove.type='button';remove.className='btn ghost small';remove.textContent='⌫';remove.setAttribute('aria-label','Delete shot');remove.title='Delete selected shot';remove.dataset.cutDelete='';
    const valid=selectedShowCut?.project===doc.project_id&&selectedShowCut?.revision===doc.revision;remove.disabled=!valid;
    remove.onclick=()=>{if(selectedShowCut)changeSourceCut(doc,{op:'delete',index:selectedShowCut.index});};
    const label=document.createElement('span');label.className='hint';label.dataset.cutSelection='';label.textContent=valid?`Shot ${selectedShowCut.index+1} selected`:'Select a shot';tools.append(scissors,remove,label);$('#showCutToolsHost').replaceChildren(tools);
    bed.onclick=e=>{if(e.ctrlKey||e.metaKey)changeSourceCut(doc,{op:'split',at:atClick(e)});};
    row.onkeydown=e=>{if((e.key==='Delete'||e.key==='Backspace')&&e.target.closest('.cut-shot')&&selectedShowCut&&!cutBusy){e.preventDefault();changeSourceCut(doc,{op:'delete',index:selectedShowCut.index});}};
  }
  let offset=0;
  for(const [a,b] of ranges){
    for(const shot of doc.shots){const lo=Math.max(a,shot.start),hi=Math.min(b,shot.end);if(hi<=lo)continue;
      const block=document.createElement('button');block.type='button';block.className='cut-shot';block.style.left=((offset+lo-a)/length*100)+'%';block.style.width=((hi-lo)/length*100)+'%';block.textContent=shot.label;block.title=`${shot.start.toFixed(2)}–${shot.end.toFixed(2)}s · ${shot.label}. Right-click to edit this shot.`;
      // Capture the offset for this source interval, not the loop's final accumulator.
      const seekOffset=offset+lo-a;
      block.dataset.shotIndex=shot.index;block.dataset.cutKind=doc.kind;
      const selected=sourceEditable&&selectedShowCut?.project===doc.project_id&&selectedShowCut?.revision===doc.revision&&selectedShowCut?.index===shot.index;
      block.classList.toggle('selected',!!selected);if(sourceEditable)block.setAttribute('aria-pressed',String(!!selected));
      block.onclick=e=>{e.stopPropagation();if(sourceEditable&&(e.ctrlKey||e.metaKey)){changeSourceCut(doc,{op:'split',at:atClick(e)});return;}if(doc.kind==='music')onSelect(shot);else{$('#showSceneVideo').pause();if(sourceEditable)selectShowCut(doc,shot,row);seekShowTimeline(e.detail?toOffset(atClick(e)):seekOffset);updateShowCursor();}};
      block.oncontextmenu=e=>{e.preventDefault();e.stopPropagation();if(sourceEditable){if(e.ctrlKey){changeSourceCut(doc,{op:'split',at:atClick(e)});return;}selectShowCut(doc,shot,row);seekShowTimeline(toOffset(atClick(e)));updateShowCursor();cutMenu(e,doc,shot,atClick(e),onSelect);}else onSelect(shot);};bed.append(block);
    }
    offset+=b-a;
  }
  for(const boundary of doc.boundaries){
      const a=ranges[0][0],b=ranges.at(-1)[1];if(boundary.at<a || boundary.at>b || boundary.max<=boundary.min)continue;
      const minimum=Math.max(a,boundary.min),maximum=Math.min(b,boundary.max);if(maximum-minimum<1/doc.fps)continue;
      const handle=document.createElement('button');handle.type='button';handle.className='cut-handle';handle.setAttribute('aria-label',`${label}: move cut ${boundary.index}`);handle.setAttribute('role','slider');handle.setAttribute('aria-valuemin',minimum.toFixed(2));handle.setAttribute('aria-valuemax',maximum.toFixed(2));
      const position=at=>{handle.style.left=(toOffset(at)/length*100)+'%';handle.title=`Cut ${boundary.index} · ${at.toFixed(2)}s. Drag, use arrow keys, or double-click for an exact time.`;handle.setAttribute('aria-valuenow',at.toFixed(2));};position(boundary.at);
      let drag=null,next=boundary.at;
      const clamp=at=>Math.max(Math.ceil(minimum*doc.fps)/doc.fps,Math.min(Math.floor(maximum*doc.fps)/doc.fps,Math.round(at*doc.fps)/doc.fps));
      const status=text=>{const el=$(doc.kind==='music'?'#musicCutStatus':'#showProgramStatus');if(el)el.textContent=text;};
      const save=async at=>{if(cutBusy)return;cutBusy=true;status('Saving cut…');try{
        const saved=await showPatch('/edit/timeline',{kind:doc.kind,project_id:doc.project_id,revision:doc.revision,index:boundary.index,at});
        if(doc.kind==='music'){musicTimeline=saved;await refreshMusicReview();renderMusicCuts();}
        else{
          if(doc.kind==='podcast')showModeReview.podcast=await api('/show/podcast/plan');
          if(doc.kind==='story')showModeReview.story=(await api('/show/story/plan')).plan;
          await refreshShowEditor(showEdit.scenes[showEdit.selected].id);
          await renderCutTimelines();
        }
        status('Cut saved. Preview when you are ready.');
      }catch(error){status(error.message);if(doc.kind==='music')await loadMusicCuts();else await renderCutTimelines();}finally{cutBusy=false;}};
      handle.onpointerdown=e=>{if(e.button!==0||cutBusy||(sourceEditable&&(e.ctrlKey||e.metaKey)))return;e.preventDefault();e.stopPropagation();$('#showSceneVideo').pause();drag={x:e.clientX,at:boundary.at,width:bed.getBoundingClientRect().width};next=boundary.at;handle.setPointerCapture(e.pointerId);handle.classList.add('dragging');};
      handle.onpointermove=e=>{if(!drag)return;next=clamp(toTime(toOffset(drag.at)+(e.clientX-drag.x)/drag.width*length));position(next);status(`Cut ${boundary.index} · ${next.toFixed(2)}s`);};
      handle.onpointerup=e=>{if(!drag)return;e.stopPropagation();drag=null;handle.classList.remove('dragging');if(Math.abs(next-boundary.at)>.001)save(next);};
      handle.onpointercancel=()=>{drag=null;position(boundary.at);handle.classList.remove('dragging');};
      handle.onclick=e=>{e.stopPropagation();if(!sourceEditable||cutBusy)return;const time=e.detail?atClick(e):boundary.at;if(e.ctrlKey||e.metaKey){changeSourceCut(doc,{op:'split',at:time});return;}const shot=doc.shots.find(s=>s.start<=time&&s.end>time);if(shot){selectShowCut(doc,shot,row);$('#showSceneVideo').pause();seekShowTimeline(e.detail?toOffset(time):toOffset(shot.start));updateShowCursor();}};
      handle.onkeydown=e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();save(clamp(boundary.at+(e.key==='ArrowRight'?1:-1)*(e.shiftKey?.5:1/doc.fps)));};
      handle.ondblclick=e=>{e.preventDefault();openExactCut(boundary,minimum,maximum,doc.fps,save);};bed.append(handle);
    }
  if(doc.kind!=='music'){const cursor=document.createElement('i');cursor.className='show-playhead';bed.append(cursor);wireShowScrub(bed,length,label);}
  return row;
}
function openExactCut(boundary,min,max,fps,save){
  const dialog=document.createElement('dialog');dialog.className='cut-dialog';dialog.innerHTML='<form><h3>Move cut</h3><label>Time in the full edit (seconds)<input type="number" required step="any"></label><p class="hint"></p><div class="actions"><button type="button">Cancel</button><button class="btn primary">Save cut</button></div></form>';
  const input=dialog.querySelector('input');input.value=boundary.at.toFixed(3);input.min=Math.ceil(min*fps)/fps;input.max=Math.floor(max*fps)/fps;dialog.querySelector('p').textContent=`Between ${Number(input.min).toFixed(2)} and ${Number(input.max).toFixed(2)} seconds. Arrow keys move by one frame; Shift moves by half a second.`;
  dialog.querySelector('button[type=button]').onclick=()=>dialog.close();dialog.querySelector('form').onsubmit=e=>{e.preventDefault();const at=Math.round(Number(input.value)*fps)/fps;dialog.close();save(at);};dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();input.focus();
}
async function renderCutTimelines(){
  const token=++cutLoadToken;if($('#showReview').hidden)return;
  try{const kind=cutKind(),docs=await Promise.all([cutDocument(kind)]);if(token!==cutLoadToken||$('#showReview').hidden)return;
    if(kind!=='show')$('#showCutToolsHost').replaceChildren();
    const scene=showEdit.scenes[showEdit.selected],host=$('#showEditorTimeline');host.querySelectorAll('.cut-track,.cut-help').forEach(el=>el.remove());
    host.querySelector('.show-video-bed')?.parentElement.classList.add('cut-replaced');
    if(kind==='podcast')host.querySelector(':scope > p.hint:not(.cut-help)')?.remove();
    host.style.setProperty('--timeline-width',Math.max(650,docs.reduce((n,d)=>Math.max(n,d.shots.filter(s=>s.start<scene.end&&s.end>scene.start).length),0)*65+90)+'px');
    const before=host.querySelector('.show-track:not(.cut-replaced)');
    docs.forEach(doc=>host.insertBefore(makeCutTrack(doc,scene,doc.kind==='podcast'?'Cameras':doc.kind==='story'?'Story pictures':kind==='show'?'Video cuts':'Voice cuts',shot=>{
      if(doc.kind==='podcast')openPodcastShot(shot.index);
      else if(doc.kind==='story')$('#showDecisionsOpen').click();
      else openShowShotFrame(doc,shot);
    }),before));
    const help=document.createElement('p');help.className='hint cut-help';help.textContent=kind==='show'?'Drag the white playhead, then Scissors to split. Ctrl/⌘ + click cuts here. Select a shot to delete it. Orange lines move the cuts.':'Drag a cut line to move it. Right-click a shot to edit its picture or framing.';host.insertBefore(help,before);updateShowCursor();
  }catch(error){$('#showProgramStatus').textContent=error.message;}
}
async function openShowShotFrame(doc,shot){
  try{const track=await api('/show/narrator'),original=track.shots[shot.index];$('#showSceneVideo').pause();
    const dialog=document.createElement('dialog');dialog.className='cut-dialog';dialog.innerHTML='<form><h3>Shot framing</h3><div class="cut-aim"><video muted playsinline></video><i></i></div><p class="hint">Click the image to choose the focus. Choose where the camera looks in this shot. The preview updates after saving.</p><label>Zoom<input name="zoom" type="range" min="1" max="2.5" step=".05"></label><label>Look left / right<input name="x" type="range" min="0" max="1" step=".01"></label><label>Look up / down<input name="y" type="range" min="0" max="1" step=".01"></label><p class="cut-error"></p><div class="actions"><button type="button">Cancel</button><button class="btn primary">Save framing</button></div></form>';
    const field=name=>dialog.querySelector(`[name="${name}"]`);field('zoom').value=original.zoom;field('x').value=(original.face||original.focus||[.5,.5])[0];field('y').value=(original.face||original.focus||[.5,.5])[1];
    const aim=dialog.querySelector('.cut-aim'),image=aim.querySelector('video'),box=aim.querySelector('i');image.src=track.source_url;image.onloadedmetadata=()=>{image.currentTime=(original.source[0]+original.source[1])/2;};
    const draw=()=>{const w=100/Number(field('zoom').value),x=Math.max(w/2,Math.min(100-w/2,Number(field('x').value)*100)),y=Math.max(w/2,Math.min(100-w/2,Number(field('y').value)*100));Object.assign(box.style,{width:w+'%',height:w+'%',left:(x-w/2)+'%',top:(y-w/2)+'%'});};
    ['zoom','x','y'].forEach(n=>field(n).oninput=draw);aim.onclick=e=>{const rect=aim.getBoundingClientRect();field('x').value=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));field('y').value=Math.max(0,Math.min(1,(e.clientY-rect.top)/rect.height));draw();};draw();
    dialog.querySelector('button[type=button]').onclick=()=>dialog.close();dialog.onclose=()=>{image.removeAttribute('src');image.load();dialog.remove();};dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();try{await api('/show/narrator/framing',{project_id:doc.project_id,revision:doc.revision,op:'frame',start:shot.start,end:shot.end,zoom:Number(field('zoom').value),face:[Number(field('x').value),Number(field('y').value)],move:'cut'});dialog.close();await refreshShowEditor(showEdit.scenes[showEdit.selected].id);await renderCutTimelines();$('#showProgramStatus').textContent='Framing saved. Updating preview…';}catch(error){dialog.querySelector('.cut-error').textContent=error.message;}};document.body.append(dialog);dialog.showModal();
  }catch(error){$('#showProgramStatus').textContent=error.message;}
}
async function loadMusicCuts(){try{musicTimeline=await cutDocument('music');renderMusicCuts();}catch(error){$('#musicCutStatus').textContent=error.message;}}
function renderMusicCuts(){
  const host=$('#musicCuts');if(!musicTimeline?.shots.length)return;host.replaceChildren(makeCutTrack(musicTimeline,{start:musicTimeline.shots[0].start,end:musicTimeline.shots.at(-1).end},'Video cuts',shot=>openMusicShot(shot.index)));
}
async function openMusicShot(index){
  try{const doc=await api('/edit/shot?index='+index),dialog=document.createElement('dialog');dialog.className='cut-dialog';dialog.innerHTML='<form><h3>Camera / viewpoint</h3><label>Shot<select name="camera"></select></label><div class="music-flat" hidden></div><img class="music-spherical" alt="Drag the 360 picture to aim this shot" draggable="false" hidden style="width:100%;cursor:grab;touch-action:none"><label>Look left / right<input name="yaw" type="range" min="-180" max="180" step="1"></label><label>Look up / down<input name="pitch" type="range" min="-85" max="85" step="1"></label><label>Field of view<input name="fov" type="range" min="30" max="120" step="1"></label><p class="hint music-sphere-hint">360 controls affect this shot only. Preview or render after saving.</p><p class="cut-error"></p><div class="actions"><button type="button">Cancel</button><button class="btn primary">Save shot</button></div></form>';
    const field=n=>dialog.querySelector(`[name="${n}"]`);doc.choices.forEach((c,i)=>field('camera').add(new Option(c.label,i)));field('yaw').value=doc.pose.yaw||0;field('pitch').value=doc.pose.pitch||0;field('fov').value=doc.pose.fov||95;let flatUI=null;const sphericalImage=new Image(),sphereTarget=dialog.querySelector('.music-spherical');
    const drawSphere=()=>{if(!doc.choices[Number(field('camera').value)].spherical || !sphericalImage.naturalWidth)return;try{sphereTarget.src=webSphericalStill(sphericalImage,{yaw:Number(field('yaw').value),pitch:Number(field('pitch').value),fov:Number(field('fov').value)});}catch(error){dialog.querySelector('.cut-error').textContent=error.message;}};
    sphericalImage.onload=drawSphere;['yaw','pitch','fov'].forEach(n=>field(n).oninput=drawSphere);
    sphereTarget.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();sphereTarget.setPointerCapture(e.pointerId);const start={x:e.clientX,y:e.clientY,yaw:Number(field('yaw').value),pitch:Number(field('pitch').value)};sphereTarget.onpointermove=move=>{field('yaw').value=((start.yaw-(move.clientX-start.x)*.35+540)%360)-180;field('pitch').value=Math.max(-85,Math.min(85,start.pitch+(move.clientY-start.y)*.25));drawSphere();};sphereTarget.onpointerup=sphereTarget.onpointercancel=()=>{sphereTarget.onpointermove=null;};};sphereTarget.onwheel=e=>{e.preventDefault();field('fov').value=Math.max(30,Math.min(120,Number(field('fov').value)+(e.deltaY>0?3:-3)));drawSphere();};
    const update=()=>{const choice=Number(field('camera').value),sphere=doc.choices[choice].spherical;['yaw','pitch','fov'].forEach(n=>field(n).closest('label').hidden=!sphere);dialog.querySelector('.music-flat').hidden=sphere;sphereTarget.hidden=!sphere;if(sphere)sphericalImage.src='/api/v1/edit/shot/frame?'+new URLSearchParams({index,choice,revision:doc.revision});dialog.querySelector('.music-sphere-hint').hidden=!sphere;
      if(!sphere){flatUI ||= mountFlatCamera(dialog.querySelector('.music-flat'),choice===0?doc.framing:{});flatUI.setImage('/api/v1/edit/shot/frame?'+new URLSearchParams({index,choice,revision:doc.revision}));}
    };field('camera').onchange=()=>{flatUI?.set({zoom:1,x:.5,y:.5});update();};update();
    dialog.querySelector('.actions button[type=button]').onclick=()=>dialog.close();dialog.onclose=()=>dialog.remove();dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();try{await showPatch('/edit/shot',{project_id:doc.project_id,revision:doc.revision,index,choice:Number(field('camera').value),yaw:Number(field('yaw').value),pitch:Number(field('pitch').value),fov:Number(field('fov').value),flat_framing:flatUI?.get()});dialog.close();await refreshMusicReview();await loadMusicCuts();$('#musicCutStatus').textContent='Shot saved.';}catch(error){dialog.querySelector('.cut-error').textContent=error.message;}};document.body.append(dialog);dialog.showModal();
  }catch(error){$('#musicCutStatus').textContent=error.message;}
}
document.addEventListener('montara:show-scene',renderCutTimelines);

function previewMusicShot(index){
  const dialog=document.createElement('dialog');dialog.className='cut-dialog';dialog.style.maxWidth='850px';const title=document.createElement('h3');title.textContent=`Shot ${index+1}`;const video=document.createElement('video');video.controls=true;video.style.width='100%';video.src='/api/v1/wizard/review/preview/'+index+'?v='+Date.now();const close=document.createElement('button');close.className='btn';close.textContent='Close preview';close.onclick=()=>dialog.close();dialog.onclose=()=>{video.pause();video.removeAttribute('src');dialog.remove();};dialog.append(title,video,close);document.body.append(dialog);dialog.showModal();
}

async function refreshMusicReview(){
  await refreshFrames(true);clearInterval(state.framesPoll);state.framesPoll=setInterval(()=>{if($('#frames').hidden){clearInterval(state.framesPoll);state.framesPoll=null;return;}refreshFrames(false).catch(console.warn);},1500);
}
