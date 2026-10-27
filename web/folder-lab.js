"use strict";
(() => {
  const allowedVideo = new Set(["mp4","mov","mkv","webm","mts","m2ts"]);
  const allowedAudio = new Set(["wav","mp3","flac","aif","aiff","m4a","ogg"]);
  const status = document.querySelector("#status");
  const results = document.querySelector("#results");
  const supported = Boolean(window.showDirectoryPicker && window.indexedDB);
  const report = (message) => { status.textContent = message; };
  const db = () => new Promise((resolve,reject) => {
    const request = indexedDB.open("montara-folder-lab", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("handles");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  const save = async (handle) => {
    const database = await db();
    try {
      await new Promise((resolve,reject) => {
        const tx=database.transaction("handles","readwrite");
        tx.objectStore("handles").put(handle,"chosen");
        tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);
      });
    } finally { database.close(); }
  };
  const stored = async () => {
    const database=await db();
    try {
      return await new Promise((resolve,reject) => {
        const tx=database.transaction("handles","readonly");
        const request=tx.objectStore("handles").get("chosen");
        request.onsuccess=()=>resolve(request.result);
        request.onerror=()=>reject(request.error);
      });
    } finally { database.close(); }
  };
  const forget = async () => {
    const database=await db();
    try {
      await new Promise((resolve,reject)=>{
        const tx=database.transaction("handles","readwrite");
        tx.objectStore("handles").delete("chosen");
        tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);
      });
    } finally { database.close(); }
  };
  async function inventory(folder) {
    const start=performance.now();
    let count=0, total=0, videos=0, audio=0, skipped=0;
    const stack=[folder];
    while(stack.length) {
      const dir=stack.pop();
      for await(const child of dir.values()) {
        if(child.kind==="directory") { stack.push(child); continue; }
        if(child.kind!=="file") continue;
        const suffix=child.name.split(".").pop().toLowerCase();
        if(!allowedVideo.has(suffix) && !allowedAudio.has(suffix)) { skipped++; continue; }
        if(++count>100000) throw Error("More than 100,000 media files: inventory stopped.");
        // File metadata only, never call arrayBuffer(), stream(), fetch(), or upload().
        const file=await child.getFile();
        total+=file.size;
        if(allowedVideo.has(suffix)) videos++; else audio++;
      }
    }
    return {video_files:videos,audio_files:audio,source_bytes:total,ignored_files:skipped,
      inventory_ms:Number((performance.now()-start).toFixed(2)),bytes_uploaded:0,
      scope:"metadata only; this does not measure transcoding or editing"};
  }
  async function run(handle) {
    report("Indexing locally — no media upload…");
    results.textContent=JSON.stringify(await inventory(handle),null,2);
    report("Indexed. Folder permission belongs to your browser.");
  }
  document.querySelector("#pick").onclick=async()=>{
    try {
      if(!supported) throw Error("Use a compatible desktop browser supporting showDirectoryPicker and IndexedDB.");
      const handle=await showDirectoryPicker({mode:"read"});
      await save(handle);
      await run(handle);
    } catch(error) { report(error.name==="AbortError"?"Selection cancelled.":error.message); }
  };
  document.querySelector("#reopen").onclick=async()=>{
    try {
      if(!supported) throw Error("Folder handles are not supported here.");
      const handle=await stored();
      if(!handle) throw Error("No folder selected in this browser.");
      const state=await handle.queryPermission({mode:"read"});
      if(state!=="granted" && await handle.requestPermission({mode:"read"})!=="granted")
        throw Error("Permission not granted.");
      await run(handle);
    } catch(error) { report(error.message); }
  };
  document.querySelector("#clear").onclick=async()=>{
    try { if(supported) await forget();results.textContent="";report("Saved folder handle cleared."); }
    catch(error) { report(error.message); }
  };
  if(!supported) report("Folder handle API unavailable: try a compatible desktop Chromium browser.");
})();
