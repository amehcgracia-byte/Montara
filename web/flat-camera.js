// Ordinary cameras: choose an area in the source frame. No rendering while adjusting.
function mountFlatCamera(host,initial={},options={}){
  host.classList.add('flat-camera');host.innerHTML='<div class="flat-frame"><img alt="Camera frame: click or drag to choose the visible area" draggable="false"><i class="flat-crop"></i><span class="flat-loading">Loading camera frame…</span></div><div class="flat-zoom-row"><button type="button" class="btn ghost small flat-out" aria-label="Open the shot">−</button><label>Zoom <output></output><input type="range" min="1" max="6" step=".05" aria-label="Close or open the shot"></label><button type="button" class="btn ghost small flat-in" aria-label="Close the shot">+</button></div><p class="hint">Click to centre the shot. Drag the frame to move it. The area inside the box is kept.</p><button type="button" class="link flat-reset">Original framing</button>';
  const live=options.aspect?document.createElement('canvas'):null;if(live){live.width=180;live.height=320;live.className='flat-live-preview';host.append(live);}
  const image=host.querySelector('img'),frame=host.querySelector('.flat-frame'),box=host.querySelector('.flat-crop'),slider=host.querySelector('input'),loading=host.querySelector('.flat-loading');let value={zoom:1,x:.5,y:.5,...initial};
  const draw=()=>{
    const side=100/value.zoom,cx=Math.max(side/2,Math.min(100-side/2,value.x*100)),cy=Math.max(side/2,Math.min(100-side/2,value.y*100));
    const sourceAspect=image.naturalWidth/image.naturalHeight || 16/9;
    const w=options.aspect&&!options.contain?side*Math.min(1,options.aspect/sourceAspect):side;
    const h=options.aspect&&!options.contain?side*Math.min(1,sourceAspect/options.aspect):side;
    Object.assign(box.style,{left:(cx-w/2)+'%',top:(cy-h/2)+'%',width:w+'%',height:h+'%'});
    if(live && image.naturalWidth){
      const ctx=live.getContext('2d');ctx.fillStyle='#0b0b0d';ctx.fillRect(0,0,live.width,live.height);
      const sx=(cx-w/2)/100*image.naturalWidth,sy=(cy-h/2)/100*image.naturalHeight,sw=w/100*image.naturalWidth,sh=h/100*image.naturalHeight;
      if(options.contain){const scale=Math.min(live.width/sw,live.height/sh),dw=sw*scale,dh=sh*scale;ctx.drawImage(image,sx,sy,sw,sh,(live.width-dw)/2,(live.height-dh)/2,dw,dh);}
      else ctx.drawImage(image,sx,sy,sw,sh,0,0,live.width,live.height);
    }
    slider.value=value.zoom;host.querySelector('output').textContent=value.zoom.toFixed(2)+'×';
  };

  const zoom=amount=>{value.zoom=Math.round(Math.max(1,Math.min(6,value.zoom+amount))*100)/100;draw();};
  host.querySelector('.flat-out').onclick=()=>zoom(-.1);host.querySelector('.flat-in').onclick=()=>zoom(.1);slider.oninput=()=>{value.zoom=Number(slider.value);draw();};host.querySelector('.flat-reset').onclick=()=>{value={zoom:1,x:.5,y:.5};draw();};
  frame.onpointerdown=event=>{if(event.button!==0||!image.naturalWidth)return;event.preventDefault();frame.setPointerCapture(event.pointerId);const rect=frame.getBoundingClientRect();if(event.target!==box){value.x=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width));value.y=Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));draw();}const start={px:event.clientX,py:event.clientY,...value};frame.onpointermove=move=>{value.x=Math.max(0,Math.min(1,start.x+(move.clientX-start.px)/rect.width));value.y=Math.max(0,Math.min(1,start.y+(move.clientY-start.py)/rect.height));draw();};frame.onpointerup=frame.onpointercancel=()=>{frame.onpointermove=null;frame.onpointerup=null;frame.onpointercancel=null;};};
  image.onload=()=>{loading.hidden=true;draw();};image.onerror=()=>{loading.hidden=false;loading.textContent='Could not load this frame. You can still adjust the zoom.';};draw();
  return {destroy:()=>{image.onload=image.onerror=null;image.removeAttribute('src');},get:()=>({...value}),set:next=>{value={zoom:1,x:.5,y:.5,...next};draw();},setImage:url=>{loading.hidden=false;loading.textContent='Loading camera frame…';image.src=url;}};
}
