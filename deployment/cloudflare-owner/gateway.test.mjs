import assert from "node:assert/strict";
import test from "node:test";
import gateway, {OWNER_HOST} from "./worker.mjs";

const ORIGIN = "https://" + OWNER_HOST;

function upstreamMock(onRequest, response) {
  return {
    OWNER_PRIVATE_API: {
      async fetch(request) {
        onRequest(request);
        return response || new Response("private", {
          status: 200,
          headers: {"content-type": "text/plain"}
        });
      }
    }
  };
}

test("unconfigured tunnel and service fail closed: no insecure fallback", async () => {
  const result = await gateway.fetch(new Request(ORIGIN + "/"), {});
  assert.equal(result.status, 503);
  assert.match(await result.text(), /not provisioned/i);
});

test("public hostname is pinned; classic editor and external paths blocked", async () => {
  const mock = upstreamMock(() => { throw Error("Backend must never be called"); });
  for (const target of [
    "https://bad.example.test/",
    "http://" + OWNER_HOST + "/",
    ORIGIN + "/api/v1/project",
    ORIGIN + "/montara/samples",
    ORIGIN + "/../api/v1/project",
    ORIGIN + "/urano/v1/%2fapi",
  ]) {
    const response = await gateway.fetch(new Request(target), mock);
    assert.ok([404, 421].includes(response.status), target + ": " + response.status);
  }
});

test("Cloudflare IP metadata and spoofed forwarded values never reach WSGI", async () => {
  let called = 0;
  const env = upstreamMock(async (req) => {
    called++;
    assert.equal(new URL(req.url).hostname, OWNER_HOST);
    assert.equal(req.headers.get("x-forwarded-proto"), null);
    assert.equal(req.headers.get("x-forwarded-host"), null);
    assert.equal(req.headers.get("cf-connecting-ip"), null);
    assert.equal(req.headers.get("x-real-ip"), null);
    assert.equal(req.headers.get("x-montara-owner"), null);
    assert.equal(req.headers.get("cookie"), "a=b");
  });
  const response = await gateway.fetch(new Request(ORIGIN + "/urano/v1/projects", {
    headers: {
      "X-Forwarded-Proto": "http",
      "X-Forwarded-Host": "evil.example.test",
      "CF-Connecting-IP": "1.2.3.4",
      "X-Real-IP": "8.8.8.8",
      "X-Montara-Owner": "forged-user",
      Cookie: "a=b"
    }
  }), env);
  assert.equal(response.status, 200);
  assert.equal(called, 1);
});

test("Google OAuth redirect and secure session cookies are preserved", async () => {
  const env = upstreamMock((req) => {
    assert.equal(req.url, "http://" + OWNER_HOST + "/urano/v1/google/start");
  }, new Response(null, {
    status: 302,
    headers: {
      Location: "https://accounts.google.com/o/oauth2/v2/auth?state=synthetic",
      "Set-Cookie": "__Host-montara-oidc-flow=synthetic; Secure; HttpOnly; Path=/",
    }
  }));
  const response = await gateway.fetch(
    new Request(ORIGIN + "/urano/v1/google/start"), env);
  assert.equal(response.status, 302);
  assert.match(response.headers.get("Location"), /accounts.google.com/);
  assert.match(response.headers.get("Set-Cookie"), /Secure/);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
});

test("same-origin CSRF writes can reach private API, not cross-origin writes", async () => {
  const env = upstreamMock(async (req) => {
    assert.equal(req.method, "POST");
    assert.equal(req.headers.get("origin"), ORIGIN);
    assert.equal(req.headers.get("x-urano-csrf"), "fake-for-contract");
    assert.equal(await req.text(), "{\"title\":\"Test\"}");
  });
  const allowed = new Request(ORIGIN + "/urano/v1/projects", {
    method: "POST",
    headers: {"Content-Type": "application/json",
              "Origin": ORIGIN, "X-Urano-CSRF": "fake-for-contract"},
    body: '{"title":"Test"}'
  });
  assert.equal((await gateway.fetch(allowed, env)).status, 200);
  const invalid = new Request(ORIGIN + "/urano/v1/projects", {
    method: "POST", headers: {Origin: "https://evil.example.test"},
    body: "bad"
  });
  assert.equal((await gateway.fetch(invalid, env)).status, 403);
});

test("backend failure returns an opaque 503 without host, secrets or stack", async () => {
  const env = upstreamMock(() => { throw Error("private file /home/secret"); });
  const result = await gateway.fetch(new Request(ORIGIN + "/healthz"), env);
  assert.equal(result.status, 503);
  assert.doesNotMatch(await result.text(), /\/home\/secret/);
});
