#!/usr/bin/env python3
"""Generate a sound effect with Venice.ai -> ElevenLabs Sound Effects v2 (crypto-payable).

Async queue: POST /audio/queue -> queue_id ; POST /audio/retrieve (JSON pending | audio bytes) ;
POST /audio/complete. Downloads, converts to engine format (48k/Float32/stereo) by default.

Usage:
  python3 venice_sfx.py --prompt "..." --seconds 2 --out ./.tmp/x.wav
Notes:
  * prompt MUST be <= 240 chars ; --seconds is an INTEGER (0.5..30 -> rounded).
  * key from ~/.claude/.env: VENICE_API_KEY
"""
import argparse, base64, json, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

BASE = "https://api.venice.ai/api/v1"
MODEL = "elevenlabs-sound-effects-v2"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def key(name="VENICE_API_KEY"):
    for raw in (Path.home() / ".claude" / ".env").read_text().splitlines():
        if raw.strip().startswith(name + "="):
            return raw.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"missing {name} in ~/.claude/.env")


def http(method, path, k, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json",
                 "Accept": "*/*", "User-Agent": UA})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.status, resp.headers.get_content_type(), resp.read()


def generate(prompt, seconds, out, model=MODEL, raw_only=False):
    if len(prompt) > 240:
        raise SystemExit(f"prompt is {len(prompt)} chars (>240). Shorten it.")
    k = key()
    _, _, p = http("POST", "/audio/queue", k, {"model": model, "prompt": prompt,
                                               "duration_seconds": int(round(seconds))})
    qid = json.loads(p).get("queue_id")
    if not qid:
        raise SystemExit(f"no queue_id: {p[:300]}")
    print(f"[venice] queued {qid}")
    for i in range(60):
        time.sleep(5)
        st, ct, body = http("POST", "/audio/retrieve", k, {"model": model, "queue_id": qid})
        if any(x in ct for x in ("audio", "octet-stream", "wav", "mpeg", "flac")):
            out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
            raw = out.with_suffix(".raw")
            raw.write_bytes(body)
            if raw_only:
                raw.rename(out); print(f"[venice] saved {out}");
            else:
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                                "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", str(out)], check=True)
                raw.unlink(missing_ok=True)
                print(f"[venice] saved {out} (48k/Float32)")
            try:
                http("POST", "/audio/complete", k, {"model": model, "queue_id": qid})
            except Exception:
                pass
            return str(out)
        status = json.loads(body).get("status", "?")
        print(f"[venice] poll {i}: {status}")
        if status in ("FAILED", "ERROR"):
            raise SystemExit(f"failed: {body[:300]}")
    raise SystemExit("timeout")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seconds", type=float, default=2)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--raw", action="store_true", help="keep original (mp3) without converting")
    a = ap.parse_args()
    generate(a.prompt, a.seconds, a.out, a.model, a.raw)
