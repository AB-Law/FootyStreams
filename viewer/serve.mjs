// A tiny static file server for the viewer: node serve.mjs [port]. Local use only.
//
// It also takes one kind of request, `POST /api/trigger`, which the Channel page's control room uses
// to ask the running producer for breaking news or a guest. It only leaves a small JSON file in the
// channel's triggers folder (CHANNEL_DIR, default replays/channel); `uv run channel` does the rest.
import { createReadStream, existsSync, mkdirSync, renameSync, statSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL(".", import.meta.url)));
const port = Number(process.argv[2] ?? process.env.PORT ?? 5173);
const channel = resolve(root, process.env.CHANNEL_DIR ?? "replays/channel");
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".ndjson": "application/x-ndjson; charset=utf-8",
  ".map": "application/json",
};
const TRIGGER_KINDS = new Set(["breaking", "guest"]);
const MAX_BODY = 2048;
const MAX_TEXT = 140;

function reply(response, status, message) {
  response.writeHead(status, { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" }).end(message);
}

/** Read a small request body; null if it is too big. */
function readBody(request) {
  return new Promise((done) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
      if (body.length > MAX_BODY) {
        done(null);
        request.destroy();
      }
    });
    request.on("end", () => done(body));
    request.on("error", () => done(null));
  });
}

async function takeTrigger(request, response) {
  // A custom header cannot be sent by another site's page without a preflight this server never answers.
  if (request.headers["x-vpl-trigger"] !== "1") return reply(response, 403, "missing x-vpl-trigger header");
  const body = await readBody(request);
  if (body === null) return reply(response, 413, "too big");
  let trigger;
  try {
    trigger = JSON.parse(body);
  } catch {
    return reply(response, 400, "not JSON");
  }
  const text = typeof trigger?.text === "string" ? trigger.text.trim() : "";
  if (!TRIGGER_KINDS.has(trigger?.kind) || text === "" || text.length > MAX_TEXT) return reply(response, 400, "needs a kind (breaking or guest) and text of 1 to 140 characters");
  const folder = join(channel, "triggers");
  mkdirSync(folder, { recursive: true });
  const name = `${Date.now()}-${Math.floor(Math.random() * 1e6)}.json`;
  writeFileSync(join(folder, `${name}.tmp`), JSON.stringify({ kind: trigger.kind, text }) + "\n");
  renameSync(join(folder, `${name}.tmp`), join(folder, name));
  return reply(response, 200, "queued");
}

createServer((request, response) => {
  const path = decodeURIComponent(new URL(request.url ?? "/", "http://localhost").pathname);
  if (path === "/api/trigger") {
    if (request.method !== "POST") return reply(response, 405, "POST only");
    void takeTrigger(request, response);
    return;
  }
  const file = normalize(join(root, path === "/" ? "index.html" : path));
  if (!file.startsWith(root) || !existsSync(file) || !statSync(file).isFile()) {
    response.writeHead(404).end("not found");
    return;
  }
  response.writeHead(200, { "content-type": types[extname(file)] ?? "application/octet-stream", "cache-control": "no-store" });
  createReadStream(file).pipe(response);
}).listen(port, "127.0.0.1", () => console.log(`viewer on http://127.0.0.1:${port}/`));
