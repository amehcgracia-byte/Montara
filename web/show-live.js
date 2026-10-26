// Uses the original editor's ShowGeometry mouse grammar: crop, Ctrl stretch/rotate.
"use strict";
const showLive = {selected:null,drag:null,sceneId:null,nodes:new Map()};
function liveShape(item) {
  const p=item.params;
  if(item.type === "overlay")return {left:p.x,top:p.y,width:p.width,center:false};
  if(item.kind === "clip") {const scale=p.person_scale ?? 1,offset=p.person_offset || [0,0];return {left:((1-scale)/2+offset[0])*100,top:(1-scale+offset[1])*100,width:scale*100,center:false,video:true};}
  if(item.kind === "background")return {left:0,top:0,width:100,center:false,background:true};
  const center=p.image_center || (p.shown?p.shown.slice(0,2):[p.position?.endsWith('right') ? .79 : .21,p.position?.startsWith('top') ? .24 : p.position?.startsWith('bottom') ? .72 : .42]);
  return {left:center[0]*100,top:center[1]*100,width:(p.image_center ? (p.size || .3) : (p.shown?.[2] ?? p.size ?? .3))*100,center:true};
}
function placeLiveNode(node,item){
  const p=item.params,pos=liveShape(item);
  Object.assign(node.style,{left:pos.left+'%',top:pos.top+'%',width:pos.width+'%',transform:pos.center?'translate(-50%,-50%)':'none'});
  if(pos.video || pos.background)node.style.aspectRatio='16/9';
  const shape=node.querySelector('.show-live-shape');if(shape)shape.style.cssText=ShowGeometry.style(p);
  node.querySelector('.show-crop-frame')?.remove();node.insertAdjacentHTML('beforeend',ShowGeometry.handles(p));
  node.classList.toggle('selected',showLive.selected===item.id);
}
function drawShowPlacedEffects(){
  if(showLive.drag || $("#showReview").hidden)return;
  const scene=showEdit.scenes[showEdit.selected],layer=$("#showLiveLayer");if(!scene)return;
  if(showLive.sceneId!==scene.id){showLive.sceneId=scene.id;showLive.selected=null;}
  const at=scene.start+showPlaybackOffset(),rendered=showPlaybackState.mode==="rendered";
  layer.dataset.rendered=String(rendered);
  const visible=showSceneItems(scene).filter(item=>item.raw.status!=="discarded" && ["overlay","drawing","word","clip","background"].includes(item.kind) && !(item.raw.needs || []).length && (item.params.picture || item.params.asset || item.kind==='word' || item.kind==='clip') && (item.at<=at+.03 && at<item.at+Math.max(.1,item.duration || 1)));
  const ids=new Set(visible.map(i=>i.id));
  for(const [id,node] of showLive.nodes)if(!ids.has(id)){node.querySelector('video')?.pause();node.remove();showLive.nodes.delete(id);}
  for(const item of visible){
    let node=showLive.nodes.get(item.id);
    if(!node){
      node=document.createElement('div');node.className='show-live-effect';node.dataset.placedEffect=item.id;node.tabIndex=0;node.setAttribute('aria-label',`Select effect: ${showItemName(item)}`);
      const shape=document.createElement('div');shape.className='show-live-shape';
      if(item.kind==='word'){
        const text=document.createElement('span');text.className='show-live-word';text.textContent=item.params.text || '';text.style.color=item.params.colour || '#fff4d6';shape.append(text);
      }else if(item.kind==='clip'){
        const video=document.createElement('video');video.src=`/api/v1/show/clips/${encodeURIComponent(item.id)}/media`;video.muted=true;video.playsInline=true;video.preload='metadata';video.draggable=false;shape.append(video);showKeyedVideo(shape,video);
      }else{
        const image=document.createElement('img');image.src=`/api/v1/show/library/file?path=${encodeURIComponent(item.params.asset || item.params.picture)}`;image.alt='';image.draggable=false;shape.append(image);
      }
      const resize=document.createElement('span');resize.className='show-live-resize';resize.dataset.liveResize='true';resize.title='Drag to resize';
      const label=document.createElement('span');label.className='show-live-name';label.textContent=showItemName(item);
      node.append(shape,resize,label);layer.append(node);showLive.nodes.set(item.id,node);
      node.addEventListener('pointerdown',event=>startLiveDrag(event,item.id));
      node.addEventListener('contextmenu',event=>{event.preventDefault();event.stopPropagation();const current=showSceneItems(showEdit.scenes[showEdit.selected]).find(i=>i.id===item.id);if(current)showPlacedContextMenu(event,current);});
      node.addEventListener('dblclick',event=>{event.preventDefault();openShowInspector(item.id);});
      node.addEventListener('keydown',event=>{if(event.key==='Enter')openShowInspector(item.id);});
    }
    const label=node.querySelector('.show-live-word');if(label){label.textContent=item.params.text || '';label.style.color=item.params.colour || '#fff4d6';}
    const image=node.querySelector('img');if(image){const src=`/api/v1/show/library/file?path=${encodeURIComponent(item.params.asset || item.params.picture)}`;if(image.getAttribute('src')!==src)image.src=src;}
    placeLiveNode(node,item);
    const keyedShape=node.querySelector('.show-live-shape');keyedShape.dataset.matte=item.params.matte || "none";if(!rendered)keyedShape.drawKeyed?.();
    // A rendered preview already contains the composited effect. Hide the raw
    // editing layer explicitly: geometry sets an inline opacity of its own.
    if(rendered)node.querySelector('.show-live-shape').style.opacity='0';
    const video=node.querySelector('video');
    if(video && video.readyState>=1){
      const desired=Math.max(0,(item.params.clip_start || 0)+at-item.at);
      if(Math.abs(video.currentTime-desired)>.12 && desired<video.duration)video.currentTime=desired;
      // The narrator is the playback clock; live layers remain muted.
      if(!$("#showSceneVideo").paused && !rendered)video.play().catch(()=>{});else video.pause();
    }
  }
}
function activateShowLive(offset=showPlaybackOffset()){
  const scene=showEdit.scenes[showEdit.selected];if(!scene)return;
  showPlaybackState.liveEditing=true;showPlayback(scene,true,offset);
  $("#showPreviewStatus").textContent=document.body.dataset.showKind==='podcast'?'Drag subtitles on the picture, or right-click to change the camera. Preview when ready.':'Live edit: drag to move, corner to resize, edges to crop. Ctrl/⌘ + drag rotates; Ctrl/⌘ + edge stretches. Preview when ready.';
}
function selectShowPlacedEffect(id,locate=false){
  const scene=showEdit.scenes[showEdit.selected],item=showSceneItems(scene).find(i=>i.id===id);if(!item)return;
  showLive.selected=id;
  if(!["overlay","drawing","word","clip","background"].includes(item.kind)){openShowInspector(id);return;}
  const offset=locate?Math.max(0,item.at-scene.start+.04):showPlaybackOffset();
  activateShowLive(offset);drawShowPlacedEffects();
}
async function saveLivePlacement(item,changes){
  const scene=showEdit.scenes[showEdit.selected];
  if(item.type==='overlay')await saveShowOverlays(scene.id,scene.overlays.map(o=>o.id===item.id?{...o,...changes}:o));
  else await changeShowProposal(item,changes,scene.id);
  const offset=showPlaybackOffset();await refreshShowEditor(scene.id);seekShowTimeline(offset);drawShowPlacedEffects();
}
function startLiveDrag(event,id){
  if(event.button!==0 || showEditor.busy)return;
  event.preventDefault();event.stopPropagation();$("#showSceneVideo").pause();
  const scene=showEdit.scenes[showEdit.selected],item=showSceneItems(scene).find(i=>i.id===id),node=event.currentTarget;
  if(!item)return;
  showLive.selected=id;
  // Keep this node alive while switching the picture behind it to the source.
  const originalBox=node.getBoundingClientRect(),stage=$("#showLiveLayer").getBoundingClientRect();
  showLive.drag={item,node,initial:structuredClone(item.params),stage,box:originalBox,x:event.clientX,y:event.clientY,edge:event.target.closest('[data-crop-edge]')?.dataset.cropEdge,resize:!!event.target.closest('[data-live-resize]'),modified:event.ctrlKey || event.metaKey,angle:Math.atan2(event.clientY-originalBox.top-originalBox.height/2,event.clientX-originalBox.left-originalBox.width/2),changes:{}};
  node.setPointerCapture(event.pointerId);activateShowLive();
  $("#showLiveLayer").dataset.rendered='false';showLive.nodes.forEach((n,key)=>n.classList.toggle('selected',key===id));
}
document.addEventListener('pointermove',event=>{
  const drag=showLive.drag;if(!drag)return;
  const {item,initial,node,stage,box}=drag,dx=(event.clientX-drag.x)/stage.width,dy=(event.clientY-drag.y)/stage.height;
  if(Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<2)return;
  if(drag.edge || drag.modified){
    drag.changes=ShowGeometry.change(initial,drag.edge,(event.clientX-drag.x)/box.width,(event.clientY-drag.y)/box.height,drag.modified,drag.angle,Math.atan2(event.clientY-box.top-box.height/2,event.clientX-box.left-box.width/2));
  }else if(item.type==='overlay')drag.changes=drag.resize?{width:Math.max(1,initial.width+dx*100)}:{x:initial.x+dx*100,y:initial.y+dy*100};
  else if(item.kind==='clip')drag.changes=drag.resize?{person_scale:Math.max(.01,(initial.person_scale ?? 1)+dx*2)}:{person_offset:[(initial.person_offset?.[0] || 0)+dx,(initial.person_offset?.[1] || 0)+dy]};
  else {
    const pos=liveShape({...item,params:initial}),center=[pos.left/100,pos.top/100];
    drag.changes=drag.resize?{size:Math.max(.01,pos.width/100+dx*2),image_center:center}:{image_center:[center[0]+dx,center[1]+dy]};
  }
  placeLiveNode(node,{...item,params:{...initial,...drag.changes}});
});
document.addEventListener('pointerup',async()=>{
  const drag=showLive.drag;if(!drag)return;showLive.drag=null;
  if(!Object.keys(drag.changes).length){drawShowPlacedEffects();return;}
  showEditor.busy=true;
  try{await saveLivePlacement(drag.item,drag.changes);}catch(error){$("#showEditorStatus").textContent=error.message;drawShowPlacedEffects();}finally{showEditor.busy=false;}
});
document.addEventListener('pointercancel',()=>{showLive.drag=null;drawShowPlacedEffects();});
$("#showLiveEdit").addEventListener('click',()=>{activateShowLive();drawShowPlacedEffects();});
$("#showSceneVideo").addEventListener('timeupdate',drawShowPlacedEffects);
$("#showSceneVideo").addEventListener('loadedmetadata',drawShowPlacedEffects);
document.addEventListener('montara:show-playback',()=>{drawShowPlacedEffects();});
function clearShowSelection(){
  showLive.selected=null;
  $("#showPlacedMenu").hidden=true;
  showLive.nodes.forEach(node=>node.classList.remove('selected'));
  drawShowPlacedEffects();
}
document.addEventListener('pointerdown',event=>{
  if(!event.target.closest('#showPlacedMenu'))$("#showPlacedMenu").hidden=true;
  if(!event.target.closest('.show-live-effect, #showPlacedMenu, #showInspector, #showEffectDialog'))clearShowSelection();
});
$("#showSceneVideo").addEventListener('play',()=>{clearShowSelection();$("#showLiveLayer").dataset.playing='true';});
$("#showSceneVideo").addEventListener('pause',()=>{$("#showLiveLayer").dataset.playing='false';});
$("#showPreviewPart").addEventListener('click',clearShowSelection);
function showPlacedContextMenu(event,item){
  event.preventDefault();event.stopPropagation();showLive.selected=item.id;$("#showSceneVideo").pause();$("#showContextMenu").hidden=true;
  const menu=$("#showPlacedMenu");menu.replaceChildren();
  const action=(name,fn)=>{const button=document.createElement('button');button.type='button';button.setAttribute('role','menuitem');button.textContent=name;button.addEventListener('click',()=>{menu.hidden=true;fn();});menu.append(button);};
  action('Edit effect',()=>{openShowInspector(item.id);if(['overlay','drawing','clip','background'].includes(item.kind))$("#showInspectorMedia").click();});
  action('Timing / movement settings',()=>openShowInspector(item.id));
  action('Move / crop on video',()=>selectShowPlacedEffect(item.id,true));
  action('Preview this effect',()=>{openShowInspector(item.id);$("#showInspectorForm").requestSubmit($("#showInspectorPreview"));});
  action('Add another effect here',()=>openShowEffectTools('media'));
  action('Remove effect',()=>{openShowInspector(item.id);$("#showInspectorDelete").click();});
  menu.hidden=false;menu.style.left=Math.max(8,Math.min(event.clientX,window.innerWidth-menu.offsetWidth-8))+'px';menu.style.top=Math.max(8,Math.min(event.clientY,window.innerHeight-menu.offsetHeight-8))+'px';menu.querySelector('button').focus();
}
$("#showLivePlay").addEventListener('click',()=>compactTogglePlayback());
