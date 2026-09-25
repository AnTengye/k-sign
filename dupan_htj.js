"use strict";

// Browserless runner for the official Baidu Sofire web SDK. The Python caller
// supplies only the current device ID/UA; credentials never enter this process.
const fs = require("node:fs");
const jsdom = require("jsdom");
const { JSDOM, VirtualConsole } = jsdom;

const SDK_URL = "https://sofire.bdstatic.com/js/dfxaf3.js";
const AID = "13655";
const DATA_APP = Buffer.from(JSON.stringify({
  app_key: AID,
  app_view: "promote",
  browser_url: "https://sofire.baidu.com/data/ua/ab.json",
  form_desc: "",
  send_interval: 50,
  send_method: 3,
})).toString("base64");
const ALLOWED_HOSTS = new Set([
  "sofire.bdstatic.com", "sfp.safe.baidu.com", "sofire.baidu.com",
  "safe.cdn.bcebos.com",
]);

function checkURL(url) {
  const target = new URL(url);
  if (target.protocol !== "https:" || !ALLOWED_HOSTS.has(target.hostname)) {
    throw new Error("SDK requested a URL outside the approved Baidu hosts");
  }
}

function resourcesFor(input) {
  if (jsdom.ResourceLoader) {
    return new (class extends jsdom.ResourceLoader {
      fetch(url, options) {
        checkURL(url);
        return super.fetch(url, options);
      }
    })({ userAgent: input.userAgent,
      ...(input.proxy ? { proxy: input.proxy } : {}) });
  }
  // jsdom 30 uses an undici dispatcher for scripts and XHR instead.
  const resources = { userAgent: input.userAgent,
    interceptors: [jsdom.requestInterceptor(request => checkURL(request.url))] };
  if (input.proxy) {
    const { ProxyAgent } = require("undici");
    resources.dispatcher = new ProxyAgent(input.proxy);
  }
  return resources;
}

function readInput() {
  const bytes = fs.readFileSync(0);
  if (bytes.length > 16384) throw new Error("HTJ input is too large");
  const input = JSON.parse(bytes.toString("utf8"));
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("invalid HTJ input");
  }
  if (typeof input.cuid !== "string" || !input.cuid || input.cuid.length > 2048 ||
      typeof input.userAgent !== "string" || !input.userAgent ||
      input.userAgent.length > 2048 || /[\r\n\0]/.test(input.cuid + input.userAgent)) {
    throw new Error("invalid HTJ device profile");
  }
  if (input.proxy != null) {
    if (typeof input.proxy !== "string") throw new Error("invalid HTJ proxy");
    const proxy = new URL(input.proxy);
    if (proxy.protocol !== "http:" || proxy.username || proxy.password) {
      throw new Error("HTJ proxy must be an unauthenticated HTTP proxy");
    }
  }
  return input;
}

async function createToken(input) {
  const loader = resourcesFor(input);
  const virtualConsole = new VirtualConsole();
  const dom = new JSDOM("<!doctype html><html><head></head><body></body></html>", {
    url: "https://pan.baidu.com/operation/activitys/taskSystem/growth",
    resources: loader,
    runScripts: "dangerously",
    pretendToBeVisual: true,
    virtualConsole,
  });
  try {
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("HTJ SDK timed out")), 20000);
      const finish = (error, value) => {
        clearTimeout(timer);
        if (error) reject(error);
        else resolve(value);
      };
      const script = dom.window.document.createElement("script");
      script.src = SDK_URL;
      script.onerror = () => finish(new Error("HTJ SDK download failed"));
      script.onload = () => {
        try {
          const sdk = dom.window.xaf;
          if (!sdk || !sdk.init({ aid: AID, dataApp: DATA_APP }) || !sdk.coreDfXaf) {
            throw new Error("HTJ SDK initialization failed");
          }
          sdk.report({ c: input.cuid, aid: AID, complete: result => {
            if (!result || result.code !== 0 ||
                typeof result.jt !== "string" || !result.jt || result.jt.length > 20000) {
              finish(new Error("HTJ SDK returned no valid token"));
              return;
            }
            finish(null, { jt: result.jt, version: String(sdk.version || "") });
          } });
        } catch (error) {
          finish(error);
        }
      };
      dom.window.document.head.appendChild(script);
    });
  } finally {
    dom.window.close();
  }
}

createToken(readInput()).then(result => {
  process.stdout.write(JSON.stringify(result));
}).catch(error => {
  // Never include SDK, proxy, device or account data in the caller's logs.
  const safe = /^(HTJ SDK|HTJ input|invalid HTJ|SDK requested)/.test(error.message)
    ? error.message : "HTJ generation failed";
  const detail = process.env.DUPAN_HTJ_DEBUG === "1"
    ? ` (${error.name}, ${error.code || error.cause?.code || "unknown"})` : "";
  process.stderr.write(safe + detail + "\n");
  process.exitCode = 1;
});
