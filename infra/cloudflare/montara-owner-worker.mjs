/**
 * MONTARA C8 Google-owner gateway — Cloudflare Workers VPC Service.
 *
 * Dedicated URL: https://montara-owner.memoriainvalida001.workers.dev
 * Service binding OWNER_PRIVATE_API maps EXCLUSIVELY to 127.0.0.1:8115
 * on fgardel00's VM via a named, private Cloudflare Tunnel.
 *
 * No Worker-to-public-IP fetch, no redirect to the classic editor, no
 * identity headers, no Google client secret at the edge. All Google ID
 * validation and project ownership remain in the reviewed Python backend.
 *
 * Until the VPC Service exists, every private request fails closed as 503.
 */
export const OWNER_HOST = "montara-owner.memoriainvalida001.workers.dev";
const OWNER_ORIGIN = "https://" + OWNER_HOST;
const PRIVATE_HTTP_ORIGIN = "http://" + OWNER_HOST;

const REQUEST_HEADERS = [
  "accept", "accept-language", "content-type", "cookie", "origin",
  "referer", "user-agent", "x-urano-csrf", "x-urano-proxy-sha256",
  "x-zucker-filename", "upload-offset", "x-montara-engine-generation", "range",
  "x-urano-original-claim", "x-urano-signed-receipt"
];

function denied(status, message) {
  return new Response(message, {
    status,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "x-robots-tag": "noindex, nofollow",
      "referrer-policy": "no-referrer"
    }
  });
}

export default {
  async fetch(request, env) {
    let url;
    try { url = new URL(request.url); }
    catch { return denied(400, "Invalid URL"); }

    // Same fixed origin used by Google callback, sessions and Companion.
    if (url.protocol !== "https:" || url.host !== OWNER_HOST) {
      return denied(421, "Incorrect beta hostname");
    }
    const pathname = url.pathname;
    if (
      !["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"].includes(request.method)
      || /%2f|%5c|%00|\\/i.test(pathname)
      || pathname.includes("//")
      || !(
        pathname === "/" || pathname === "/healthz" ||
        pathname.startsWith("/urano/v1/")
      )
    ) {
      return denied(404, "Not found");
    }
    if (!env || typeof env.OWNER_PRIVATE_API?.fetch !== "function") {
      return denied(503, "Private beta not provisioned");
    }

    const headers = new Headers();
    for (const key of REQUEST_HEADERS) {
      const value = request.headers.get(key);
      if (value !== null) headers.set(key, value);
    }
    // Cloudflare may itself add CF-Connecting-IP and X-Forwarded-*
    // headers on genuine requests. Ignore them COMPLETELY: only headers
    // from the explicit allowlist above go to our local WSGI boundary.
    // Never let browser- or edge-supplied origin metadata assert HTTPS.
    if (headers.has("origin") && headers.get("origin") !== OWNER_ORIGIN) {
      return denied(403, "Cross-origin writes unavailable");
    }

    // The URL host populates Host for the VPC Service, while routing to the
    // pre-registered 127.0.0.1:8115 target. No SSRF via user-supplied URLs.
    const upstream = PRIVATE_HTTP_ORIGIN + pathname + url.search;
    const hasBody = !["GET", "HEAD"].includes(request.method);
    const options = {
      method: request.method,
      headers,
      redirect: "manual"
    };
    if (hasBody && request.body) {
      options.body = request.body;
      options.duplex = "half";
    }
    try {
      const response = await env.OWNER_PRIVATE_API.fetch(
        new Request(upstream, options)
      );
      // Preserve Set-Cookie from the verified Google OIDC flow.
      const responseHeaders = new Headers(response.headers);
      responseHeaders.set("cache-control", "no-store");
      responseHeaders.set("x-robots-tag", "noindex, nofollow");
      responseHeaders.set("x-content-type-options", "nosniff");
      responseHeaders.set("referrer-policy", "no-referrer");
      return new Response(response.body, {
        status: response.status,
        headers: responseHeaders
      });
    } catch {
      // Never reveal tunnel identifiers, network topology, tokens, paths.
      return denied(503, "Private beta temporarily unavailable");
    }
  }
};
