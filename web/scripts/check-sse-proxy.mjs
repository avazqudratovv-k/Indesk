// Proves that the Next /api rewrite delivers a Server-Sent Events stream event by event, also when the browser
// allows gzip (the 4.1 finding: the rewrite compressed and buffered streams).
//
// It needs no real API, no secrets and no sign-in: a small fake upstream sends 6 events, 400 ms apart, and a copy of
// `next dev` is pointed at it with API_INTERNAL_URL. The client then reads the stream the way a browser does
// (Accept-Encoding: gzip, deflate, br) and records when each chunk of bytes arrives.
//
// Pass = the first bytes arrive within 1.5 s and the chunks are spread over the stream (not one burst at the end).
// Run from web/:  node scripts/check-sse-proxy.mjs
import { spawn } from "node:child_process";
import { createServer, request } from "node:http";

const UPSTREAM_PORT = 38017;
const NEXT_PORT = 38018;
const EVENTS = 6;
const GAP_MS = 400;

const upstream = createServer((req, res) => {
  if (!req.url?.startsWith("/api/runs/demo/events")) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no" });
  let sent = 0;
  const timer = setInterval(() => {
    sent += 1;
    res.write(`id: ${sent}\nevent: step\ndata: {"seq":${sent},"filler":"${"x".repeat(200)}"}\n\n`);
    if (sent === EVENTS) {
      clearInterval(timer);
      res.end();
    }
  }, GAP_MS);
  req.on("close", () => clearInterval(timer));
});
await new Promise((resolve) => upstream.listen(UPSTREAM_PORT, "127.0.0.1", resolve));

const next = spawn("npx", ["next", "dev", "-p", String(NEXT_PORT)], {
  cwd: new URL("..", import.meta.url),
  env: { ...process.env, API_INTERNAL_URL: `http://127.0.0.1:${UPSTREAM_PORT}`, NEXT_TELEMETRY_DISABLED: "1" },
  stdio: ["ignore", "pipe", "pipe"],
});
let nextLog = "";
next.stdout.on("data", (chunk) => (nextLog += chunk));
next.stderr.on("data", (chunk) => (nextLog += chunk));

function stop(code) {
  next.kill("SIGTERM");
  upstream.close();
  setTimeout(() => process.exit(code), 300).unref();
}

async function waitForNext() {
  for (let i = 0; i < 120; i += 1) {
    if (/Ready in|Local:/.test(nextLog)) return;
    if (next.exitCode !== null) throw new Error(`next dev exited early:\n${nextLog}`);
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`next dev did not start:\n${nextLog}`);
}

function readStream(acceptEncoding) {
  return new Promise((resolve, reject) => {
    const started = performance.now();
    const arrivals = [];
    const req = request({ host: "127.0.0.1", port: NEXT_PORT, path: "/api/runs/demo/events", headers: { "Accept-Encoding": acceptEncoding, Accept: "text/event-stream" } }, (res) => {
      res.on("data", (chunk) => arrivals.push({ ms: Math.round(performance.now() - started), bytes: chunk.length }));
      res.on("end", () => resolve({ encoding: res.headers["content-encoding"] ?? "none", status: res.statusCode, arrivals }));
    });
    req.on("error", reject);
    req.end();
  });
}

function judge(result) {
  const times = result.arrivals.map((a) => a.ms);
  const first = times[0] ?? Infinity;
  const spread = times.length > 1 ? times[times.length - 1] - times[0] : 0;
  const pass = result.status === 200 && first < 1500 && result.arrivals.length >= EVENTS - 1 && spread >= (EVENTS - 2) * GAP_MS;
  return { first, spread, chunks: result.arrivals.length, pass };
}

try {
  await waitForNext();
  // Warm the route once (the first request compiles the rewrite in dev).
  await readStream("identity").catch(() => {});
  let failed = false;
  for (const acceptEncoding of ["identity", "gzip, deflate, br"]) {
    const result = await readStream(acceptEncoding);
    const verdict = judge(result);
    failed ||= !verdict.pass;
    console.log(`${verdict.pass ? "PASS" : "FAIL"}  Accept-Encoding: ${acceptEncoding.padEnd(17)} status ${result.status}, content-encoding ${result.encoding}, ${verdict.chunks} chunks, first at ${verdict.first} ms, spread ${verdict.spread} ms`);
    console.log(`      arrivals (ms): ${result.arrivals.map((a) => a.ms).join(", ")}`);
  }
  stop(failed ? 1 : 0);
} catch (error) {
  console.error(String(error));
  stop(2);
}
