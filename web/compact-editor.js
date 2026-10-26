// Shared compact controls. Editing never waits for a render or a media probe.
let showAutoTimer=null,showAutoGeneration=0;
function cancelShowAutoPreview(){clearTimeout(showAutoTimer);showAutoGeneration++;clearTimeout(showEdit.previewTimer);showEdit.previewToken++;}
function compactAddMenu(event){
  document.querySelector('.cut-context')?.remove();const menu=document.createElement('div');menu.className='cut-context';menu.setAttribute('role','menu');
  for(const [label,run] of [['Effect',()=>$('#showOpenEffects').click()],['Music',()=>$('#showMusicOpen').click()],['Video / image',()=>openShowEffectTools('media')]]){const button=document.createElement('button');button.type='button';button.setAttribute('role','menuitem');button.textContent=label;button.onclick=()=>{menu.remove();run();};menu.append(button);}
  document.body.append(menu);menu.style.left=Math.min(event.clientX,innerWidth-menu.offsetWidth-8)+'px';menu.style.top=Math.min(event.clientY,innerHeight-menu.offsetHeight-8)+'px';
  const close=e=>{if(!menu.contains(e.target)){menu.remove();document.removeEventListener('pointerdown',close,true);}};document.addEventListener('pointerdown',close,true);
}
function scheduleShowAutoPreview(){
  cancelShowAutoPreview();const generation=showAutoGeneration,project=state.projectId,scene=showEdit.scenes[showEdit.selected];if(!scene||$('#showReview').hidden)return;
  $('#showPreviewStatus').textContent='Updating preview…';
  const run=async()=>{
    if(generation!==showAutoGeneration||state.projectId!==project||$('#showReview').hidden)return;
    if(showEditor.busy||cutBusy||showLive.drag||document.querySelector('#showInspector[open],#showEffectDialog[open],#showCameraDialog[open]')){showAutoTimer=setTimeout(run,350);return;}
    try{
      await prepareShowProgramPreview();if(generation!==showAutoGeneration)return;
      await api(`/show/scenes/${encodeURIComponent(scene.id)}/preview`,{next:[]});
      const started=Date.now();
      while(generation===showAutoGeneration && state.projectId===project){
        const data=await api('/show/scenes'),fresh=data.scenes?.find(s=>s.id===scene.id);
        if(!fresh)return;
        if(fresh.preview?.status==='ready'){
          const active=showEdit.scenes.find(s=>s.id===scene.id);if(active)active.preview=fresh.preview;showPlaybackState.cache.set(project+'|'+scene.id,fresh.preview);
          if(showEdit.scenes[showEdit.selected]?.id===scene.id){const video=$('#showSceneVideo'),offset=showPlaybackOffset();if(video.paused&&!showLive.selected){showPlaybackState.liveEditing=false;showPlayback(active,false,offset);}$('#showPreviewStatus').textContent='Preview updated';}
          return;
        }
        if(fresh.preview?.status==='failed')throw new Error(fresh.preview.error||'Preview could not update.');
        if(Date.now()-started>120000)throw new Error('Preview is still processing; you can keep editing.');
        await new Promise(resolve=>setTimeout(resolve,1200));
      }
    }catch(error){if(generation===showAutoGeneration)$('#showPreviewStatus').textContent=error.message;}
  };
  showAutoTimer=setTimeout(run,750);
}
function updateLiveFraming(){
  const video=$('#showSceneVideo');if(showPlaybackState.mode==='rendered'||['podcast','storytelling'].includes(showModeReview.kind)){video.style.transform='';return;}
  const at=(showEdit.scenes[showEdit.selected]?.start||0)+showPlaybackOffset(),shot=showEdit.narratorCache?.shots?.find(s=>s.at<=at&&at<s.at+s.duration);
  if(!shot){video.style.transform='';return;}const share=Math.min(1,Math.max(0,(at-shot.at)/shot.duration));const z=shot.zoom+(shot.zoom_end==null?0:(shot.zoom_end-shot.zoom)*share);
  video.style.transform=`scale(${z})`;video.style.transformOrigin=`${(shot.focus?.[0]??.5)*100}% ${(shot.focus?.[1]??.5)*100}%`;
}
const liveMusicNodes=new Map();
function updateLiveMusic(){
  const video=$('#showSceneVideo'),scene=showEdit.scenes[showEdit.selected];if(!scene)return;
  const at=scene.start+showPlaybackOffset(),items=showSceneItems(scene).filter(i=>i.kind==='jingle'&&i.raw.status!=='discarded'&&i.at<=at&&at<i.at+i.duration),active=new Set();
  if(showPlaybackState.mode!=='rendered')for(const item of items){
    active.add(item.id);let audio=liveMusicNodes.get(item.id);if(!audio){audio=new Audio(`/montara/show/editor/audio/${encodeURIComponent(item.id)}`);audio.preload='metadata';liveMusicNodes.set(item.id,audio);}
    audio.volume=Math.max(0,Math.min(1,(item.params.volume??.28)*video.volume));audio.muted=video.muted;
    const t=(item.params.start||0)+at-item.at;if(Number.isFinite(audio.duration)&&Math.abs(audio.currentTime-t)>.2)audio.currentTime=t;
    if(video.paused)audio.pause();else audio.play().catch(()=>{});
  }
  for(const [id,audio] of liveMusicNodes)if(!active.has(id)||showPlaybackState.mode==='rendered')audio.pause();
}
for(const event of ['timeupdate','loadedmetadata','seeking','play','pause','volumechange'])$('#showSceneVideo').addEventListener(event,()=>{updateLiveFraming();updateLiveMusic();const play=$('#showLivePlay');play.textContent=$('#showSceneVideo').paused?'▶':'❚❚';play.setAttribute('aria-label',$('#showSceneVideo').paused?'Play':'Pause');});
$('#showPlaybackVolume').oninput=()=>{$('#showSceneVideo').volume=Number($('#showPlaybackVolume').value);};
$('#showMute').onclick=()=>{const video=$('#showSceneVideo');video.muted=!video.muted;$('#showMute').textContent=video.muted?'×':'♪';$('#showMute').setAttribute('aria-label',video.muted?'Unmute':'Mute');};
$('#showSceneVideo').addEventListener('contextmenu',()=>{
  const menu=$('#showContextEdits'),button=document.createElement('button');button.type='button';button.setAttribute('role','menuitem');button.textContent='Remove effects from this part';button.onclick=()=>{$('#showContextMenu').hidden=true;clearShowSceneEffects(showEdit.scenes[showEdit.selected]).catch(error=>$('#showPreviewStatus').textContent=error.message);};menu.append(button);
});
// Use the same compact transport in Stage camera previews, assets and output.
function compactMedia(video){
  if(video.id==='showSceneVideo'||!video.controls||video.dataset.compact)return;video.dataset.compact='true';video.controls=false;
  const bar=document.createElement('div');bar.className='editor-transport compact-media';const play=document.createElement('button');play.className='icon-btn';play.type='button';play.textContent='▶';play.setAttribute('aria-label','Play preview');
  play.onclick=()=>video.paused?video.play().catch(()=>{}):video.pause();const seek=document.createElement('input');seek.type='range';seek.min=0;seek.max=100;seek.step=.1;seek.value=0;seek.setAttribute('aria-label','Preview position');seek.oninput=()=>{if(Number.isFinite(video.duration))video.currentTime=video.duration*Number(seek.value)/100;};
  const volume=document.createElement('input');volume.type='range';volume.min=0;volume.max=1;volume.step=.01;volume.value=video.volume;volume.setAttribute('aria-label','Preview volume');volume.oninput=()=>video.volume=Number(volume.value);
  bar.append(play,seek,volume);video.after(bar);video.addEventListener('timeupdate',()=>{seek.value=Number.isFinite(video.duration)?video.currentTime/video.duration*100:0;});video.addEventListener('play',()=>play.textContent='❚❚');video.addEventListener('pause',()=>play.textContent='▶');
}
document.querySelectorAll('video[controls]').forEach(compactMedia);new MutationObserver(records=>{for(const record of records)for(const node of record.addedNodes)if(node instanceof Element){if(node.matches('video[controls]'))compactMedia(node);node.querySelectorAll('video[controls]').forEach(compactMedia);}}).observe(document.body,{childList:true,subtree:true});
const capPlay=$('#capPlay');if(capPlay){const volume=document.createElement('input');volume.type='range';volume.min=0;volume.max=1;volume.step=.01;volume.value=1;volume.setAttribute('aria-label','Reel playback volume');volume.oninput=()=>$('#capVideo').volume=Number(volume.value);capPlay.parentElement.append(volume);}

document.addEventListener('montara:edit-saved',scheduleShowAutoPreview);
function compactTogglePlayback(){
  const video=$('#showSceneVideo'),scene=showEdit.scenes[showEdit.selected];if(!video.paused){video.pause();return;}
  const ready=scene?.preview?.status==='ready';
  if(ready&&showPlaybackState.mode!=='rendered'){
    const offset=showPlaybackOffset();showPlaybackState.liveEditing=false;showPlayback(scene,false,offset);
    if(video.readyState>=1)video.play().catch(()=>{});else video.addEventListener('loadedmetadata',()=>video.play().catch(()=>{}),{once:true});
  }else video.play().catch(error=>$('#showPreviewStatus').textContent=error.message);
}
