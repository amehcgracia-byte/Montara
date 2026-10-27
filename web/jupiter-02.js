"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const FILE = "proyecto-jupiter02.json";
  const MAGIC = "montara-jupiter02-lab-v1";
  const DB = "montara-jupiter02-folder";
  let folder = null, files = [], selected = null, mark = null, objectUrl = null;
  let clips = [];
  const announce = (s) => { $("status").textContent = s; };
  const show = () => { $("cuts").textContent = JSON.stringify({version:1, clips},null,2); };
  const controls = () => {
    $("write").disabled = !folder;
    $("save").disabled = !folder;
    $("load").disabled = !folder;
    $("start").disabled = !selected;
    $("end").disabled = !selected || mark === null;
  };
  const dbOpen = () => new Promise((resolve,reject) => {
    const request = indexedDB.open(DB,1);
    request.onupgradeneeded = () => request.result.createObjectStore("handles");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  async function handleStore(value,remove=false) {
    const db = await dbOpen();
    try {
      return await new Promise((resolve,reject) => {
        const tx=db.transaction("handles",remove||value?"readwrite":"readonly");
        const store=tx.objectStore("handles");
        const request=remove?store.delete("folder"):value?store.put(value,"folder"):store.get("folder");
        let found;
        if(!remove&&!value) request.onsuccess=()=>{found=request.result;};
        tx.oncomplete=()=>resolve(found);
        tx.onerror=()=>reject(tx.error);
        tx.onabort=()=>reject(tx.error);
      });
    } finally { db.close(); }
  }
  function releaseMedia() {
    $("player").pause();
    $("player").removeAttribute("src");
    $("player").load();
    if(objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    selected = null;
    mark = null;
  }
  async function selectVideo(index) {
    releaseMedia();
    const entry=files[index];
    if(!entry) {controls();return;}
    const file=await entry.handle.getFile();
    objectUrl=URL.createObjectURL(file);
    $("player").src=objectUrl;
    selected=entry.path;
    $("current").textContent=entry.path+" ("+(file.size/1048576).toFixed(2)+" MiB)";
    controls();
  }
  async function enumerate(handle) {
    releaseMedia();
    files=[];
    const stack=[{dir:handle,path:""}];
    while(stack.length) {
      const {dir,path}=stack.pop();
      for await(const child of dir.values()) {
        // Do not enumerate anything created by the test lab.
        if(child.kind==="directory") {
          if(path==="" && child.name==="Montara") continue;
          stack.push({dir:child,path:path?path+"/"+child.name:child.name});
        } else if(child.kind==="file" && /\.(mp4|webm|mov|mkv)$/i.test(child.name)) {
          files.push({handle:child,path:path?path+"/"+child.name:child.name});
          if(files.length>10000) throw Error("Limite de 10000 videos alcanzado");
        }
      }
    }
    files.sort((a,b)=>a.path.localeCompare(b.path));
    const list=$("videos");
    list.replaceChildren();
    for(let i=0;i<files.length;i++) {
      const option=document.createElement("option");
      option.value=String(i); option.textContent=files[i].path; list.append(option);
    }
    $("count").textContent=files.length+" videos encontrados (0 bytes subidos).";
    if(files.length) await selectVideo(0);
    controls();
  }
  async function readPermission(handle) {
    if(await handle.queryPermission({mode:"read"})==="granted") return true;
    return await handle.requestPermission({mode:"read"})==="granted";
  }
  async function bindFolder(handle) {
    if(!(await readPermission(handle))) throw Error("Permiso de lectura denegado.");
    folder=handle;
    await handleStore(handle);
    await enumerate(handle);
    announce("Carpeta "+handle.name+" lista. Los originales son solo lectura por politica de Montara.");
  }
  async function writePermission() {
    if(!folder) throw Error("Primero selecciona carpeta.");
    if(await folder.queryPermission({mode:"readwrite"})==="granted") return true;
    return await folder.requestPermission({mode:"readwrite"})==="granted";
  }
  async function projectFolder(create=false) {
    if(!folder) throw Error("No hay carpeta.");
    return await folder.getDirectoryHandle("Montara",{create});
  }
  async function projectFile(create=false) {
    const dir=await projectFolder(create);
    return await dir.getFileHandle(FILE,{create});
  }
  $("pick").onclick=async()=>{
    try{
      if(!window.showDirectoryPicker) throw Error("Utiliza Chrome o Edge con HTTPS o localhost.");
      await bindFolder(await showDirectoryPicker({mode:"read"}));
    }catch(e){announce(e.name==="AbortError"?"Seleccion cancelada.":e.message);}
  };
  $("reopen").onclick=async()=>{
    try {
      const saved=await handleStore();
      if(!saved) throw Error("No se ha recordado ninguna carpeta.");
      await bindFolder(saved);
      // Read without creating anything.
      try { await loadProject(false); } catch(e) {
        if(e.name!=="NotFoundError") announce("Carpeta abierta. Proyecto: "+e.message);
      }
    } catch(e) { announce(e.message); }
  };
  $("write").onclick=async()=>{
    try { announce(await writePermission()?"Escritura autorizada. Ningun original sera modificado.":"Permiso de escritura denegado."); }
    catch(e) { announce(e.message); }
  };
  $("videos").onchange=async()=>{try {await selectVideo(Number($("videos").value));}catch(e){announce(e.message);}};
  $("start").onclick=()=>{if(!selected)return;mark=Number($("player").currentTime.toFixed(3));controls();announce("Inicio marcado en "+mark+"s");};
  $("end").onclick=()=>{
    if(!selected||mark===null)return;
    const end=Number($("player").currentTime.toFixed(3));
    if(!Number.isFinite(end)||end<=mark){announce("El final debe ser posterior al inicio.");return;}
    clips.push({source:selected,start:mark,end});
    mark=null;controls();show();announce("Corte anadido en memoria. Guardalo en el proyecto si quieres conservarlo.");
  };
  async function loadProject(notify=true) {
    const handle=await projectFile(false);
    const raw=await (await handle.getFile()).text();
    const parsed=JSON.parse(raw);
    if(parsed.app!==MAGIC || !Array.isArray(parsed.clips) || parsed.clips.length>10000)
      throw Error("Este archivo no es un proyecto Jupiter-02 valido.");
    if(!parsed.clips.every(c=>typeof c.source==="string" && c.source.length<2048 && Number.isFinite(c.start)&&Number.isFinite(c.end)&&c.start>=0&&c.end>c.start))
      throw Error("Cortes invalidos; no se ha cargado el archivo.");
    clips=parsed.clips.map(c=>({source:c.source,start:c.start,end:c.end}));
    show();
    if(notify)announce("Proyecto recuperado del disco: "+clips.length+" cortes.");
  }
  $("save").onclick=async()=>{
    try {
      if(!await writePermission()) throw Error("No has concedido escritura.");
      // Never replace unknown data: refuse to write over a foreign file.
      let prior=null;
      try { prior=await projectFile(false); }
      catch(e){if(e.name!=="NotFoundError")throw e;}
      if(prior) {
        let old;
        try {old=JSON.parse(await (await prior.getFile()).text());}
        catch(e){throw Error("El archivo existente no es JSON valido y no sera sustituido.");}
        if(old.app!==MAGIC)throw Error("El archivo existente no pertenece a este laboratorio; no se sobrescribe.");
      }
      const target=prior||await projectFile(true);
      const writer=await target.createWritable({keepExistingData:false});
      try {
        await writer.write(JSON.stringify({app:MAGIC,version:1,clips},null,2));
        await writer.close();
      }catch(e){try{await writer.abort();}catch(_){}throw e;}
      announce("Proyecto guardado en Montara/"+FILE+" ("+clips.length+" cortes).");
    } catch(e){announce("No se guardo el proyecto: "+e.message);}
  };
  $("load").onclick=async()=>{try{await loadProject();}catch(e){announce("No se pudo recuperar: "+e.message);}};
  $("forget").onclick=async()=>{
    try {await handleStore(null,true);releaseMedia();folder=null;files=[];$("videos").replaceChildren();clips=[];show();controls();announce("Carpeta olvidada en este navegador. Nada borrado del disco.");}
    catch(e){announce(e.message);}
  };
  show();controls();
  if(!window.showDirectoryPicker)announce("API de carpetas no disponible: usa Chrome o Edge en localhost/HTTPS.");
})();
