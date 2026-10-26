// Music is placed through the engine's existing audio APIs, never a separate renderer.
"use strict";
const musicShelf={items:[],chosen:null,scene:null,project:null,busy:false,playToken:0,moreAvailable:0};
const musicDialog=document.createElement('dialog');musicDialog.id='showMusicDialog';musicDialog.className='show-effect-dialog';musicDialog.setAttribute('aria-labelledby','showMusicTitle');
musicDialog.innerHTML=`<div class="show-dialog-heading"><h3 id="showMusicTitle">Music</h3><button type="button" class="btn ghost small" id="showMusicClose">Close</button></div><p class="hint">Choose a track for this part, or add your own. Browse the library, upload audio or add a link.</p><div class="actions"><label class="btn ghost small">Upload your music<input type="file" accept="audio/*" id="showMusicUpload" hidden></label><label>Find music<input id="showMusicSearch" type="search" placeholder="Name or mood"></label></div><form id="showMusicLinkForm" class="actions"><label>YouTube link<input id="showMusicLinkUrl" type="url" placeholder="https://www.youtube.com/watch?v=…" required></label><button type="submit" class="btn ghost small">Add from link</button></form><p class="hint">Paste a YouTube link, or upload your audio file.</p><div id="showMusicList" class="music-shelf-list"></div><button id="showMusicMore" type="button" class="btn ghost small music-more">More creator classics</button><form id="showMusicPlace"><h4 id="showMusicChosen">Choose a track</h4><p class="hint" id="showMusicRights"></p><a id="showMusicSource" target="_blank" rel="noopener noreferrer" hidden>Source and licence</a><audio id="showMusicListen" preload="none" hidden></audio><div class="show-placement"><label>Start in this part (seconds)<input id="showMusicAt" type="number" min="0" step="0.1" required></label><label>Duration (seconds)<input id="showMusicDuration" type="number" min="0.1" step="0.1" required></label></div><label>Start inside the music (seconds)<input id="showMusicStart" type="number" min="0" step="0.1" value="0"></label><label>Music level <output id="showMusicLevelValue">28%</output><input id="showMusicLevel" type="range" min="0" max="100" value="28"></label><label><input type="checkbox" id="showMusicDuck" checked> Keep narration in front</label><p class="hint">Hear the mix with Preview this part. Move or trim the music on the timeline; right-click to edit or remove it.</p><div class="actions"><button class="btn primary small" type="submit" id="showMusicAdd" disabled>Add music</button><button type="button" id="showMusicCredits" class="btn ghost small">Music attribution</button></div></form><p class="hint" id="showMusicStatus" role="status"></p>`;
document.body.append(musicDialog);
const musicContext=document.createElement('button');musicContext.type='button';musicContext.role='menuitem';musicContext.textContent='Music';musicContext.addEventListener('click',openMusicShelf);$('#showContextMenu').append(musicContext);
function renderMusicShelf(){
 const q=$('#showMusicSearch').value.trim().toLowerCase(),list=$('#showMusicList');list.replaceChildren();let category='';
 for(const track of musicShelf.items.filter(t=>`${t.name} ${t.mood} ${t.artist} ${t.category}`.toLowerCase().includes(q))){
  if(category!==track.category){category=track.category;const heading=document.createElement('h4');heading.className='music-category';heading.textContent=category;list.append(heading);}
  const row=document.createElement('button');row.type='button';row.className='music-shelf-track'+(track.id===musicShelf.chosen?.id?' on':'');row.dataset.musicTrack=track.id;const icon=document.createElement('span');icon.className='music-row-play';icon.setAttribute('aria-hidden','true');icon.textContent='▶';
  const title=document.createElement('strong');title.textContent=track.name;const detail=document.createElement('small');detail.textContent=`${track.mood} · ${track.artist} · ${track.license==='CC0'?'CC0 — no credit required':track.license==='CC BY 4.0'?'Free · credit the artist':track.license}`;row.append(icon,title,detail);
  row.addEventListener('click',()=>auditionMusic(track));list.append(row);
 }
 if(!list.children.length)list.textContent='No music found. Try another name or upload your own.';
 paintMusicPlayback();
}
function paintMusicPlayback(){
 const audio=$('#showMusicListen');
 for(const row of $('#showMusicList').querySelectorAll('[data-music-track]')){
  const selected=row.dataset.musicTrack===musicShelf.chosen?.id,playing=selected&&!audio.paused&&!audio.ended;
  const track=musicShelf.items.find(t=>t.id===row.dataset.musicTrack);
  row.classList.toggle('playing',playing);row.setAttribute('aria-label',`${playing?'Pause':'Play'} ${track?.name||'music'}`);row.setAttribute('aria-pressed',String(playing));
  row.querySelector('.music-row-play').textContent=playing?'❚❚':'▶';
  row.style.setProperty('--music-progress',selected&&Number.isFinite(audio.duration)&&audio.duration>0?Math.min(100,100*audio.currentTime/audio.duration)+'%':'0%');
 }
}
function auditionMusic(track){
 const audio=$('#showMusicListen'),same=musicShelf.chosen?.id===track.id;
 if(same&&!audio.paused){audio.pause();return;}
 if(!same){
  audio.pause();musicShelf.chosen=track;audio.src=track.url;audio.volume=Number($('#showMusicLevel').value)/100;
  $('#showMusicRights').textContent=track.license==='CC BY 4.0'?'CC BY 4.0 · Attribution prepared for your final video.':track.license==='CC0'?'CC0: no attribution required.':'Your audio';
  $('#showMusicSource').hidden=!track.page;$('#showMusicSource').href=track.page||'#';$('#showMusicChosen').textContent=track.name;$('#showMusicStart').value='0';$('#showMusicAdd').disabled=false;
  const duration=$('#showMusicDuration');duration.value=Math.min(Number(duration.value),track.duration).toFixed(1);
  renderMusicShelf();
 }
 if(audio.ended)audio.currentTime=0;
 const token=++musicShelf.playToken;$('#showMusicStatus').textContent='';
 audio.play().catch(error=>{if(token===musicShelf.playToken&&error.name!=='AbortError'){$('#showMusicStatus').textContent='Could not play this song. Tap its play button to try again.';paintMusicPlayback();}});
}
for(const event of ['play','pause','timeupdate','ended','loadedmetadata'])$('#showMusicListen').addEventListener(event,paintMusicPlayback);
async function loadMusicShelf(){
 const data=await api('/montara/music');musicShelf.items=data.items;musicShelf.moreAvailable=Number(data.more_available)||0;
 const button=$('#showMusicMore');button.hidden=false;button.disabled=!musicShelf.moreAvailable;button.textContent=musicShelf.moreAvailable?`More music · ${musicShelf.moreAvailable} left`:`All ${data.library_total||musicShelf.items.length} library tracks loaded`;
 renderMusicShelf();
}
async function openMusicShelf(){
 const scene=showEdit.scenes[showEdit.selected];if(!scene)return;
 $('#showSceneVideo').pause();$('#showContextMenu').hidden=true;musicShelf.scene=scene.id;musicShelf.project=state.projectId;musicShelf.chosen=null;$('#showMusicRights').textContent='';$('#showMusicSource').hidden=true;$('#showMusicChosen').textContent='Choose a track';$('#showMusicAdd').disabled=true;$('#showMusicListen').hidden=true;$('#showMusicSearch').value='';
 const at=Math.floor(Math.max(0,Math.min(showPlaybackOffset(),scene.end-scene.start-.1))*10)/10;$('#showMusicAt').value=at.toFixed(1);$('#showMusicDuration').value=(Math.floor((scene.end-scene.start-at)*10)/10).toFixed(1);$('#showMusicStatus').textContent='Loading music…';musicDialog.showModal();
 try{await loadMusicShelf();$('#showMusicStatus').textContent='';}catch(error){$('#showMusicStatus').textContent=error.message;}
}
$('#showMusicOpen').addEventListener('click',openMusicShelf);
$('#showMusicClose').addEventListener('click',()=>{if(!musicShelf.busy)musicDialog.close();});
musicDialog.addEventListener('cancel',e=>{if(musicShelf.busy)e.preventDefault();});musicDialog.addEventListener('close',()=>{musicShelf.playToken++;$('#showMusicListen').pause();});
$('#showMusicSearch').addEventListener('input',()=>{$('#showMusicListen').pause();renderMusicShelf();});
$('#showMusicLevel').addEventListener('input',()=>{$('#showMusicLevelValue').textContent=$('#showMusicLevel').value+'%';$('#showMusicListen').volume=Number($('#showMusicLevel').value)/100;});
$('#showMusicUpload').addEventListener('change',async e=>{
 const file=e.target.files[0];e.target.value='';if(!file||musicShelf.busy)return;musicShelf.busy=true;$('#showMusicStatus').textContent='Adding your music…';
 try{const body=new FormData();body.append('file',file);const response=await fetch('/montara/music/import',{method:'POST',body});const data=await response.json();if(!response.ok)throw new Error(data.error?.message||'Could not import this audio.');await loadMusicShelf();$('#showMusicStatus').textContent='Your music is ready.';}catch(error){$('#showMusicStatus').textContent=error.message;}finally{musicShelf.busy=false;}
});
$('#showMusicPlace').addEventListener('submit',async e=>{
 e.preventDefault();if(musicShelf.busy||!musicShelf.chosen)return;const scene=showEdit.scenes[showEdit.selected];
 if(musicShelf.project!==state.projectId||musicShelf.scene!==scene?.id){$('#showMusicStatus').textContent='Reopen Music in the part you want to edit.';return;}
 const offset=Number($('#showMusicAt').value),duration=Number($('#showMusicDuration').value),start=Number($('#showMusicStart').value);
 if(!Number.isFinite(offset+duration+start)||offset<0||duration<.1||offset+duration>scene.end-scene.start+.001||start<0){$('#showMusicStatus').textContent='Keep the music inside this part.';return;}
 musicShelf.busy=true;$('#showMusicAdd').disabled=true;$('#showMusicStatus').textContent='Adding music…';
 try{const result=await api('/montara/music/place/'+musicShelf.chosen.id,{scene_id:scene.id,project_id:state.projectId,at:scene.start+offset,duration,start,volume:Number($('#showMusicLevel').value)/100,under_voice:$('#showMusicDuck').checked});showPushUndo({type:'proposal',id:result.proposal.id,sceneId:scene.id,changes:{status:'discarded'}});await refreshShowEditor(scene.id);$('#showPreviewStatus').textContent='Music added. Updating preview…';musicDialog.close();}catch(error){$('#showMusicStatus').textContent=error.message;}finally{musicShelf.busy=false;$('#showMusicAdd').disabled=false;}
});

