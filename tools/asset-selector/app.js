'use strict';
const $=s=>document.querySelector(s);let data,view='pending',collection='green',chosen=null,player=null,limit=12,lastQuery='',visibleCount=24,hoverCard=null,hoverTimer=null;
async function api(path,body){const r=await fetch('/api/'+path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const d=await r.json();if(!r.ok)throw Error(d.error||'No se ha podido completar');return d;}
function status(t){$('#status').textContent=t;}
async function load(){data=await api('state');render();}
function text(tag,s,cls){const n=document.createElement(tag);n.textContent=s;if(cls)n.className=cls;return n;}
function button(s,fn){const n=text('button',s);n.type='button';n.onclick=async()=>{try{await fn(n);}catch(e){status(e.message);}};return n;}
function stopHover(){clearTimeout(hoverTimer);if(hoverCard){hoverCard.querySelector('.hover-preview')?.remove();hoverCard=null;}}
function startHover(card,c){stopHover();hoverTimer=setTimeout(()=>{hoverCard=card;const frame=document.createElement(c.status==='ready'?'video':'iframe');frame.className='hover-preview';if(frame.tagName==='VIDEO'){frame.src='/media/'+c.file;frame.muted=true;frame.autoplay=true;frame.loop=true;frame.playsInline=true;frame.play().catch(()=>{});}else{frame.src='https://www.youtube.com/embed/'+(c.video_id||c.id)+'?autoplay=1&mute=1&controls=0&playsinline=1&loop=1&playlist='+(c.video_id||c.id)+'&rel=0';frame.title='Vista previa sin sonido';frame.allow='autoplay; encrypted-media';frame.referrerPolicy='strict-origin-when-cross-origin';}card.querySelector('.thumb').append(frame);},300);}
function diverse(items){
 const groups=new Map();for(const c of items){const key=c.category; if(!groups.has(key))groups.set(key,[]);groups.get(key).push(c);}
 const result=[];while([...groups.values()].some(g=>g.length))for(const g of groups.values())if(g.length)result.push(g.shift());return result;
}
function render(){
 const selectedFilter=$('#filter').value,categories=[...new Set(data.candidates.map(c=>c.category).concat(data.clips.map(c=>c.category)))].sort(),tops=[...new Set(categories.map(c=>c.split('/')[0]))].sort();
 const options=[['','Todas las carpetas'],...tops.flatMap(t=>[[t,t],...categories.filter(c=>c.startsWith(t+'/')).map(c=>[c,'↳ '+c.split('/').slice(1).join(' / ')])])];
 $('#filter').replaceChildren(...options.map(([value,label])=>{const o=document.createElement('option');o.value=value;o.textContent=label;return o;}));$('#filter').value=selectedFilter;
 stopHover();const clips=data.clips.filter(c=>(c.collection||'green')===collection),accepted=new Set(clips.map(c=>c.video_id)),rejected=new Set((data.rejections||data.rejected.map(v=>'green:'+v)).filter(v=>v.startsWith(collection+':')).map(v=>v.slice(collection.length+1))),filter=$('#filter').value;
 $('#stats').textContent=`${data.clips.length} fragmentos elegidos · decisiones guardadas`;
 const items=view==='saved'?clips:data.candidates.filter(c=>c.collection===collection&&!c.off_topic&&(view==='rejected'?rejected.has(c.id):!rejected.has(c.id)&&!accepted.has(c.id)));
 const grid=$('#grid');grid.replaceChildren();
 let matching=items.filter(c=>!filter||c.category.startsWith(filter));
 if(view==='pending'){matching=diverse(matching.sort((a,b)=>Number(b.category.startsWith('Dibujos'))-Number(a.category.startsWith('Dibujos'))));if(lastQuery)matching.sort((a,b)=>Number(b.query===lastQuery)-Number(a.query===lastQuery));}
 for(const c of matching.slice(0,visibleCount)){
  const card=text('article','','card'),thumb=text('div','','thumb'),image=document.createElement('img');image.src='https://i.ytimg.com/vi/'+(c.video_id||c.id)+'/mqdefault.jpg';image.alt='';image.loading='lazy';thumb.append(image,text('span','Pasa el ratón · vista sin sonido','hover-hint'));card.append(thumb);
  thumb.tabIndex=0;thumb.setAttribute('role','button');thumb.setAttribute('aria-label','Previsualizar: '+(c.name||c.title));thumb.addEventListener('focus',()=>startHover(card,c));thumb.addEventListener('blur',stopHover);thumb.addEventListener('keydown',e=>{if(e.key==='Enter')open(c);});
  thumb.addEventListener('pointerenter',e=>{if(e.pointerType!=='touch')startHover(card,c);});thumb.addEventListener('pointerleave',stopHover);thumb.addEventListener('click',()=>open(c));
  const body=text('div','','body');body.append(text('h3',c.name||c.title),text('div',c.category.replaceAll('/',' / '),'meta tag'));
  body.append(text('div',view==='saved'?`${c.start}–${c.end}s · ${c.status==='ready'?Math.round(c.bytes/1024)+' KB':c.status==='error'?'Descarga pendiente: reintentar':'Descargando…'}`:`${c.channel||'YouTube'}${c.duration?' · '+Math.round(c.duration)+'s':''}`,'meta'));
  const actions=text('div','','actions');
  if(view==='pending'){
   const yes=button('Sí',async b=>{b.disabled=true;if(!c.duration||c.duration>120){open(c);$('#clipStatus').textContent='Vídeo largo: elige el fragmento que quieras conservar.';b.disabled=false;return;}await accept(c,0,c.duration,c.title,c.category,collection);});yes.className='primary';actions.append(yes,button('No',async()=>{await api('reject',{id:c.id,collection});await load();}),button('Revisar',()=>open(c)));
  }else if(view==='rejected')actions.append(button('Revisar',()=>open(c)),button('Recuperar',async()=>{await api('restore',{id:c.id,collection});await load();}));
  else{actions.append(button('Ver / recortar',()=>open(c)),button(collection==='green'?'Mover a vídeos con fondo':'Mover a green screens',async()=>{await api('classify',{id:c.video_id,collection:collection==='green'?'regular':'green'});await load();}));if(c.status==='error')actions.append(button('Reintentar',async()=>{const d=await api('retry',{id:c.id});watch(d.job);await load();}));}
  body.append(actions);card.append(body);grid.append(card);
 }
 if(!grid.children.length)grid.append(text('div',view==='saved'?'Aquí aparecerán los fragmentos que elijamos.':'No quedan candidatos con este filtro. Busca algo nuevo o cambia de carpeta.','empty'));
 $('#more').hidden=view!=='pending';if(matching.length>visibleCount)grid.append(button('Mostrar otros 24 candidatos',()=>{visibleCount+=24;render();}));
 $('#collectionHint').textContent=collection==='green'?'Primera pasada: fondos verdes o negros que se pueden eliminar. Los resultados son candidatos por revisar.':'Segunda pasada: escenas y frases con su imagen completa. Se guardan en otra carpeta.';
}
async function watch(key,local=false){if(!key)return;const timer=setInterval(async()=>{try{const job=await api('jobs/'+key);status(job.message);if(local)$('#clipStatus').textContent=job.message;if(job.status!=='working'){clearInterval(timer);await load();}}catch(e){clearInterval(timer);status(e.message);}},1200);}
async function accept(c,start,end,name,category,type){const d=await api('accept',{url:'https://www.youtube.com/watch?v='+(c.video_id||c.id),name,category,start,end,collection:type});status(d.duplicate?'Este fragmento ya estaba guardado.':'Sí: elección guardada. Descargando en su carpeta…');watch(d.job,true);await load();return d;}
async function doSearch(){const d=await api('search',{query:lastQuery,limit,category:$('#searchCategory').value,collection});status('Buscando en YouTube… puedes seguir revisando.');watch(d.job);}
$('#searchForm').onsubmit=async e=>{e.preventDefault();lastQuery=$('#query').value;limit=12;visibleCount=24;try{await doSearch();}catch(e){status(e.message);}};
$('#more').onclick=async()=>{lastQuery=$('#query').value;limit=Math.min(60,limit+12);await doSearch();};
$('#linkForm').onsubmit=async e=>{e.preventDefault();try{const d=await api('link',{url:$('#link').value,category:$('#searchCategory').value,collection});await load();open(data.candidates.find(c=>c.id===d.id));}catch(e){status(e.message);}};
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{view=b.dataset.view;visibleCount=24;document.querySelectorAll('[data-view]').forEach(n=>n.setAttribute('aria-pressed',String(n===b)));render();};
for(const b of document.querySelectorAll('[data-collection]'))b.onclick=()=>{collection=b.dataset.collection;lastQuery='';visibleCount=24;document.querySelectorAll('[data-collection]').forEach(n=>n.setAttribute('aria-pressed',String(n===b)));render();};
$('#filter').onchange=()=>{visibleCount=24;render();};
function open(c){
 stopHover();chosen=c;const vid=c.video_id||c.id;$('#title').textContent=c.name||c.title;$('#clipName').value=c.name||c.title;$('#clipCategory').value=c.category;$('#clipCollection').value=c.collection||collection;$('#start').value=c.start||0;$('#end').value=c.end||Math.min(c.duration||3,120);$('#clipStatus').textContent='';$('#youtube').href='https://www.youtube.com/watch?v='+vid;
 $('#player').replaceChildren();player=null;
 const frame=document.createElement('iframe');frame.id='ytPlayer';frame.src='https://www.youtube.com/embed/'+vid+'?enablejsapi=1&origin='+encodeURIComponent(location.origin);frame.title=c.title||c.name;frame.allow='autoplay; encrypted-media; picture-in-picture';frame.referrerPolicy='strict-origin-when-cross-origin';frame.allowFullscreen=true;$('#player').append(frame);if(window.YT?.Player)player=new YT.Player('ytPlayer');$('#editor').showModal();
}
function close(){if(player?.destroy)player.destroy();player=null;$('#player').replaceChildren();$('#editor').close();}
$('#close').onclick=close;$('#editor').addEventListener('cancel',()=>{if(player?.stopVideo)player.stopVideo();$('#player').replaceChildren();});
function mark(id){if(player?.getCurrentTime)$(id).value=player.getCurrentTime().toFixed(1);else $('#clipStatus').textContent='Puedes escribir los segundos manualmente mientras carga YouTube.';}
$('#markIn').onclick=()=>mark('#start');$('#markOut').onclick=()=>mark('#end');
$('#preview').onclick=()=>{const start=Number($('#start').value),end=Number($('#end').value);if(player?.loadVideoById)player.loadVideoById({videoId:chosen.video_id||chosen.id,startSeconds:start,endSeconds:end});};
$('#reject').onclick=async()=>{await api('reject',{id:chosen.video_id||chosen.id,collection});close();await load();};
$('#clipForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const d=await accept(chosen,Number($('#start').value),Number($('#end').value),$('#clipName').value,$('#clipCategory').value,$('#clipCollection').value);$('#clipStatus').textContent=d.duplicate?'Este fragmento ya estaba guardado.':'Guardado. Puedes marcar otro tramo de este vídeo.';}catch(e){$('#clipStatus').textContent=e.message;}finally{b.disabled=false;}};
window.onYouTubeIframeAPIReady=()=>{if($('#ytPlayer'))player=new YT.Player('ytPlayer');};const script=document.createElement('script');script.src='https://www.youtube.com/iframe_api';document.head.append(script);load().catch(e=>status(e.message));
