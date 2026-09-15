#!/usr/bin/env python3
"""Astrolabe ai-face receiver: accepts opencode task pushes, shows the current task."""

import argparse
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIELDS = ("source", "kind", "ts", "project", "session", "agent", "task", "display")

state_lock = threading.Lock()
latest = {}
history = deque(maxlen=50)

def normalize(payload):
    record = {k: payload[k] for k in FIELDS if k in payload}
    record["received_at"] = time.time()
    return record


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="refresh" content="30">
<title>Astrolabe</title>
<style>
  html, body { margin: 0; height: 100%; background: #0f1115; color: #e6e6e6;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  body { display: flex; align-items: center; justify-content: center; }
  .face { text-align: center; padding: 24px; max-width: 40em; }
  .emoji { font-size: 64px; line-height: 1; }
  h1 { font-size: 24px; letter-spacing: 1px; color: #e8762d; margin: 12px 0 4px; }
  .status { font-size: 16px; text-transform: uppercase; letter-spacing: 2px; }
  .status.running { color: #f2cf76; animation: pulse 1.6s ease-in-out infinite; }
  .status.busy { color: #f2cf76; }
  .status.idle, .status.done { color: #9aa0a6; }
  .task { font-size: 16px; color: #e6e6e6; margin: 18px 0 8px; white-space: pre-wrap; }
  .meta { font-size: 13px; color: #9aa0a6; }
  .age { font-size: 12px; color: #6b7280; margin-top: 14px; }
  .empty { color: #6b7280; font-size: 15px; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }
</style>
</head>
<body>
<div class="face" id="face"><p class="empty">astrolabe: waiting for opencode</p></div>
<script>
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
async function tick() {
  try {
    const r = await fetch("/state", { cache: "no-store" });
    const s = await r.json();
    const f = document.getElementById("face");
    if (!s || !s.session) { f.innerHTML = '<p class="empty">astrolabe: waiting for opencode</p>'; return; }
    const p = s.project || {}, a = s.agent || {}, t = s.task || {}, se = s.session || {};
    const status = esc(se.status || "idle");
    const age = s.received_at ? Math.round((Date.now() / 1000) - s.received_at) : null;
    f.innerHTML = `
      <div class="emoji">${esc(p.emoji || "")}</div>
      <h1>${esc(p.name || "opencode")}</h1>
      <div class="status ${status}">${status}</div>
      ${se.title ? `<div class="task">${esc(se.title)}</div>` : ""}
      ${t.text ? `<div class="task">${esc(t.text)}</div>` : ""}
      <div class="meta">${esc(a.name || "")}${a.model ? " · " + esc(a.model) : ""}${t.step ? " · step " + esc(t.step) : ""}</div>
      ${age !== null ? `<div class="age">updated ${age}s ago</div>` : ""}`;
  } catch (e) {}
}
setInterval(tick, 2000);
tick();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "opencode-astrolabe/0.1"

    def _send(self, code, body=b"", content_type="application/json"):
        self.send_response(code)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/face"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/state":
            with state_lock:
                body = json.dumps(latest).encode()
            self._send(200, body)
        elif path == "/history":
            with state_lock:
                body = json.dumps(list(history)).encode()
            self._send(200, body)
        elif path == "/health":
            self._send(200, b'{"ok":true}')
        elif path == "/favicon.ico":
            self._send(204)
        else:
            self._send(404, b'{"error":"not_found"}')

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/", "/face", "/ai-face", "/state"):
            self._send(404, b'{"error":"not_found"}')
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
        except (ValueError, json.JSONDecodeError) as e:
            self._send(400, json.dumps({"error": str(e)}).encode())
            return
        record = normalize(payload)
        global latest
        with state_lock:
            latest = record
            history.append(record)
        self._send(204)

    def log_message(self, fmt, *args):
        pass


def main():
    global history
    ap = argparse.ArgumentParser(description="opencode-astrolabe receiver")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--history", type=int, default=50)
    args = ap.parse_args()
    history = deque(maxlen=args.history)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"opencode-astrolabe listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
