# opencode-astrolabe

Push the current OpenCode task to an Astrolabe face. Two small pieces:

- `plugin/astrolabe.ts` — an OpenCode plugin that watches session events and POSTs the current task as a compact `ai-face` payload.
- `receiver/astrolabe_server.py` — a zero-dependency Python receiver that accepts those pushes and renders the task as a live face page.

```text
opencode serve ──plugin──▶ POST :8090 ──▶ receiver ──▶ browser / rear display
```

Maintained by [Castalia Institute](https://github.com/CastaliaInstitute). Related: [mynah-ai](https://github.com/CastaliaInstitute/mynah-ai) (bridge with `/v1/astrolabe/state` and BLE relay), [mynah-opencode](https://github.com/CastaliaInstitute/mynah-opencode) (tailnet task navigation).

## Payload contract

The plugin POSTs JSON to `url + path` (default `http://127.0.0.1:8090/`):

```json
{
  "source": "opencode",
  "kind": "ai-face",
  "ts": 1760000000000,
  "project": { "name": "f101-kali", "emoji": "📱" },
  "session": { "id": "ses_...", "title": "Port NetHunter kernel", "status": "running" },
  "agent":   { "name": "build", "model": "...", "provider": "..." },
  "task":    { "text": "current task text (≤300 chars)", "partType": "step-start", "partState": "pending", "step": 3 },
  "display": "📱 Port NetHunter kernel · running · build · ..."
}
```

The receiver accepts any object POSTed to `/`, `/face`, `/ai-face`, or `/state`; unknown fields are dropped. It answers:

| Endpoint | Method | Purpose |
|---|---|---|
| `/` or `/face` | GET | Live face page (polls `/state` every 2 s) |
| `/state` | GET | Latest payload as JSON |
| `/history` | GET | Recent payloads (default 50) |
| `/health` | GET | Connectivity check |

## Plugin install

Copy `plugin/astrolabe.ts` into `~/.config/opencode/plugin/` (all projects) or `<project>/.opencode/plugin/` (one project), then opt in per project via `opencode.json`:

```json
{
  "emoji": "📱",
  "astrolabe": {
    "enabled": true,
    "url": "http://127.0.0.1:8090",
    "path": "/",
    "min_interval": 250
  }
}
```

The plugin is silent by default (`enabled: false`); a disabled or unreachable receiver never breaks OpenCode. Basic-auth URLs are not supported — the receiver is loopback-only.

## Receiver run

```sh
python3 receiver/astrolabe_server.py            # 127.0.0.1:8090
python3 receiver/astrolabe_server.py --host 0.0.0.0 --port 8090
```

No dependencies beyond Python 3 stdlib. Only `python3` is required, so it runs on macOS, Termux, or a Kali chroot.

## F101 (Kali chroot via Magisk)

Copy the receiver to `/opt/opencode-astrolabe/astrolabe_server.py` inside the chroot and start it from the existing boot script alongside `opencode serve`:

```sh
# in /data/adb/service.d/50-f101-opencode-serve, after the opencode serve block:
nohup chroot "$T" /usr/bin/python3 /opt/opencode-astrolabe/astrolabe_server.py --host 127.0.0.1 --port 8090 \
  </dev/null >/data/local/tmp/opencode-astrolabe.log 2>&1 &
```

The F101's OpenCode server itself runs on the standard OpenCode port 4096; astrolabe's 8090 is receiver-only. Android shares the chroot's loopback, so `127.0.0.1:8090` reaches the face from any phone browser.
