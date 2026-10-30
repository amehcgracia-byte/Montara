'use strict';
const packUI={doc:null,selected:'1',timer:null,busy:false,dirty:false,signature:'',range:null,inputKey:'',pending:Promise.resolve()};
const packOption=document.createElement('div');packOption.id='pushPackOption';packOption.hidden=true;
packOption.innerHTML='<label class="opt pack-option"><input id="pushPackOn" type="checkbox"><span><b>4 reels from one video</b><small>One internet link or one uploaded music video.</small></span></label><div id="pushPackLink" hidden><label>Video link<input id="pushPackURL" type="url" placeholder="https://…" autocomplete="off"></label><p class="hint">Paste a public video link, or drop one video below. Each reel stays editable.</p><button id="pushPackExample" type="button" class="link">Use the included internet example</button><p id="pushPackInputStatus" class="hint" role="status"></p><button id="pushPackResume" type="button" class="btn ghost small" hidden>Resume saved reel pack</button></div>';
const nativeVideoDrop=$('[data-drop="video"]');nativeVideoDrop.before(packOption);
const packScreen=document.createElement('section');packScreen.id='pushPack';packScreen.className='screen';packScreen.hidden=true;
packScreen.innerHTML='<p class="eyebrow">PUSH · FOUR REELS</p><h2>One video. Four reels.</h2><p id="packStatus" class="lead small" role="status"></p><div id="packReview" hidden><div class="show-review-layout"><div><div class="show-player pack-player" id="packPlayer"><canvas id="packBackground" aria-hidden="true" width="160" height="90" hidden></canvas><video id="packVideo" controls playsinline preload="metadata"></video><div class="pack-caption-layer"><span id="packCaption" class="show-preview-caption"></span></div></div><div class="actions"><button id="packPlay" class="btn ghost small" type="button">Play this reel</button><button id="packAdjustFrame" class="btn ghost small" type="button">Adjust frame</button><span id="packNow" class="hint"></span></div></div><div><label>Layout<select id="packLayout"><option value="9:16">Vertical</option><option value="16:9">Horizontal</option><option value="mix">Mix</option><option value="mix_vertical_horizontal">Mix alternate</option></select></label><label id="packMixShareRow" hidden>Vertical / horizontal<select id="packMixShare"><option value="auto">Automatic</option><option value="0.75">75% vertical · 25% horizontal</option><option value="0.5">50% vertical · 50% horizontal</option><option value="0.25">25% vertical · 75% horizontal</option></select></label><div id="packChoices" class="pack-choices"></div><p class="hint">Select a reel to review it. Tick the reels you want to export.</p><p class="hint">Move the edges on the timeline. Right-click a reel to adjust its frame.</p></div></div><div id="packTimeline" class="show-editor-timeline"></div><p class="hint">Drag a region to move it; drag either edge to trim. No render runs while you edit.</p><div id="packCaptionEditor"><div class="actions"><label><input id="packCaptionsOn" type="checkbox"> Captions on this reel</label><label>Style<select id="packCaptionStyle"><option value="clean">Clean</option><option value="bold">Bold</option><option value="glow">Yellow glow</option><option value="words">Word by word</option></select></label><button id="packSyncWords" class="btn ghost small" type="button">Sync words to voice</button><button id="packUseDetected" class="btn ghost small" type="button" hidden>Replace with detected lyrics</button><button id="packReadLyrics" class="btn ghost small" type="button">Read lyrics again</button></div><p id="packLyricsStatus" class="hint" role="status"></p><div id="packCues"></div><div class="actions"><button id="packAddCue" class="btn ghost small" type="button">Add caption</button><button id="packSaveCaptions" class="btn ghost small" type="button">Save captions</button></div></div><div class="actions"><button id="packExport" class="btn primary" type="button">Export selected reels</button></div><div id="packDownloads" aria-live="polite"></div></div><div class="actions"><button id="packBack" class="btn ghost" type="button">Back to video</button><p id="packError" class="hint" role="status"></p></div>';
$('main').append(packScreen);
const packLoading=document.createElement('div');packLoading.id='packLoading';packLoading.className='pack-loading is-indeterminate';
const packRing=$('#making .ring').cloneNode(true);packRing.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));packRing.querySelector('b').textContent='';packLoading.append(packRing);$('#packReview').before(packLoading);
function paintPackLoading(doc){packLoading.hidden=doc.status!=='preparing';if(packLoading.hidden)return;const known=Number.isFinite(doc.progress);packLoading.classList.toggle('is-indeterminate',!known);packRing.querySelector('.bar').style.strokeDashoffset=known?326.7*(1-doc.progress/100):245;packRing.querySelector('b').textContent=known?Math.round(doc.progress)+'%':'';packLoading.setAttribute('aria-label',doc.message);}
function packFramedAt(reel,position){const span=reel.layout_segments?.find(s=>s.start<=position&&position<s.end);if(span)return span.layout==='horizontal';return packUI.doc.format==='16:9'||packUI.doc.format==='mix_vertical_horizontal'&&Number(reel.id)%2===0;}
function applyPackView(reel,position){const video=$('#packVideo'),framed=packFramedAt(reel,position),frame=reel.framing||{x:.5,y:.5,zoom:1};const key=[reel.id,reel.revision,framed,frame.x,frame.y,frame.zoom].join('|');if(video.dataset.view===key)return;video.dataset.view=key;$('#packPlayer').style.aspectRatio='9 / 16';$('#packPlayer').style.maxWidth='360px';video.style.objectFit=framed?'contain':'cover';video.style.objectPosition=`${frame.x*100}% ${frame.y*100}%`;video.style.transformOrigin=`${frame.x*100}% ${frame.y*100}%`;video.style.transform=`scale(${frame.zoom})`;$('#packBackground').hidden=!framed;}

