/**
 * URANO U5: real browser bridge functions, mocked HTTP transport only.
 * Tests web/companion.js + the actual upload functions from web/montara.js.
 * No video sources, server, Companion process or outbound network required.
 */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { webcrypto, createHash } = require("node:crypto");

const root = path.resolve(__dirname, "..");
const companionJS = fs.readFileSync(path.join(root, "web/companion.js"), "utf8");
const uiJS = fs.readFileSync(path.join(root, "web/montara.js"), "utf8");
const start = uiJS.indexOf("// URANO U3C: local original upload is retained");
const end = uiJS.indexOf("const KIND_LABEL =", start);
assert.ok(start !== -1 && end > start, "Review upload extraction boundaries");
const actualUploadJS = uiJS.slice(start, end);

const bytes = Buffer.alloc(180000);
for (let i = 0; i < bytes.length; ++i) bytes[i] = (i * 17 + 3) % 256;
const original = new File([bytes], "camera.mp4", { type: "video/mp4", lastModified: 1700000000000 });
const expectedFinger = createHash("sha256")
  .update(bytes.subarray(0, 65536))
  .update(bytes.subarray(bytes.length - 65536))
  .digest("hex");
const proxyData = Buffer.from("synthetic proxy response from Companion");
const proxyKey = "a".repeat(24);
const response = (body, status = 200) => ({
  status, ok: status >= 200 && status < 300,
  json: async () => body,
  blob: async () => new Blob([proxyData], { type: "video/mp4" }),
});

async function scenario(mode) {
  const calls = [];
  const uploads = [];
  const prompts = [];
  const entry = { name: original.name, kind: "uploading", removed: false, progress: 0 };
  const state = { uploads: 0, platform: "reel", files: [entry] };
  const ctx = vm.createContext({
    AbortSignal,
    AUDIO_NAME: /\.(wav|mp3|aiff?)$/i,
    Blob, File, AbortController, setTimeout, clearTimeout,
    crypto: webcrypto, state,
    console: { warn() {}, info() {} },
    window: { confirm: message => { prompts.push(message); return false; } },
    fetch: async (url, options = {}) => {
      assert.ok(url.startsWith("http://127.0.0.1:47820/"), "Only mock localhost");
      const endpoint = url.replace("http://127.0.0.1:47820", "");
      calls.push(endpoint);
      if (endpoint === "/health") return response({
        app: "montara-companion", ffmpeg: true, lossless_audio: true, audio_preview: true,
      });
      if (endpoint === "/locate") {
        const payload = JSON.parse(options.body);
        assert.equal(payload.name, original.name);
        assert.equal(payload.size, original.size);
        assert.equal(payload.fingerprint, expectedFinger, "Browser edge fingerprint");
        return mode === "missing" ? response({ error: "not found" }, 404) : response({ id: proxyKey });
      }
      if (endpoint === "/proxies") {
        assert.deepEqual(JSON.parse(options.body), { id: proxyKey, preview: false });
        return response({ id: proxyKey });
      }
      if (endpoint === "/proxies/" + proxyKey) {
        return mode === "failed" ? response({ status: "failed", error: "test FFmpeg failure" })
          : response({ status: "ready", progress: 1 });
      }
      if (endpoint === "/proxies/" + proxyKey + "/file") return response({});
      throw Error("Unexpected Companion route: " + endpoint);
    },
    XMLHttpRequest: class {
      constructor() { this.upload = {}; }
      open(method, url) { this.method = method; this.url = url; }
      setRequestHeader() {}
      send(file) { uploads.push({ route: this.url, file }); this.onloadend?.(); }
    },
    sendResumableUpload: async (file,progress,registered,cancelled,extra) => {
      uploads.push({route:"/montara/uploads",file,extra});
      return {videos:[{path:"/lab/camera.small.mp4",duration:1}]};
    },
    renderFiles: () => {}, remember: () => {},
    $: () => ({ checked: false }), videos: () => [], LONG_AUDIO_BYTES: 150000000,
  });
  vm.runInContext(companionJS, ctx, { filename: "web/companion.js", timeout: 1000 });
  vm.runInContext(actualUploadJS, ctx, { filename: "web/montara.js upload", timeout: 1000 });
  const companion = vm.runInContext("montaraCompanion", ctx);
  assert.ok(await companion.detect(), "Companion detection");
  await vm.runInContext("upload", ctx)(original, entry);
  await new Promise(resolve=>setImmediate(resolve));

  assert.ok(calls.includes("/locate"), mode + " locate called");
  assert.equal(calls.filter(p => p === "/locate").length, 1);
  if (mode === "success") {
    assert.deepEqual(calls, [
      "/health", "/locate", "/proxies",
      "/proxies/" + proxyKey, "/proxies/" + proxyKey + "/file",
    ]);
    assert.equal(uploads.length, 1, "Only one network transfer to server");
    assert.equal(uploads[0].route, "/montara/uploads");
    assert.equal(uploads[0].extra.video_preview,true);
    assert.equal(uploads[0].extra.original.fingerprint,expectedFinger);
    assert.equal(uploads[0].extra.original.name,original.name);
    assert.equal(uploads[0].file.name, "camera.small.mp4");
    assert.equal(uploads[0].file.size, proxyData.length);
    assert.notEqual(uploads[0].file, original, "Original never uploaded");
    assert.equal(entry.original.name, original.name);
    assert.equal(entry.original.size, original.size);
    assert.equal(entry.original.fingerprint, expectedFinger);
    assert.equal(entry.original.lastModified, original.lastModified);
    assert.equal(entry.small, true);
    assert.equal(prompts.length, 0);
  } else {
    assert.equal(uploads.length, 0, "No silent original transfer on " + mode);
    assert.equal(entry.kind, "error");
    assert.equal(prompts.length, 1, "Fallback always requires confirmation");
    assert.match(prompts[0], /ORIGINAL video/);
    assert.ok(!entry.small);
  }
  console.log("COMPANION_BROWSER_BRIDGE_PASS", mode, calls.length, uploads.length);
}

(async () => {
  await scenario("success");
  await scenario("missing");
  await scenario("failed");
  console.log("URANO_BROWSER_COMPANION_CONTRACT_PASS: 3 cases, actual browser functions, mocked HTTP");
})().catch(error => { console.error(error); process.exitCode = 1; });
