"use strict";
// Match the green matte and light recovery used by the rendering engine.
function showKeyPixels(image,matte){
 const d=image.data,clip=x=>Math.max(0,Math.min(1,x));let bg=[0,255,0];
 if(matte==='green-light'){
  const samples=[[],[],[]],w=image.width,h=image.height;
  for(let y=0;y<h;y+=2)for(let x=0;x<w;x+=2){if(x>4&&x<w-5&&y>4&&y<h-5)continue;const i=(y*w+x)*4;if(d[i+1]-Math.max(d[i],d[i+2])>30)for(let c=0;c<3;c++)samples[c].push(d[i+c]);}
  if(samples[0].length)bg=samples.map(a=>a.sort((x,y)=>x-y)[Math.floor(a.length/2)]);
 }
 for(let i=0;i<d.length;i+=4){
  let r=d[i],g=d[i+1],b=d[i+2],a=1;
  if(matte==='green'){
   a=1-clip((g-Math.max(r,b)-22)/45)*clip((g-65)/50);
   // Suppress green spill at the keyed edge, retaining the subject's colours.
   if(a<.99)g=Math.min(g,Math.max(r,b)+18);
  }else if(matte==='black'||matte==='green-light'){
   if(matte==='green-light'){
    const opacity=clip(Math.max((r-bg[0])/Math.max(1,255-bg[0]),(b-bg[2])/Math.max(1,255-bg[2])));
    r=Math.min(opacity*255,Math.max(0,r-bg[0]*(1-opacity)));g=Math.min(opacity*255,Math.max(0,g-bg[1]*(1-opacity)));b=Math.min(opacity*255,Math.max(0,b-bg[2]*(1-opacity)));
   }
   a=Math.max(r,g,b)/255;
   if(a){r/=a;g/=a;b/=a;}
  }
  d[i]=r;d[i+1]=g;d[i+2]=b;d[i+3]=Math.round(d[i+3]*a);
 }
 return image;
}
function showKeyedVideo(shape,video){
 const canvas=document.createElement('canvas');canvas.className='show-keyed-video';shape.append(canvas);
 const ctx=canvas.getContext('2d',{willReadFrequently:true});
 const draw=()=>{
  const mode=shape.dataset.matte,keyed=['green','black','green-light'].includes(mode);
  video.style.display=keyed?'none':'';canvas.hidden=!keyed;
  if(!keyed||video.readyState<2||!shape.isConnected)return;
  const w=Math.min(640,video.videoWidth),h=Math.max(1,Math.round(video.videoHeight*w/video.videoWidth));
  if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
  ctx.drawImage(video,0,0,w,h);const pixels=ctx.getImageData(0,0,w,h);ctx.putImageData(showKeyPixels(pixels,mode),0,0);
 };
 let ticket=0;
 const loop=()=>{draw();if(!video.paused&&shape.isConnected)ticket=requestAnimationFrame(loop);else ticket=0;};
 video.addEventListener('play',()=>{if(!ticket)loop();});video.addEventListener('seeked',draw);video.addEventListener('loadeddata',draw);shape.drawKeyed=draw;
}