const packEnabled=()=>state.platform==='reel' && $('#pushPackOn').checked;
const packApi=(path,body,method)=>{
  const options=body===undefined?{}:{method:method || 'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
  return fetch('/montara/push/packs'+path,options).then(async response=>{const data=await response.json();if(!response.ok)throw new Error(data.error?.message || 'Could not update this reel pack.');return data;});
};
function packInput(){
  packOption.hidden=state.platform!=='reel';const on=packEnabled();$('#pushPackLink').hidden=!on;$('#pushPackResume').hidden=!sessionStorage.getItem('montara-push-pack');
  if(on && state.files.length && state.files.every(f=>f.sample)){const next=$('#pushPackURL').value.trim()?[]:[videos()[0]].filter(Boolean);if(state.files.length!==next.length){state.files=next;$('#sampleNote').hidden=!next.length;packNativeFiles();}}
  $('[data-drop="audio"]').closest('.box').hidden=on;$('#footage .branding').hidden=on;
  nativeVideoDrop.querySelector('strong').textContent=on?'Drop one music video':'Drop your videos';
  nativeVideoDrop.querySelector('span').textContent=on?'One video, with the song in its audio track.':'Every camera of the performance: phone, camera, 360. They don’t need to start together.';
  if(on){const ready=!!$('#pushPackURL').value.trim() || videos().length===1;$('#continueFootage').disabled=state.uploads>0 || !ready;$('#pushPackInputStatus').textContent=state.uploads?'Uploading your video…':videos().length>1?'Choose a single video for the four-reel pack.':'';}
}
const packNativeFiles=renderFiles;renderFiles=function(){packNativeFiles();packInput();};
const packNativeShow=show;show=function(id){if(id!=='pushPack'){$('#packVideo').pause();clearTimeout(packUI.timer);}packNativeShow(id);packInput();};
const packNativeAdd=addFiles;addFiles=function(files,handles){if(packEnabled()){if(rejectRaw360(files))return;if(files.length!==1 || !files[0].type.startsWith('video/'))return toast('Choose one music video for this pack.',true);$('#pushPackURL').value='';state.files=[];$('#sampleNote').hidden=true;packUI.doc=null;}packNativeAdd(files,handles);};
$('#pushPackOn').onchange=()=>{if(packEnabled() && state.files.every(f=>f.sample)){const first=videos()[0];state.files=first?[first]:[];}renderFiles();if(!packEnabled() && !state.files.length)loadSamples().catch(console.warn);};
$('#pushPackURL').oninput=()=>{packUI.doc=null;renderFiles();};
const packNativeRegister=registerProject;
registerProject=async function(){
  if(!packEnabled())return packNativeRegister();
  const url=$('#pushPackURL').value.trim();if(!url && videos().length!==1)return toast('Choose one video or paste one link.',true);
  const inputKey=JSON.stringify([url || videos()[0].path,$('#reelDuration').value,reelFormat(),$('#mixShare').value]);
  if(packUI.doc && packUI.doc.status!=='failed' && packUI.inputKey===inputKey){show('pushPack');renderPack();pollPack();return;}
  show('pushPack');paintPackLoading({status:'preparing',progress:null,message:'Preparing your four reels…'});$('#packStatus').textContent='Preparing your four reels…';$('#packError').textContent='';$('#packReview').hidden=true;
  try{packUI.doc=await packApi('',{...(url?{url}:{source:videos()[0].path}),length:Number($('#reelDuration').value),format:reelFormat(),mix_vertical_ratio:$('#mixShare').value});packUI.inputKey=inputKey;sessionStorage.setItem('montara-push-pack',JSON.stringify({id:packUI.doc.id,url,source:url?'':videos()[0].path,name:videos()[0]?.name || 'Music video'}));packUI.selected='1';packUI.signature='';packUI.dirty=false;renderPack();pollPack();}
  catch(error){packLoading.hidden=true;$('#packError').textContent=error.message;$('#packStatus').textContent='Your video could not be prepared. Go back and try another link or file.';}
};
function selectedPackReel(){return packUI.doc?.reels.find(reel=>reel.id===packUI.selected);}
function patchPackReel(id,changes){
  const task=async()=>{
    packUI.busy=true;$('#packError').textContent='';
    try{const reel=packUI.doc.reels.find(r=>r.id===id);packUI.doc=await packApi('/'+packUI.doc.id+'/reels/'+id,{revision:reel.revision,...changes},'PATCH');packUI.signature='';renderPack();}
    catch(error){$('#packError').textContent=error.message;throw error;}finally{packUI.busy=false;}
  };
  const result=packUI.pending.then(task,task);packUI.pending=result.catch(()=>{});return result;
}
function renderPack(){
  const doc=packUI.doc;if(!doc || $('#pushPack').hidden)return;
  $('#packStatus').textContent=doc.status==='ready'?doc.title+(doc.cached_source?' · included original, processed into four editable reels.':' · four suggested moments. Check the cuts and lyrics.'):doc.message;
  paintPackLoading(doc);
  $('#packReview').hidden=doc.status!=='ready';if(doc.status!=='ready')return;
  $('#packLyricsStatus').textContent=[selectedPackReel()?.lyrics_message || doc.captions_message,selectedPackReel()?.alignment_message].filter(Boolean).join(' · ');
  $('#packSyncWords').disabled=selectedPackReel()?.alignment_status==='running'||selectedPackReel()?.lyrics_status==='running';
  $('#packSaveCaptions').disabled=selectedPackReel()?.alignment_status==='running'||selectedPackReel()?.lyrics_status==='running';
  $('#packReadLyrics').disabled=doc.captions_status==='running'||selectedPackReel()?.lyrics_status==='running';
  $('#packMixShareRow').hidden=doc.format!=='mix';$('#packMixShare').value=String(doc.mix_vertical_ratio??.5);
  $('#packLayout').value=doc.format;$('#packLayout').disabled=doc.reels.some(r=>['running','queued'].includes(r.render.status));
  $('#packUseDetected').hidden=!selectedPackReel()?.captions_edited || doc.captions_status!=='ready';
  const selected=selectedPackReel();
  $('#packChoices').innerHTML=doc.reels.map(r=>`<div class="pack-choice"><label><input type="checkbox" data-pack-export="${r.id}" ${r.selected?'checked':''} ${['running','queued'].includes(r.render.status)?'disabled':''}> Export</label><button class="btn ghost small ${r.id===packUI.selected?'on':''}" data-pack-select="${r.id}" type="button">Reel ${r.id}</button></div>`).join('');
  $('#packDownloads').innerHTML=doc.reels.map(r=>`<p>Reel ${r.id} · ${r.render.status==='ready'?`<a class="link" href="${r.render.url}">Download reel ${r.id}</a>`:r.render.status==='failed'?escapeHtml(r.render.message):r.render.status==='running'?'Rendering…':r.render.status==='queued'?'Waiting to render…':'Not exported'}</p>`).join('');
  if(doc.reels.some(r=>r.render.status==='ready')){const note=document.createElement('p');note.className='hint publication-note';note.textContent='Before publishing, make sure you have permission to use the music, images, video and people featured. You are responsible for what you publish.';$('#packDownloads').append(note);}
  $('#packExport').disabled=!doc.reels.some(r=>r.selected)||doc.reels.some(r=>['running','queued'].includes(r.render.status));
  const signature=selected.id+'|'+selected.revision+'|'+doc.captions_status+'|'+doc.format;
  if(packUI.dirty || packUI.range || signature===packUI.signature)return;
  packUI.signature=signature;
  $('#packCaptionsOn').checked=selected.captions_on;$('#packCaptionStyle').value=selected.caption_style;
  renderPackCues(selected.captions);
  const video=$('#packVideo');if(video.getAttribute('src')!==doc.source_url){video.src=doc.source_url;video.onloadedmetadata=()=>{video.currentTime=selectedPackReel().start;};}else if(video.currentTime<selected.start || video.currentTime>selected.end)video.currentTime=selected.start;
  applyPackView(selected,Math.max(0,video.currentTime-selected.start));
  renderPackTimeline();paintPackCaption();
}
function renderPackCues(cues){
  const length=selectedPackReel().end-selectedPackReel().start;
  $('#packCues').innerHTML=cues.map((c,i)=>`<div class="pack-cue"><input type="hidden" data-cue-start value="${c.start}"><input type="hidden" data-cue-end value="${c.end}"><label>Lyrics ${i+1}<textarea data-cue-text rows="2">${escapeHtml(c.text)}</textarea></label><button class="btn ghost small" type="button" data-cue-remove aria-label="Remove caption">×</button><div class="pack-cue-bed" aria-label="Caption position within this reel"><button class="pack-cue-bar" type="button" style="left:${c.start/length*100}%;width:${(c.end-c.start)/length*100}%" aria-label="Move caption ${i+1}"><i data-cue-edge="start" role="slider" tabindex="0" aria-label="Caption ${i+1} start" aria-valuemin="0" aria-valuemax="${length}" aria-valuenow="${c.start}"></i><span>${escapeHtml(c.text || 'New caption')}</span><i data-cue-edge="end" role="slider" tabindex="0" aria-label="Caption ${i+1} end" aria-valuemin="0" aria-valuemax="${length}" aria-valuenow="${c.end}"></i></button></div></div>`).join('');
  $$('#packCues .pack-cue').forEach(row=>{
    const bar=row.querySelector('.pack-cue-bar'),start=row.querySelector('[data-cue-start]'),end=row.querySelector('[data-cue-end]');let drag=null;
    const update=(a,b)=>{start.value=a;end.value=b;bar.style.left=a/length*100+'%';bar.style.width=(b-a)/length*100+'%';bar.querySelector('[data-cue-edge=start]').setAttribute('aria-valuenow',a);bar.querySelector('[data-cue-edge=end]').setAttribute('aria-valuenow',b);packUI.dirty=true;};
    bar.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();$('#packVideo').pause();drag={x:e.clientX,a:Number(start.value),b:Number(end.value),edge:e.target.dataset.cueEdge,width:bar.parentElement.getBoundingClientRect().width};bar.setPointerCapture(e.pointerId);};
    bar.onpointermove=e=>{if(!drag)return;const delta=(e.clientX-drag.x)/drag.width*length;let a=drag.a,b=drag.b;if(drag.edge==='start')a=Math.max(0,Math.min(b-.06,a+delta));else if(drag.edge==='end')b=Math.min(length,Math.max(a+.06,b+delta));else{a=Math.max(0,Math.min(length-(b-a),a+delta));b=a+drag.b-drag.a;}update(a,b);};
    bar.onpointerup=bar.onpointercancel=()=>{drag=null;};
    bar.querySelectorAll('[data-cue-edge]').forEach(handle=>handle.onkeydown=e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const delta=(e.key==='ArrowRight'?1:-1)*.04;let a=Number(start.value),b=Number(end.value);if(handle.dataset.cueEdge==='start')a=Math.max(0,Math.min(b-.06,a+delta));else b=Math.min(length,Math.max(a+.06,b+delta));update(a,b);});
    bar.onclick=()=>{$('#packVideo').pause();$('#packVideo').currentTime=selectedPackReel().start+Number(start.value);};
  });
}
function renderPackTimeline(){
  const doc=packUI.doc,host=$('#packTimeline');host.innerHTML=`<div class="show-timeline-heading"><h3>Your four reels · original video</h3><output>${doc.duration.toFixed(1)}s</output></div><div class="show-timeline-ruler"><span>0s</span><span>${(doc.duration/2).toFixed(1)}s</span><span>${doc.duration.toFixed(1)}s</span></div>${doc.reels.map(r=>`<div class="show-track"><span>Reel ${r.id}</span><div class="show-track-bed" data-pack-bed="${r.id}"><button class="show-effect-bar" data-pack-region="${r.id}" type="button" style="left:${r.start/doc.duration*100}%;width:${(r.end-r.start)/doc.duration*100}%" aria-label="Move reel ${r.id}"><i data-pack-edge="left" role="slider" tabindex="0" aria-label="Start of reel ${r.id}" aria-valuemin="0" aria-valuemax="${doc.duration}" aria-valuenow="${r.start}"></i><b>Reel ${r.id}</b><i data-pack-edge="right" role="slider" tabindex="0" aria-label="End of reel ${r.id}" aria-valuemin="0" aria-valuemax="${doc.duration}" aria-valuenow="${r.end}"></i></button></div></div>`).join('')}`;
  host.querySelectorAll('[data-pack-region]').forEach(bar=>{
    const reel=doc.reels.find(r=>r.id===bar.dataset.packRegion);let moved=false;bar.oncontextmenu=event=>openPackMenu(event,reel.id);
    bar.onpointerdown=event=>{if(event.button!==0||packUI.busy||['queued','running'].includes(reel.render.status))return;if(packUI.dirty){event.preventDefault();toast('Save your captions before moving this cut.',true);return;}event.preventDefault();$('#packVideo').pause();moved=false;packUI.range={id:reel.id,x:event.clientX,start:reel.start,end:reel.end,edge:event.target.dataset.packEdge,width:bar.parentElement.getBoundingClientRect().width};bar.setPointerCapture(event.pointerId);};
    bar.onpointermove=event=>{const drag=packUI.range;if(!drag||drag.id!==reel.id)return;const delta=(event.clientX-drag.x)/drag.width*doc.duration;if(Math.abs(event.clientX-drag.x)>3)moved=true;let start=drag.start,end=drag.end;if(drag.edge==='left')start=Math.max(0,Math.min(end-1,Math.max(end-90,start+delta)));else if(drag.edge==='right')end=Math.max(start+1,Math.min(doc.duration,Math.min(start+90,end+delta)));else{start=Math.max(0,Math.min(doc.duration-(end-start),start+delta));end=start+drag.end-drag.start;}drag.next={start:Math.round(start*25)/25,end:Math.round(end*25)/25};bar.style.left=start/doc.duration*100+'%';bar.style.width=(end-start)/doc.duration*100+'%';bar.title=start.toFixed(2)+'–'+end.toFixed(2)+'s';};
    bar.onpointerup=async()=>{const next=packUI.range?.next;packUI.range=null;if(next&&moved){packUI.dirty=false;await patchPackReel(reel.id,next).catch(()=>renderPackTimeline());}};
    bar.onpointercancel=()=>{packUI.range=null;renderPackTimeline();};bar.onclick=()=>{if(!moved)selectPackReel(reel.id);};
    bar.querySelectorAll('[data-pack-edge]').forEach(handle=>handle.onkeydown=async event=>{if(!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();const key=handle.dataset.packEdge==='left'?'start':'end';await patchPackReel(reel.id,{[key]:Math.round((reel[key]+(event.key==='ArrowRight'?1:-1)*(event.shiftKey?.5:.04))*100)/100}).catch(()=>{});});
  });
}
function selectPackReel(id){if(packUI.dirty){toast('Save your caption changes before switching reels.',true);return;}$('#packVideo').pause();packUI.selected=id;packUI.signature='';renderPack();$('#packVideo').currentTime=selectedPackReel().start;}
async function pollPack(){
  clearTimeout(packUI.timer);if(!packUI.doc||$('#pushPack').hidden)return;
  try{if(!packUI.busy){packUI.doc=await packApi('/'+packUI.doc.id);if(packUI.networkError){$('#packError').textContent='';packUI.networkError=false;}renderPack();}}
  catch(error){packUI.networkError=true;$('#packError').textContent='Reconnecting… Your saved reels are preserved.';}
  if(!$('#pushPack').hidden)packUI.timer=setTimeout(pollPack,1000);
}
function paintPackCaption(){
  const reel=selectedPackReel();if(!reel)return;const video=$('#packVideo'),time=video.currentTime-reel.start,caption=$('#packCaption');$('#packNow').textContent=`Reel ${reel.id} · ${Math.max(0,time).toFixed(1)} / ${(reel.end-reel.start).toFixed(1)}s`;
  applyPackView(reel,Math.max(0,time));
  const cue=reel.captions_on?reel.captions.find(c=>c.start<=time&&time<c.end):null;let text=cue?.text || '';
  if(cue&&reel.caption_style==='words'){const word=cue.words?.find(w=>w.start<=time&&time<w.end);text=cue.words?.length?(word?.text || ''):cue.text;}
  caption.textContent=text;caption.dataset.style=reel.caption_style;
  const bg=$('#packBackground');if(!bg.hidden&&video.readyState>=2)bg.getContext('2d').drawImage(video,0,0,160,90);
}
$('#packVideo').ontimeupdate=()=>{const reel=selectedPackReel();if(!reel)return;if($('#packVideo').currentTime>=reel.end && !$('#packVideo').paused){$('#packVideo').pause();$('#packVideo').currentTime=reel.end;}paintPackCaption();};
$('#packVideo').onplay=()=>{const reel=selectedPackReel(),video=$('#packVideo');if(reel&&(video.currentTime<reel.start || video.currentTime>=reel.end-.05))video.currentTime=reel.start;};
$('#packPlay').onclick=()=>{const video=$('#packVideo');if(video.paused)video.play().catch(error=>{$('#packError').textContent=error.message;});else video.pause();};
$('#packChoices').onclick=event=>{const button=event.target.closest('[data-pack-select]');if(button)selectPackReel(button.dataset.packSelect);};
$('#packChoices').onchange=event=>{if(event.target.dataset.packExport)patchPackReel(event.target.dataset.packExport,{selected:event.target.checked}).catch(()=>{});};
$('#packCaptionEditor').oninput=event=>{if(event.target.id!=='packReadLyrics')packUI.dirty=true;};
$('#packCues').onclick=event=>{if(event.target.closest('[data-cue-remove]')){event.target.closest('.pack-cue').remove();packUI.dirty=true;}};
$('#packAddCue').onclick=()=>{const cues=$$('#packCues .pack-cue').map(row=>({start:Number(row.querySelector('[data-cue-start]').value),end:Number(row.querySelector('[data-cue-end]').value),text:row.querySelector('textarea').value}));const start=Math.min(selectedPackReel().end-selectedPackReel().start-1,cues.at(-1)?.end || 0);cues.push({start:Math.max(0,start),end:Math.min(selectedPackReel().end-selectedPackReel().start,start+2),text:''});renderPackCues(cues);packUI.dirty=true;};
$('#packSaveCaptions').onclick=async()=>{const changes={captions_on:$('#packCaptionsOn').checked,caption_style:$('#packCaptionStyle').value,captions:$$('#packCues .pack-cue').map(row=>({start:Number(row.querySelector('[data-cue-start]').value),end:Number(row.querySelector('[data-cue-end]').value),text:row.querySelector('textarea').value}))};try{await patchPackReel(packUI.selected,changes);packUI.dirty=false;packUI.signature='';renderPack();toast('Captions saved.');}catch{}};
$('#packReadLyrics').onclick=async()=>{try{await packUI.pending;packUI.doc=await packApi('/'+packUI.doc.id+'/reels/'+packUI.selected+'/lyrics',{});packUI.dirty=false;packUI.signature='';renderPack();}catch(error){$('#packError').textContent=error.message;}};
$('#packExport').onclick=async()=>{if(packUI.dirty)return toast('Save your captions before exporting.',true);try{await packUI.pending;packUI.doc=await packApi('/'+packUI.doc.id+'/export',{ids:packUI.doc.reels.filter(r=>r.selected).map(r=>r.id)});renderPack();}catch(error){$('#packError').textContent=error.message;}};
$('#packBack').onclick=()=>{show('footage');};

$('#pushPackResume').onclick=async()=>{try{const saved=JSON.parse(sessionStorage.getItem('montara-push-pack'));packUI.doc=await packApi('/'+saved.id);$('#pushPackURL').value=saved.url || '';if(saved.source)state.files=[{id:crypto.randomUUID(),name:saved.name,kind:'video',path:saved.source,sample:false}];$('#reelDuration').value=packUI.doc.length;const format=document.querySelector(`input[name=format][value="${packUI.doc.format}"]`);if(format)format.checked=true;packUI.inputKey=JSON.stringify([saved.url || saved.source,$('#reelDuration').value,reelFormat(),$('#mixShare').value]);packUI.signature='';packUI.dirty=false;show('pushPack');renderPack();pollPack();}catch(error){toast(error.message,true);}};
document.addEventListener('DOMContentLoaded',async()=>{
  const id=new URLSearchParams(location.search).get('push_pack');if(!id || !/^[0-9a-f]{32}$/.test(id))return;
  state.platform='reel';$('#modeLabel').textContent='Push';$('#pushPackOn').checked=true;show('pushPack');$('#packStatus').textContent='Opening your saved reel pack…';
  try{packUI.doc=await packApi('/'+id);$('#reelDuration').value=packUI.doc.length;$('#formatRow').hidden=false;$('#durationRow').hidden=false;sessionStorage.setItem('montara-push-pack',JSON.stringify({id}));renderPack();pollPack();}
  catch(error){$('#packError').textContent=error.message;}
});

function clearPackDeepLink(){const url=new URL(location.href);if(url.searchParams.has('push_pack')){url.searchParams.delete('push_pack');history.replaceState(history.state,'',url);}}
$('#newVideo').addEventListener('click',clearPackDeepLink);$('.brand').addEventListener('click',clearPackDeepLink);$('#packBack').addEventListener('click',clearPackDeepLink);

$('#packSyncWords').onclick=async()=>{if(packUI.dirty)return toast('Save the words first; saving also syncs them to the voice.',true);try{await packUI.pending;packUI.doc=await packApi('/'+packUI.doc.id+'/reels/'+packUI.selected+'/align',{});renderPack();}catch(error){$('#packError').textContent=error.message;}};
let packPaintFrame;
const packPaint=()=>{paintPackCaption();if(!$('#packVideo').paused&&!$('#pushPack').hidden)packPaintFrame=requestAnimationFrame(packPaint);};
$('#packVideo').addEventListener('play',()=>{cancelAnimationFrame(packPaintFrame);packPaint();});
$('#packVideo').addEventListener('pause',()=>cancelAnimationFrame(packPaintFrame));
const packMenu=document.createElement('div');packMenu.className='show-context-menu';packMenu.hidden=true;document.body.append(packMenu);
function openPackMenu(event,id){event.preventDefault();$('#packVideo').pause();packMenu.replaceChildren();const button=document.createElement('button');button.type='button';button.textContent='Adjust frame · Reel '+id;button.onclick=()=>{packMenu.hidden=true;openPackFrame(id);};packMenu.append(button);packMenu.style.left=Math.min(event.clientX,innerWidth-220)+'px';packMenu.style.top=Math.min(event.clientY,innerHeight-65)+'px';packMenu.hidden=false;button.focus();}
document.addEventListener('pointerdown',event=>{if(!packMenu.contains(event.target))packMenu.hidden=true;});document.addEventListener('keydown',event=>{if(event.key==='Escape')packMenu.hidden=true;});
$('#packVideo').oncontextmenu=event=>openPackMenu(event,packUI.selected);
const packFrameDialog=document.createElement('dialog');packFrameDialog.className='show-effect-dialog';packFrameDialog.id='packFrameDialog';
packFrameDialog.innerHTML='<h3 id="packFrameTitle">Adjust frame</h3><p class="hint">Drag the picture to choose what stays in the reel. Scroll or use the slider to zoom.</p><div id="packFrameStage"><video id="packFrameVideo" muted playsinline preload="metadata"></video></div><label>Zoom<input id="packFrameZoom" type="range" min=".1" max="3" step=".01" value="1"></label><div class="actions"><button class="btn ghost small" id="packFrameFit" type="button">Fit whole picture</button><button class="btn ghost small" id="packFrameReset" type="button">Reset frame</button><button class="btn ghost" id="packFrameCancel" type="button">Cancel</button><button class="btn primary" id="packFrameSave" type="button">Save frame</button></div><p class="hint" id="packFrameStatus" role="status"></p>';
document.body.append(packFrameDialog);let packFrameEdit;
function drawPackFrame(){const {x,y,zoom}=packFrameEdit.framing,v=$('#packFrameVideo');v.style.objectPosition=`${x*100}% ${y*100}%`;v.style.transformOrigin=`${x*100}% ${y*100}%`;v.style.transform=`scale(${zoom})`;$('#packFrameZoom').value=zoom;}
function openPackFrame(id){if(packUI.dirty)return toast('Save your captions before adjusting a frame.',true);const reel=packUI.doc.reels.find(r=>r.id===id);if(['running','queued'].includes(reel.render.status))return toast('Wait for this export before changing its frame.',true);$('#packVideo').pause();packFrameEdit={id,framing:{x:.5,y:.5,zoom:1,...reel.framing}};const v=$('#packFrameVideo'),framed=packFramedAt(reel,Math.max(0,$('#packVideo').currentTime-reel.start));$('#packFrameStage').style.aspectRatio='9 / 16';$('#packFrameStage').style.width='min(100%, calc(44vh * 9 / 16))';v.style.objectFit=framed?'contain':'cover';$('#packFrameTitle').textContent='Adjust frame · Reel '+id;$('#packFrameStatus').textContent='';const position=$('#packVideo').currentTime;v.onloadedmetadata=()=>{v.currentTime=position>=reel.start&&position<reel.end?position:reel.start+(reel.end-reel.start)/2;};v.src=packUI.doc.source_url;drawPackFrame();packFrameDialog.showModal();}
$('#packFrameStage').onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();const stage=e.currentTarget,v=$('#packFrameVideo'),box=stage.getBoundingClientRect(),start={px:e.clientX,py:e.clientY,...packFrameEdit.framing};stage.setPointerCapture(e.pointerId);const cover=v.style.objectFit==='cover',scale=(cover?Math.max(box.width/v.videoWidth,box.height/v.videoHeight):Math.min(box.width/v.videoWidth,box.height/v.videoHeight))*start.zoom,dx=v.videoWidth*scale-box.width,dy=v.videoHeight*scale-box.height;stage.onpointermove=move=>{packFrameEdit.framing.x=Math.max(0,Math.min(1,start.x-(move.clientX-start.px)/(Math.abs(dx)<1?box.width:dx)));packFrameEdit.framing.y=Math.max(0,Math.min(1,start.y-(move.clientY-start.py)/(Math.abs(dy)<1?box.height:dy)));drawPackFrame();};const finish=()=>{stage.onpointermove=null;stage.onpointerup=null;stage.onpointercancel=null;};stage.onpointerup=stage.onpointercancel=finish;};
$('#packFrameZoom').oninput=()=>{packFrameEdit.framing.zoom=Number($('#packFrameZoom').value);drawPackFrame();};$('#packFrameStage').onwheel=e=>{e.preventDefault();packFrameEdit.framing.zoom=Math.max(.1,Math.min(3,packFrameEdit.framing.zoom+(e.deltaY<0?.05:-.05)));drawPackFrame();};
$('#packFrameReset').onclick=()=>{packFrameEdit.framing={x:.5,y:.5,zoom:1};drawPackFrame();};$('#packFrameCancel').onclick=()=>packFrameDialog.close();
$('#packFrameSave').onclick=async()=>{const button=$('#packFrameSave');button.disabled=true;try{await patchPackReel(packFrameEdit.id,{framing:packFrameEdit.framing});packFrameDialog.close();}catch(error){$('#packFrameStatus').textContent=error.message;}finally{button.disabled=false;}};

