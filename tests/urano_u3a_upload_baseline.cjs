/**
 * URANO U3C — retain original uploads exclusively after user consent.
 * Runs actual uploadSmall/upload/uploadInParts functions from web/montara.js
 * under vm with ALL network calls mocked. No real files, uploads, or browser.
 *
 * Original U3A baseline is documented in docs/lab; these are now the
 * U3B desired-policy assertions. No actual bytes leave this test.
 */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "..", "web", "montara.js"), "utf8");
const start = source.indexOf("// URANO U3C: local original upload is retained");
const end = source.indexOf("const KIND_LABEL =", start);
assert(start !== -1 && end > start, "Upload function boundaries changed: review test extraction");
const actualUploadCode = source.slice(start, end);

async function scenario(name, config) {
  const recorded = [];
  const prompts = [];
  const state = {uploads: 0, platform: "reel", files: []};
  const fileName = config.name || "original.mov";
  const file = {name: fileName, size: config.mb * 1024 * 1024,
    type: /\.(wav|aiff?|mp3)$/i.test(fileName) ? "audio/wav" : "video/quicktime"};
  const entry = {name: file.name, removed: false, progress: 0};
  const companion = {
    info: config.companion ? {ffmpeg:true} : null,
    helps: () => true,
    isVideo: file => /video\//.test(file.type) || /\.(mp4|mov|mkv|avi)$/i.test(file.name),
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
    window:{confirm:message=>{prompts.push(message);return Boolean(config.approveOriginal);}},
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
  if (expected==="none") assert.match(entry.error,/Companion|not found/i,name+" helpful guidance");
  if (config.expectedPrompt !== undefined) assert.equal(prompts.length,config.expectedPrompt,name+" prompt count");
  if (prompts.length) { assert.match(prompts[0], /ORIGINAL video.*MiB/i, name+" consent size"); assert.ok(prompts[0].includes("server storage"), name+" consent costs"); }
  console.log("U3C_POLICY",name,expected,sent?.route || "no transfer");
}
(async()=>{
  await scenario("no_companion_2MiB",{companion:false,mb:2,expected:"none"});
  await scenario("no_companion_10MiB",{companion:false,mb:10,expected:"none"});
  await scenario("no_companion_300MiB",{companion:false,mb:300,expected:"none"});
  await scenario("companion_missing_10MiB",{companion:true,mb:10,result:"missing",expected:"none"});
  await scenario("companion_missing_300MiB",{companion:true,mb:300,result:"missing",expected:"none"});
  await scenario("companion_failed_300MiB",{companion:true,mb:300,result:"null",expected:"none"});
  await scenario("companion_ffmpeg_throws_300MiB",{companion:true,mb:300,result:"throw",expected:"none"});
  await scenario("companion_success_300MiB",{companion:true,mb:300,result:"proxy",expected:"proxy",route:"/api/v1/wizard/upload"});
  // Manual consent must retain the old upload capability, without silent fallback.
  await scenario("manual_no_companion_2MiB",{companion:false,mb:2,approveOriginal:true,expectedPrompt:1,expected:"original",route:"/api/v1/wizard/upload"});
  await scenario("manual_no_companion_300MiB",{companion:false,mb:300,approveOriginal:true,expectedPrompt:1,expected:"original",route:"/montara/uploads"});
  await scenario("manual_failed_proxy_300MiB",{companion:true,mb:300,result:"throw",approveOriginal:true,expectedPrompt:1,expected:"original",route:"/montara/uploads"});
  // Stage audio routing remains unchanged; removing that path needs its own review.
  await scenario("legacy_stage_audio_10MiB",{companion:false,name:"session.wav",mb:10,expected:"original",route:"/montara/uploads"});
  console.log("URANO_U3C_MANUAL_FALLBACK_PASS: 12 mocked cases; silent original uploads blocked, explicit test consent retains upload.");
})().catch(error=>{console.error(error);process.exitCode=1;});
