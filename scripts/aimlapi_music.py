#!/usr/bin/env python3
"""Generate music/ambient with AIMLAPI (crypto-payable). Default model: lyria2 (Google Lyria 2).

Async: POST /v2/generate/audio -> {id} ; poll GET ?generation_id= until completed ; audio_file.url.
Cloudflare needs a browser User-Agent (both API and CDN).

Usage:
  python3 aimlapi_music.py --model lyria2 --prompt "..." --out ./.tmp/bg.wav
  python3 aimlapi_music.py --model stable-audio --prompt "..." --seconds 30 --out ./.tmp/x.wav
Models: lyria2 (music ~30s, 48k), stable-audio (SFX/ambient, 44.1k, takes --seconds), minimax-music.
Key: AIMLAPI_KEY in ~/.claude/.env
"""
import argparse, json, subprocess, time, urllib.request, urllib.error
from pathlib import Path

GEN = "https://api.aimlapi.com/v2/generate/audio"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def key(name="AIMLAPI_KEY"):
    for raw in (Path.home() / ".claude" / ".env").read_text().splitlines():
        if raw.strip().startswith(name + "="):
            return raw.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"missing {name} in ~/.claude/.env")


def req(url, k, data=None, method="GET"):
    r = urllib.request.Request(url, data=(json.dumps(data).encode() if data else None),
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json", "User-Agent": UA},
        method=method)
    for _ in range(5):
        try:
            with urllib.request.urlopen(r, timeout=90) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise SystemExit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(4)
    raise SystemExit("network failure")


def generate(model, prompt, out, seconds=None, negative=None, convert=True):
    k = key()
    body = {"model": model, "prompt": prompt}
    if seconds and model == "stable-audio":
        body["seconds_total"] = int(seconds)
    if negative:
        body["negative_prompt"] = negative
    resp = req(GEN, k, body, "POST")
    gid = resp.get("id") or resp.get("generation_id")
    spent = (resp.get("meta", {}).get("usage", {}) or {}).get("usd_spent")
    print(f"[aimlapi] {model} id={gid} cost=${spent}")
    for i in range(70):
        time.sleep(6)
        st = req(f"{GEN}?generation_id={gid}", k)
        s = st.get("status")
        print(f"[aimlapi] poll {i}: {s}")
        if s == "completed":
            url = (st.get("audio_file") or {}).get("url")
            out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
            raw = out.with_suffix(".raw.wav")
            subprocess.run(["curl", "-sS", "-A", UA, "-o", str(raw), url], check=True)
            if convert:
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                                "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", str(out)], check=True)
                raw.unlink(missing_ok=True)
            else:
                raw.rename(out)
            print(f"[aimlapi] saved {out}")
            return str(out)
        if s in ("error", "failed"):
            raise SystemExit(f"failed: {json.dumps(st)[:300]}")
    raise SystemExit("timeout")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="lyria2")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seconds", type=int, default=None, help="stable-audio only")
    ap.add_argument("--negative", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    generate(a.model, a.prompt, a.out, a.seconds, a.negative)
