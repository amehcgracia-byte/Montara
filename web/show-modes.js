"use strict";
const showSources={podcast:{people:[],cameras:[]},story:{narration:null,clips:[]}};
const showModeReview={kind:null,projectId:null,captionsOn:false,captionRevision:0,defaults:{},podcast:null,story:null,captionDrag:null,shot:null,frameBusy:false,framePending:false};
async function uploadShowSupport(files){
  if(rejectRaw360(files))throw new Error("Export a stitched 360 MP4 from your camera app first.");
  const paths=[];state.uploads++;renderShowInput();
  try{for(const file of files){
    const response=await fetch('/api/v1/wizard/upload',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Zucker-Filename':encodeURIComponent(file.name)},body:file});const data=await response.json();
    if(!response.ok)throw new Error(data.error?.message || 'Could not upload this file');
    const record=['videos','master','songs','ignored'].flatMap(k=>data[k] || []).find(r=>r.path);
    if(!record)throw new Error('No usable media path was returned');paths.push({path:record.path,name:file.name,projection:record.projection});
  }return paths;}finally{state.uploads--;renderShowInput();}
}
function usingShowKit(){return !!videos()[0]?.sample && state.sampleVariant===showEdit.pace;}
function showInputURL(path){return '/montara/show/input?path='+encodeURIComponent(path);}
function renderShowMaterialBoxes(){
  const pod=showEdit.pace==='podcast',story=showEdit.pace==='storytelling';
  $('#showDropTitle').textContent=story?'Drop your videos and narration here':'Drop your videos here';
  $('#showDropHint').textContent=story?'Videos, pictures and optional narration audio':'Every camera, including fixed and 360 cameras';
  const files=pod&&showSources.podcast.cameras.length?showSources.podcast.cameras.map(c=>({path:c.path,name:c.name||c.path.split('/').pop()})):story&&showSources.story.clips.length?[...(showSources.story.narration?[{...showSources.story.narration,audio:true}]:[]),...showSources.story.clips]:videos();
  const signature=JSON.stringify(files.map(f=>[f.path,f.name]));
  if($('#showVideoMaterials').dataset.signature===signature)return;
  $('#showVideoMaterials').dataset.signature=signature;
  $('#showVideoMaterials').innerHTML=files.map((f,i)=>{const url=escapeHtml(showInputURL(f.path)),image=/\.(png|jpe?g|webp|gif)$/i.test(f.path),audio=f.audio||/\.(wav|mp3|m4a|flac|ogg)$/i.test(f.path);return `<li>${audio?`<audio controls preload="none" src="${url}"></audio>`:image?`<img src="${url}" alt="">`:`<video muted playsinline preload="metadata" src="${url}#t=0.2"></video>`}<span>${String(i+1).padStart(2,'0')} · ${escapeHtml(f.name||f.path.split('/').pop())}</span><button class="link" type="button" data-show-material-remove="${i}" aria-label="Remove ${escapeHtml(f.name||'source')}">×</button></li>`;}).join('');
  $('#showVideoMaterials').onclick=event=>{const button=event.target.closest('[data-show-material-remove]');if(!button)return;const file=files[Number(button.dataset.showMaterialRemove)];showEdit.resume=null;if(pod){showSources.podcast.cameras=showSources.podcast.cameras.filter(c=>c.path!==file.path);state.files=state.files.filter(c=>c.path!==file.path);}else if(story){if(showSources.story.narration?.path===file.path)showSources.story.narration=null;showSources.story.clips=showSources.story.clips.filter(c=>c.path!==file.path);state.files.forEach(f=>f.sample=false);}else state.files=state.files.filter(c=>c.path!==file.path);renderShowInput();};
}
function renderShowModeInputs(){
  const kind=showEdit.pace,pod=kind==='podcast',story=kind==='storytelling';
  $('#showPaceHint').textContent=pod?'One microphone per person. Cameras follow the speakers; every shot stays editable.':story?'Narration and matching pictures, with a saved, editable montage plan.':'The original voice stays with your video.';
  $('#showPodcastInputs').hidden=!pod;$('#showStoryInputs').hidden=!story;
  $('#showModeInputStatus').textContent=state.uploads?'Uploading support files…':'';
  if(pod){
    if(!usingShowKit() && !state.uploads)for(const file of videos())if(!showSources.podcast.cameras.some(c=>c.path===file.path))showSources.podcast.cameras.push({path:file.path,name:file.name,kind:isSphere(file)?'360':'flat'});
    $('#showPodcastKitInfo').textContent=showSources.podcast.people.length?`${showSources.podcast.people.length} microphones and ${showSources.podcast.cameras.length} cameras loaded.`:usingShowKit()?'Test kit: 5 microphones, 3 fixed cameras and a 360 camera. The saved seat map is used for the first rehearsal.':'Add one microphone per person. Cameras can be fixed or 360; speaker associations are analysed locally.';
    const micSignature=JSON.stringify(showSources.podcast.people);
    if($('#showPodcastPeople').dataset.signature!==micSignature){$('#showPodcastPeople').dataset.signature=micSignature;$('#showPodcastPeople').innerHTML=showSources.podcast.people.map((p,i)=>`<div class="show-mic-row"><label>Microphone ${i+1}<input data-pod-name="${i}" value="${escapeHtml(p.name)}"><small>${escapeHtml(p.mic.split('/').pop())}</small></label><audio controls preload="none" src="${escapeHtml(showInputURL(p.mic))}"></audio><button class="link" type="button" data-pod-remove="${i}" aria-label="Remove microphone ${i+1}">×</button></div>`).join('');}

    $('#showPodcastCameraList').innerHTML=showSources.podcast.cameras.map((c,i)=>`<label>${escapeHtml(c.name)} <input type="checkbox" data-pod-360="${i}" ${c.kind==='360'?'checked':''}> 360 camera</label>`).join('');
  }
  if(story)$('#showStoryKitInfo').textContent=usingShowKit()?'Test kit: narration and 10 clips. The first montage uses an agent-reviewed reference plan; every choice is recorded.':`${showSources.story.narration?.name || 'Choose a narration'} · ${showSources.story.clips.length} pictures/clips. New material uses local matching and needs editorial review.`;
  if(story){
    const material=[...(showSources.story.narration?[{...showSources.story.narration,kind:'narration'}]:[]),...showSources.story.clips.map(c=>({...c,kind:'video'}))];
    $('#showStoryMaterials').innerHTML=material.map(fileRow).join('');
  }
  renderShowMaterialBoxes();
  let button=$('#showModeExample');
  if((pod||story)&&!usingShowKit() && !(pod?showSources.podcast.people.length:showSources.story.narration)){
    if(!button){button=document.createElement('button');button.id='showModeExample';button.type='button';button.className='btn ghost small';$('#showModeInputs').append(button);button.onclick=async()=>{state.files=[];state.projectId=null;await loadSamples(showEdit.pace);renderShowInput();};}
    button.hidden=false;button.textContent=`Use the ${pod?'Podcast':'Story'} test kit`;
  }else if(button)button.hidden=true;
}
$('#showPodcastPeople').addEventListener('change',event=>{if(event.target.dataset.podName!==undefined){showSources.podcast.people[Number(event.target.dataset.podName)].name=event.target.value.trim() || 'Person';showEdit.resume=null;}});
$('#showPodcastCameraList').addEventListener('change',event=>{if(event.target.dataset.pod360!==undefined){showSources.podcast.cameras[Number(event.target.dataset.pod360)].kind=event.target.checked?'360':'flat';showEdit.resume=null;}});
for(const [id,target] of [['#showPodcastMics','mics'],['#showPodcastCameras','cameras'],['#showStoryNarration','narration'],['#showStoryClips','clips']])$(id).addEventListener('change',async event=>{
  try{const items=await uploadShowSupport([...event.target.files]);
    if(target==='mics')showSources.podcast.people.push(...items.map(item=>({name:item.name.replace(/\.[^.]+$/,''),mic:item.path})));
    if(target==='cameras')showSources.podcast.cameras.push(...items.map(item=>({name:item.name,path:item.path,kind:/360|insv/i.test(item.name)?'360':'flat'})));
    if(target==='narration')showSources.story.narration=items[0];
    if(target==='clips')showSources.story.clips.push(...items);
    showEdit.resume=null;renderShowInput();
  }catch(error){$('#showModeInputStatus').textContent=error.message;}finally{event.target.value='';}
});
async function putShow(path,body){const response=await fetch('/api/v1'+path,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw new Error(data.error?.message || 'Could not save the media setup');return data;}
async function prepareShowSources(){
  if(!['podcast','storytelling'].includes(showEdit.pace))return;
  if(usingShowKit()){
    const prepared=await api(`/montara/show/examples/${showEdit.pace}/prepare`,{project_id:state.projectId});
    if(showEdit.pace==='podcast' && showSources.podcast.people.length)await putShow('/show/podcast',{...prepared,people:showSources.podcast.people,cameras:showSources.podcast.cameras,render_width:640,render_height:360});
    return;
  }
  if(showEdit.pace==='podcast'){
    const setup=showSources.podcast;
    if(!setup.people.length)throw new Error('Add the microphone tracks, or use the Podcast test kit.');
    const cameras=setup.cameras.length?setup.cameras:videos().map(file=>({path:file.path,name:file.name,kind:/360|insv/i.test(file.name)?'360':'flat'}));
    await putShow('/show/podcast',{people:setup.people,cameras});
  }else{
    if(!showSources.story.narration || !showSources.story.clips.length)throw new Error('Add narration and pictures/clips, or use the Story test kit.');
    await putShow('/show/story',{narration:showSources.story.narration.path,clips:showSources.story.clips.map(item=>item.path)});
  }
}
async function loadShowModeReview(data){
  showModeReview.kind=data.plan?.style || showEdit.pace;
  showEdit.pace=showModeReview.kind==='choe'?'fast':showModeReview.kind==='calm'?'normal':showModeReview.kind;
  showModeReview.projectId=data.project_id || state.projectId;showModeReview.captionsOn=!!data.captions_enabled;showModeReview.captionRevision=data.caption_revision || 0;showModeReview.defaults=data.caption_defaults || {};
  document.body.dataset.showKind=showModeReview.kind;
  $('#showReview h2').textContent=showModeReview.kind==='podcast'?'Your podcast, shaped.':showModeReview.kind==='storytelling'?'Your story, shaped.':'Your video, shaped.';
  $('#showReview .lead').textContent=showModeReview.kind==='podcast'?'Review the camera changes and subtitles. Right-click a shot to adjust its viewpoint.':showModeReview.kind==='storytelling'?'Review the story, its chosen clips and subtitles. Every decision stays editable.':'Watch each part. Keep the suggested effects, or leave it clean.';
  $('#showSceneText').setAttribute('aria-label',showModeReview.kind==='podcast'?'Podcast transcript':'Transcript. Select words to add an effect.');
  $('#showCaptionsOn').checked=showModeReview.captionsOn;
  $('#showCaptionSize').value=showModeReview.defaults.size || (showEdit.pace==='fast'?76:58);
  $('#showCaptionPreset').value=showModeReview.defaults.fun_effect==='pop'?'pop':showModeReview.defaults.font==='Impact'?'bold':'clean';
  $('#showCameraEdit').hidden=showModeReview.kind!=='podcast';
  showModeReview.podcast=null;showModeReview.story=null;
  if(showModeReview.kind==='podcast'){showModeReview.podcast=await api('/show/podcast/plan');showSources.podcast={people:structuredClone(showModeReview.podcast.people),cameras:structuredClone(showModeReview.podcast.cameras)};}
  if(showModeReview.kind==='storytelling')showModeReview.story=(await api('/show/story/plan')).plan;
}
function programTime(){
  let remaining=showPlaybackOffset();const scene=showEdit.scenes[showEdit.selected];
  for(const [a,b] of scene?.segments || []){if(remaining<b-a)return a+remaining;remaining-=b-a;}
  return scene?.segments?.at(-1)?.[1] || scene?.start+showPlaybackOffset() || 0;
}
function programOffset(time){
  let total=0;const scene=showEdit.scenes[showEdit.selected];
  for(const [a,b] of scene?.segments || []){if(time>=a && time<=b)return total+time-a;total+=b-a;}
  return null;
}
function activePodcastShot(){const time=programTime();return (showModeReview.podcast?.shots || []).findIndex(s=>s.start<=time && time<s.end);}
function renderShowProgramTimeline(){if(typeof renderCutTimelines==='function')renderCutTimelines();}
function requestCameraFrame(){
  const edit=showModeReview.shot;if(!edit)return;
  if(showModeReview.frameBusy){showModeReview.framePending=true;return;}
  const view=edit.doc.views[Number($('#showCameraView').value)],camera=edit.doc.cameras[view.camera],image=$('#showCameraFrame');
  const flat=camera.kind!=='360';$('#showFlatCamera').hidden=!flat;$('#showCameraStage').hidden=flat;$('#showSphereZoomLabel').hidden=flat;$('#showSphereHint').hidden=flat;
  if(flat){edit.flatUI ||= mountFlatCamera($('#showFlatCamera'),edit.framing);edit.flatUI.setImage('/api/v1/show/podcast/view?'+new URLSearchParams({path:camera.path,t:(edit.start+edit.end)/2}));return;}
  showModeReview.frameBusy=true;showModeReview.framePending=false;
  const complete=()=>{showModeReview.frameBusy=false;if(showModeReview.framePending)requestCameraFrame();};image.onload=complete;image.onerror=()=>{$('#showCameraStatus').textContent='Could not load this camera frame.';complete();};
  if(camera.kind==='360')image.src='/api/v1/show/podcast/view?'+new URLSearchParams({path:camera.path,yaw:edit.yaw,pitch:edit.pitch,fov:!edit.aimModified && view.projection==='planet'?view.fov:edit.fov,projection:!edit.aimModified?view.projection:'flat',t:(edit.start+edit.end)/2});
  else image.src='/api/v1/show/podcast/view?'+new URLSearchParams({path:camera.path,t:(edit.start+edit.end)/2});
}
function openPodcastShot(index=activePodcastShot()){
  const doc=showModeReview.podcast;if(!doc?.shots?.[index]){$('#showProgramStatus').textContent='Move the playhead onto a camera shot first.';return;}
  $('#showSceneVideo').pause();clearShowSelection();const shot=doc.shots[index],view=shot.override || doc.views[shot.view];
  showModeReview.shot={doc,index,start:shot.start,end:shot.end,framing:shot.flat_framing || {zoom:1,x:.5,y:.5},aimModified:!!shot.override,yaw:view.yaw || 0,pitch:view.pitch || 0,fov:view.fov && view.fov<=120?view.fov:70};
  $('#showCameraView').replaceChildren(...doc.views.map((v,i)=>new Option(`${doc.cameras[v.camera].name || `Camera ${v.camera+1}`} · ${v.people.map(n=>doc.people[n]?.name).join(', ') || v.kind}`,String(i))));$('#showCameraView').value=String(shot.view);
  $('#showCameraZoom').value=showModeReview.shot.fov;$('#showCameraReason').value='';$('#showCameraStatus').textContent='';$('#showCameraShotInfo').textContent=`${shot.start.toFixed(1)}–${shot.end.toFixed(1)}s · Changes affect this interval only.`;
  $('#showCameraDialog').showModal();requestCameraFrame();
}
$('#showCameraView').onchange=()=>{const view=showModeReview.shot.doc.views[Number($('#showCameraView').value)];showModeReview.shot.flatUI?.set({zoom:1,x:.5,y:.5});Object.assign(showModeReview.shot,{framing:{zoom:1,x:.5,y:.5},aimModified:false,yaw:view.yaw || 0,pitch:view.pitch || 0,fov:view.fov && view.fov<=120?view.fov:70});$('#showCameraZoom').value=showModeReview.shot.fov;requestCameraFrame();};
$('#showCameraZoom').oninput=()=>{showModeReview.shot.aimModified=true;showModeReview.shot.pitch=Math.max(-85,Math.min(85,showModeReview.shot.pitch));showModeReview.shot.fov=Number($('#showCameraZoom').value);requestCameraFrame();};
$('#showCameraFrame').onpointerdown=event=>{
  const edit=showModeReview.shot,view=edit.doc.views[Number($('#showCameraView').value)];if(edit.doc.cameras[view.camera].kind!=='360')return;
  event.preventDefault();event.target.setPointerCapture(event.pointerId);const start={x:event.clientX,y:event.clientY,yaw:edit.yaw,pitch:edit.pitch};
  event.target.onpointermove=move=>{edit.aimModified=true;edit.yaw=((start.yaw-(move.clientX-start.x)*.35+540)%360)-180;edit.pitch=Math.max(-85,Math.min(85,start.pitch+(move.clientY-start.y)*.25));requestCameraFrame();};
  const end=()=>{event.target.onpointermove=null;event.target.onpointerup=null;event.target.onpointercancel=null;};event.target.onpointerup=end;event.target.onpointercancel=end;
};
$('#showCameraSave').onclick=async()=>{const edit=showModeReview.shot;$('#showCameraSave').disabled=true;try{
  showModeReview.podcast=await showPatch(`/show/podcast/plan/${edit.index}`,{project_id:showModeReview.projectId,revision:edit.doc.revision,view:Number($('#showCameraView').value),yaw:edit.yaw,pitch:edit.pitch,fov:edit.fov,use_view:!edit.aimModified,reason:$('#showCameraReason').value,flat_framing:edit.flatUI?.get() || edit.framing});
  $('#showCameraDialog').close();$('#showProgramStatus').textContent='Camera shot saved. Preview this part to update the video.';renderShowProgramTimeline();
}catch(error){$('#showCameraStatus').textContent=error.message;}finally{$('#showCameraSave').disabled=false;}};
$('#showCameraCancel').onclick=()=>$('#showCameraDialog').close();$('#showCameraEdit').onclick=()=>openPodcastShot();
$('#showSceneVideo').addEventListener('contextmenu',event=>{if(showModeReview.kind==='podcast'){event.preventDefault();event.stopImmediatePropagation();openPodcastShot();}},true);
async function refreshShowCaptionData(){const data=await api('/show/scenes');const current=showEdit.scenes[showEdit.selected]?.id;showEdit.scenes=data.scenes;showEdit.selected=Math.max(0,showEdit.scenes.findIndex(s=>s.id===current));showModeReview.captionRevision=data.caption_revision;showModeReview.captionsOn=data.captions_enabled;showModeReview.defaults=data.caption_defaults || {};drawShowCaptions();}
function liveCaption(){const scene=showEdit.scenes[showEdit.selected],time=(scene?.start || 0)+showPlaybackOffset();return scene?.captions?.find(c=>c.start<=time && time<c.end);}
function drawShowCaptions(){
  const layer=$('#showCaptionLayer');if(showModeReview.captionDrag || $('#showReview').hidden)return;
  const cue=showModeReview.captionsOn?liveCaption():null;
  if(!cue){layer.replaceChildren();return;}
  layer.dataset.rendered=String(showPlaybackState.mode==='rendered');
  let node=layer.querySelector('.show-preview-caption');if(!node){node=document.createElement('div');node.className='show-preview-caption';node.tabIndex=0;node.setAttribute('aria-label','Subtitle: drag to move, drag its corner to resize');node.innerHTML='<span></span><i title="Resize subtitle"></i>';node.onpointerdown=startShowCaptionDrag;layer.append(node);}
  const style=cue.style_override || {},newCue=node.dataset.cue!==cue.id;node.dataset.cue=cue.id;node.querySelector('span').textContent=cue.lines.join(' ');
  Object.assign(node.style,{left:(style.horizontal ?? 50)+'%',top:(style.vertical ?? 74)+'%',fontSize:((style.size || 58)*$('#showSceneVideo').getBoundingClientRect().height/1080)+'px',fontFamily:style.font==='Impact'?'Impact,sans-serif':'Arial,sans-serif',fontWeight:'700',color:style.color || '#fff'});
  node.classList.toggle('caption-pop',style.fun_effect==='pop');if(newCue && style.fun_effect==='pop')node.animate([{scale:.8},{scale:1}],{duration:180});
}
function startShowCaptionDrag(event){
  if(event.button!==0)return;event.preventDefault();event.stopPropagation();$('#showSceneVideo').pause();const cue=liveCaption();if(!cue)return;const node=event.currentTarget,stage=$('#showCaptionLayer').getBoundingClientRect(),initial={...cue.style_override},offset=showPlaybackOffset();
  activateShowLive(offset);node.setPointerCapture(event.pointerId);const drag=showModeReview.captionDrag={cue,node,initial,x:event.clientX,y:event.clientY,stage,resize:event.target.tagName==='I',changes:{}};
  node.onpointermove=move=>{const dx=(move.clientX-drag.x)/stage.width,dy=(move.clientY-drag.y)/stage.height;drag.changes=drag.resize?{size:Math.max(24,Math.min(140,(initial.size || 58)+dx*1080))}:{horizontal:Math.max(0,Math.min(100,(initial.horizontal ?? 50)+dx*100)),vertical:Math.max(0,Math.min(100,(initial.vertical ?? 74)+dy*100))};cue.style_override={...initial,...drag.changes};showModeReview.captionDrag=null;drawShowCaptions();showModeReview.captionDrag=drag;};
  const finish=async cancel=>{node.onpointermove=null;node.onpointerup=null;node.onpointercancel=null;showModeReview.captionDrag=null;try{if(cancel)cue.style_override=initial;else if(Object.keys(drag.changes).length){const saved=await showPatch('/show/captions/'+cue.id,{project_id:showModeReview.projectId,revision:showModeReview.captionRevision,changes:drag.changes});showModeReview.captionRevision=saved.revision;Object.assign(cue,saved.cue);$('#showCaptionStatus').textContent='Subtitle placement saved.';}}catch(error){cue.style_override=initial;$('#showCaptionStatus').textContent=error.message;}drawShowCaptions();};node.onpointerup=()=>finish(false);node.onpointercancel=()=>finish(true);
}
$('#showCaptionsOn').onchange=async()=>{try{await api('/show/captions/enabled',{enabled:$('#showCaptionsOn').checked,project_id:showModeReview.projectId});await refreshShowCaptionData();activateShowLive();}catch(error){$('#showCaptionStatus').textContent=error.message;}};
async function saveShowCaptionStyle(){const preset=$('#showCaptionPreset').value;try{
  const saved=await api('/show/captions/style',{project_id:showModeReview.projectId,revision:showModeReview.captionRevision,changes:{size:Number($('#showCaptionSize').value),font:preset==='bold'?'Impact':'Arial Bold',fun_effect:preset==='pop'?'pop':'none'}});showModeReview.captionRevision=saved.revision;await refreshShowCaptionData();activateShowLive();$('#showCaptionStatus').textContent='Subtitle style saved. Preview when ready.';
}catch(error){$('#showCaptionStatus').textContent=error.message;}}
$('#showCaptionPreset').onchange=saveShowCaptionStyle;$('#showCaptionSize').onchange=saveShowCaptionStyle;
$('#showCaptionSize').oninput=()=>{const cue=liveCaption();if(cue){cue.style_override={...cue.style_override,size:Number($('#showCaptionSize').value)};drawShowCaptions();}};
$('#showDecisionsOpen').onclick=async()=>{try{
  const events=await api('/show/decisions'),list=$('#showDecisionsList');list.replaceChildren();
  if(showEdit.direction?.method==='local-text-rules'){
    const notice=document.createElement('p');notice.className='hint';notice.textContent='Gamer framing · local text rules, no LLM. Mild emphasis on selected phrases; hand-aimed shots are kept.';list.append(notice);
    for(const cue of showEdit.direction.emphases){const box=document.createElement('div');box.className='show-decision';const text=document.createElement('p');text.textContent=cue.quote;const reason=document.createElement('small');reason.textContent=`${cue.reason} · ${cue.zoom}× · ${cue.start.toFixed(1)}–${cue.end.toFixed(1)}s`;box.append(text,reason);list.append(box);}
    if(!showEdit.direction.emphases.length){const text=document.createElement('p');text.textContent='No clear text cue: automatic framing stays wide.';list.append(text);}
  }
  if(showModeReview.kind==='storytelling' && showModeReview.story){
    const doc=showModeReview.story,notice=document.createElement('p');notice.className='hint';notice.textContent=doc.reference_guided?'First rehearsal: reference-guided, agent-reviewed plan. It is not a blind automatic-matching test.':'Local montage plan: review whether the chosen clips match the narration.';list.append(notice);
    doc.moments.forEach((moment,index)=>{const box=document.createElement('div');box.className='show-decision';const text=document.createElement('p');text.textContent=`${moment.start.toFixed(1)}–${moment.end.toFixed(1)}s · ${moment.original || moment.text || ''}`;const reason=document.createElement('small');reason.textContent=(moment.needs_review?'Needs review · ':'')+(moment.reason || '');const select=document.createElement('select');select.setAttribute('aria-label',`Clip for Story moment ${index+1}`);select.replaceChildren(...doc.catalogue.map(item=>new Option(item.shows || item.path.split('/').pop(),item.path)));select.value=moment.pictures[0]?.path;select.onchange=async()=>{try{const saved=await showPatch('/show/story/plan/'+index,{project_id:showModeReview.projectId,revision:showModeReview.story.revision || 0,path:select.value});showModeReview.story=saved.plan;$('#showProgramStatus').textContent='Story choice saved. Preview this part to update the video.';}catch(error){$('#showProgramStatus').textContent=error.message;}};box.append(text,select,reason);list.append(box);});
  }
  for(const event of [...events.items].reverse().slice(0,100)){const box=document.createElement('details');const title=document.createElement('summary');title.textContent=`${event.action} · ${event.method==='human'?'manual edit · unverified':event.method}`;const body=document.createElement('pre');body.textContent=JSON.stringify({at:event.at,before:event.before,after:event.after,evidence:event.evidence},null,2);box.append(title,body);list.append(box);}
  if(!list.children.length)list.textContent='No editorial corrections recorded yet.';$('#showDecisionsDialog').showModal();
}catch(error){$('#showProgramStatus').textContent=error.message;}};
$('#showDecisionsClose').onclick=()=>$('#showDecisionsDialog').close();
async function prepareShowProgramPreview(){
  const kind=showModeReview.kind,doc=kind==='podcast'?showModeReview.podcast:showModeReview.story;
  if(!['podcast','storytelling'].includes(kind) || !doc?.dirty)return;
  const route=kind==='podcast'?'podcast':'story';let job=await api(`/show/${route}/program-preview`,{project_id:showModeReview.projectId});
  while(job.status==='running'){$('#showProgramStatus').textContent=`Updating ${route} preview… ${job.progress || 0}%`;await new Promise(resolve=>setTimeout(resolve,700));job=await api(`/show/${route}/program-preview`);}
  if(job.status!=='ready')throw new Error(job.message || 'Could not update this preview');doc.dirty=false;await renderCutTimelines();$('#showProgramStatus').textContent='Camera/montage changes rendered.';
}
$('#showSceneVideo').addEventListener('timeupdate',drawShowCaptions);$('#showSceneVideo').addEventListener('loadedmetadata',drawShowCaptions);
document.addEventListener('montara:show-playback',()=>{drawShowCaptions();renderShowProgramTimeline();});

document.addEventListener("montara:show-scene",()=>{drawShowCaptions();renderShowProgramTimeline();});

$('#showSceneVideo').addEventListener('play',()=>{$('#showCaptionLayer').dataset.playing='true';});
$('#showSceneVideo').addEventListener('pause',()=>{$('#showCaptionLayer').dataset.playing='false';});

async function restoreShowModeSources(kind){
  if(kind==='podcast'){
    const data=await api('/show/podcast');showSources.podcast.people=data.people || [];showSources.podcast.cameras=data.cameras || [];
  }else if(kind==='storytelling'){
    const data=await api('/show/story');showSources.story.narration=data.narration?{path:data.narration,name:data.narration.split('/').pop()}:null;showSources.story.clips=(data.clips || []).map(path=>({path,name:path.split('/').pop()}));
  }
}

function resetShowSources(){showSources.podcast={people:[],cameras:[]};showSources.story={narration:null,clips:[]};}

$('#showPodcastPeople').addEventListener('click',e=>{const b=e.target.closest('[data-pod-remove]');if(b){showSources.podcast.people.splice(Number(b.dataset.podRemove),1);showEdit.resume=null;renderShowModeInputs();}});
for(const name of ['dragenter','dragover'])$('#showMicDrop').addEventListener(name,e=>{e.preventDefault();e.currentTarget.classList.add('over');});
for(const name of ['dragleave','drop'])$('#showMicDrop').addEventListener(name,async e=>{e.preventDefault();e.currentTarget.classList.remove('over');if(name!=='drop')return;try{const items=await uploadShowSupport([...e.dataTransfer.files]);showSources.podcast.people.push(...items.map(i=>({name:i.name.replace(/\.[^.]+$/,''),mic:i.path})));showEdit.resume=null;renderShowInput();}catch(error){toast(error.message,true);}});
