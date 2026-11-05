/**
 * URANO U3A — characterize the current original-upload fallback.
 * Runs actual uploadSmall/upload/uploadInParts functions from web/montara.js
 * under vm with ALL network calls mocked. No real files, uploads, or browser.
 *
 * Expected failures are documented observations, not desired future policy.
 * When U3B removes a fallback, update its expectation intentionally.
 */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "..", "web", "montara.js"), "utf8");
const start = source.indexOf("const WHOLE_FILE_ASK_BYTES =");
const end = source.indexOf("const KIND_LABEL =", start);
assert(start !== -1 && end > start, "Upload function boundaries changed: review test extraction");
const actualUploadCode = source.slice(start, end);

async function scenario(name, config) {
  const recorded = [];
  const state = {uploads: 0, platform: "reel", files: []};
  const file = {name: config.name || "original.mov", size: config.mb * 1024 * 1024, type: "video/quicktime"};
  const entry = {name: file.name, removed: false, progress: 0};
  const companion = {
    info: config.companion ? {ffmpeg:true} : null,
    helps: () => true,
    isAudio: () => false,
    smallVersion: async () => {
      if (config.result === "throw") throw new Error("simulated FFmpeg error");
      if (config.result === "missing") return {missing:true};
      if (config.result === "proxy") return {
        file:{name:"original.small.mp4",size:2*1024*1024,type:"video/mp4"},
        preview:false, original:{name:file.name,size:file.size,fingerprint:"mock"},
      };
      return null; // failed/skipped/unavailable
    },
  };
  class FakeXHR {
    constructor() {this.upload = {};}
    open(method,url) {this.method=method;this.url=url;}
    setRequestHeader(){}
    send(payload) {recorded.push({route:this.url,name:payload.name,size:payload.size});}
  }
  const ctx = vm.createContext({
    state, montaraCompanion:companion, XMLHttpRequest:FakeXHR,
    sendResumableUpload:async payload=>{
      recorded.push({route:"/montara/uploads",name:payload.name,size:payload.size});
      return {videos:[{path:"/lab/"+payload.name,duration:1}]};
    },
    renderFiles:()=>{}, remember:()=>{}, $:()=>({checked:false}),
    LONG_AUDIO_BYTES:100000000,videos:()=>[],console:{warn:()=>{},info:()=>{}},
    fetch:()=>{throw Error("Unmocked network call");},
  });
  vm.runInContext(actualUploadCode,ctx,{filename:"web/montara.js extract",timeout:1500});
  await vm.runInContext("upload",ctx)(file,entry);
  // resumable uploader is asynchronous, but no I/O: settle its continuation.
  await new Promise(resolve=>setImmediate(resolve));
  const expected = config.expected;
  const sent = recorded.length ? recorded[0] : null;
  assert.equal(recorded.length,expected==="none"?0:1,name+" number of transfers");
  if (expected==="original") {
    assert.equal(sent.size,file.size,name+" original bytes");
    assert.equal(sent.name,file.name,name+" original name");
  }
  if (expected==="proxy") {
    assert.equal(sent.name,"original.small.mp4",name+" proxy name");
    assert.equal(sent.size,2*1024*1024,name+" proxy size");
  }
  if (config.route) assert.equal(sent.route,config.route,name+" path");
  if (expected==="none") assert.equal(entry.kind,"error",name+" blocking error");
  console.log("U3A_CHARACTERIZED",name,expected,sent?.route || "no transfer");
}
(async()=>{
  await scenario("no_companion_10MiB",{companion:false,mb:10,expected:"original",route:"/montara/uploads"});
  await scenario("no_companion_300MiB",{companion:false,mb:300,expected:"original",route:"/montara/uploads"});
  await scenario("companion_missing_10MiB",{companion:true,mb:10,result:"missing",expected:"original",route:"/montara/uploads"});
  await scenario("companion_missing_300MiB",{companion:true,mb:300,result:"missing",expected:"none"});
  await scenario("companion_failed_300MiB",{companion:true,mb:300,result:"null",expected:"original",route:"/montara/uploads"});
  await scenario("companion_ffmpeg_throws_300MiB",{companion:true,mb:300,result:"throw",expected:"original",route:"/montara/uploads"});
  await scenario("companion_success_300MiB",{companion:true,mb:300,result:"proxy",expected:"proxy",route:"/api/v1/wizard/upload"});
  console.log("URANO_U3A_BASELINE_PASS: 7 fully mocked characterization scenarios; current fallback is intentionally present.");
})().catch(error=>{console.error(error);process.exitCode=1;});