$('#packUseDetected').onclick=async()=>{if(packUI.dirty)return toast('Save or undo your current text changes first.',true);try{await patchPackReel(packUI.selected,{use_detected_captions:true});}catch{}};

$('#pushPackExample').onclick=()=>{$('#pushPackURL').value='https://www.youtube.com/watch?v=bfGH-664RQ4';packUI.doc=null;renderFiles();};

document.addEventListener('DOMContentLoaded',async()=>{if(sessionStorage.getItem('montara-push-pack'))return;try{const latest=await packApi('/latest');if(latest.id){sessionStorage.setItem('montara-push-pack',JSON.stringify(latest));packInput();}}catch{}});

$('#packLayout').onchange=async()=>{if(packUI.dirty){$('#packLayout').value=packUI.doc.format;return toast('Save your captions first.',true);}try{await packUI.pending;packUI.doc=await packApi('/'+packUI.doc.id,{revision:packUI.doc.revision,format:$('#packLayout').value},'PATCH');packUI.signature='';renderPack();}catch(e){$('#packError').textContent=e.message;renderPack();}};
$('#packFrameFit').onclick=()=>{const v=$('#packFrameVideo'),box=$('#packFrameStage').getBoundingClientRect();if(!v.videoWidth)return;const contain=Math.min(box.width/v.videoWidth,box.height/v.videoHeight),cover=Math.max(box.width/v.videoWidth,box.height/v.videoHeight);packFrameEdit.framing={x:.5,y:.5,zoom:v.style.objectFit==='contain'?1:Math.max(.1,contain/cover)};drawPackFrame();};

$('#packAdjustFrame').onclick=()=>openPackFrame(packUI.selected);

$('#packMixShare').onchange=async()=>{if(packUI.dirty)return toast('Save your captions first.',true);try{await packUI.pending;packUI.doc=await packApi('/'+packUI.doc.id,{revision:packUI.doc.revision,mix_vertical_ratio:$('#packMixShare').value},'PATCH');packUI.signature='';renderPack();}catch(e){$('#packError').textContent=e.message;}};