$('#showMusicStart').addEventListener('change',()=>{const a=$('#showMusicListen'),t=Number($('#showMusicStart').value);if(Number.isFinite(t)&&t>=0&&Number.isFinite(a.duration))a.currentTime=Math.min(t,a.duration);});

$('#showMusicLinkForm').addEventListener('submit',async e=>{
 e.preventDefault();if(musicShelf.busy)return;musicShelf.busy=true;const button=e.target.querySelector('button');button.disabled=true;button.classList.add('music-importing');$('#showMusicStatus').textContent='Preparing your music…';
 try{
  await api('/montara/music/link',{url:$('#showMusicLinkUrl').value});
  let result;
  do{await new Promise(resolve=>setTimeout(resolve,1500));result=await api('/montara/music/link');}while(result.status==='importing');
  if(result.status!=='ready')throw new Error(result.message||'Could not retrieve this music. Try uploading an audio file.');
  await loadMusicShelf();$('#showMusicStatus').textContent='Music ready. Choose it from the library.';
 }catch(error){$('#showMusicStatus').textContent=error.message;}finally{musicShelf.busy=false;button.disabled=false;button.classList.remove('music-importing');}
});

$('#showMusicMore').addEventListener('click',async()=>{
 if(musicShelf.busy)return;musicShelf.busy=true;const button=$('#showMusicMore');button.disabled=true;button.classList.add('music-importing');$('#showMusicStatus').textContent='Fetching more music…';
 try{let result=await api('/montara/music/more',{});while(result.status==='importing'){await new Promise(resolve=>setTimeout(resolve,1500));result=await api('/montara/music/more');}await loadMusicShelf();if(result.status==='failed')throw new Error(result.message);$('#showMusicStatus').textContent=`${result.added} more songs ready.`;}catch(error){$('#showMusicStatus').textContent=error.message;}finally{musicShelf.busy=false;button.disabled=!musicShelf.moreAvailable;button.classList.remove('music-importing');}
});
const attributionDialog=document.createElement('dialog');attributionDialog.className='show-effect-dialog';attributionDialog.setAttribute('aria-labelledby','attributionTitle');
attributionDialog.innerHTML=`<div class="show-dialog-heading"><h3 id="attributionTitle">Music attribution</h3><button class="btn ghost small" id="attributionClose" type="button">Close</button></div><p class="hint" id="attributionHelp">Artist names and licences for the music used in this video. This is not your subscription balance.</p><textarea id="attributionText" class="music-credit-text" aria-label="Music attribution text" readonly></textarea><div class="actions"><button id="attributionCopy" class="btn primary small" type="button">Copy for video description</button><a id="attributionDownload" class="btn ghost small" download>Download text</a></div><p class="hint" id="attributionStatus" role="status"></p>`;document.body.append(attributionDialog);
async function openMusicAttribution(){
 $('#attributionStatus').textContent='Loading…';$('#attributionText').value='';$('#attributionCopy').disabled=true;$('#attributionDownload').hidden=true;attributionDialog.showModal();
 try{const base='/montara/music/credits?project_id='+encodeURIComponent(state.projectId),data=await api(base+'&format=json');$('#attributionText').value=data.text;$('#attributionText').hidden=!data.required;$('#attributionCopy').hidden=!data.required;$('#attributionCopy').disabled=!data.required;$('#attributionDownload').hidden=!data.required;$('#attributionDownload').href=base;$('#attributionStatus').textContent=data.required?'Include this text in your video description or end credits.':'No attribution-required library music is currently used. Your own uploads do not automatically generate an artist credit.';}catch(error){$('#attributionStatus').textContent=error.message;}
}
async function refreshResultAttribution(){
 $('#resultMusicCredits').hidden=true;if(state.platform!=='show')return;const data=await api('/montara/music/credits?format=json&project_id='+encodeURIComponent(state.projectId));$('#resultMusicCredits').hidden=!data.required;
}
$('#showMusicCredits').addEventListener('click',openMusicAttribution);$('#resultMusicCreditsOpen').addEventListener('click',openMusicAttribution);
$('#attributionClose').onclick=()=>attributionDialog.close();$('#attributionCopy').onclick=async()=>{try{await navigator.clipboard.writeText($('#attributionText').value);$('#attributionStatus').textContent='Copied.';}catch{$('#attributionText').focus();$('#attributionText').select();$('#attributionStatus').textContent='Select and copy this text.';}};
