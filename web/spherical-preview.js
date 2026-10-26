// Full equirectangular samples. Projection runs locally on the browser's GPU;
// no fixed-view replacement and no network request while aiming the camera.
'use strict';
class WebSphere {
  constructor(){
    this.canvas=document.createElement('canvas');this.canvas.width=640;this.canvas.height=360;
    const gl=this.gl=this.canvas.getContext('webgl',{preserveDrawingBuffer:true,alpha:false});
    if(!gl)throw new Error('This browser needs WebGL for interactive 360 views.');
    const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;};
    const program=this.program=gl.createProgram();
    gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec2 p; varying vec2 uv; void main(){uv=p*.5+.5;gl_Position=vec4(p,0.,1.);}'));
    gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`precision highp float; varying vec2 uv; uniform sampler2D frame; uniform vec3 pose;
      void main(){float h=tan(radians(pose.z)*.5);vec3 r=normalize(vec3((uv.x*2.-1.)*h,(uv.y*2.-1.)*h/(16./9.),1.));
      float a=radians(pose.x),b=radians(pose.y);r=vec3(r.x,cos(b)*r.y+sin(b)*r.z,-sin(b)*r.y+cos(b)*r.z);
      r=vec3(cos(a)*r.x+sin(a)*r.z,r.y,-sin(a)*r.x+cos(a)*r.z);
      vec2 st=vec2(fract(.5+atan(r.x,r.z)/6.28318530718),.5+asin(clamp(r.y,-1.,1.))/3.14159265359);
      gl_FragColor=texture2D(frame,st);}`));
    gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));gl.useProgram(program);
    const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
    const position=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
    this.texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,this.texture);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
    this.pose=gl.getUniformLocation(program,'pose');
  }
  draw(image,pose={}){const gl=this.gl;gl.useProgram(this.program);gl.bindTexture(gl.TEXTURE_2D,this.texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,image);gl.uniform3f(this.pose,pose.yaw || 0,pose.pitch || 0,Math.max(20,Math.min(170,pose.fov || 110)));gl.viewport(0,0,640,360);gl.drawArrays(gl.TRIANGLES,0,6);return this.canvas;}
}
let webSphereRenderer;
function sphereRenderer(){return webSphereRenderer ||= new WebSphere();}
function webSphericalStill(image,pose){if(!image.complete || !image.naturalWidth)return '';return sphereRenderer().draw(image,pose).toDataURL('image/jpeg',.85);}
