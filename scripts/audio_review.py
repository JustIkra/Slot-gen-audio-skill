#!/usr/bin/env python3
"""Audio understanding / QA via Gemini 2.5 Pro (+reasoning) over OpenRouter.

You can't hear; this gives a TYPE/MATERIAL read (reliable) — NOT a harshness verdict
(use the ffmpeg spectral gate for that, and the user's ears for the final call).

  describe <file>                         -> what is it, material, harsh?, brightness
  consult  <original> <attempt> "<prompt>"-> critique the IDEA + corrected ElevenLabs prompt

Short clips (<~0.4s) are padded to 2s so the model can "hear" them.
Key: OPENROUTER_KEY in ~/.codex/.env
"""
import base64, json, re, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

OR = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-pro"


def key(name="OPENROUTER_KEY"):
    for raw in (Path.home() / ".codex" / ".env").read_text().splitlines():
        if raw.strip().startswith(name + "="):
            return raw.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"missing {name}")


def b64(path):
    mp3 = Path("/tmp") / ("ar_" + str(abs(hash(path)) % 99999) + ".mp3")
    # pad to >=2s so very short SFX are audible to the model
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path,
                    "-af", "apad=whole_dur=2", "-t", "2", "-b:a", "160k", str(mp3)], check=True)
    return base64.b64encode(mp3.read_bytes()).decode()


def call(content, k):
    body = {"model": MODEL, "reasoning": {"effort": "high", "exclude": True},
            "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request(OR, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"}, method="POST")
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            m = data["choices"][0]["message"]["content"]
            return "".join(p.get("text", "") for p in m) if isinstance(m, list) else m
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
        except Exception:
            time.sleep(5)
    return "(failed)"


def aud(path):
    return {"type": "input_audio", "input_audio": {"data": b64(path), "format": "mp3"}}


def describe(path, k):
    prompt = ("Analyse this short game sound effect concisely:\n1. WHAT IS IT\n2. MATERIAL/source "
              "(metal/plastic/sand/wood/stone/synth)\n3. HARSH/sharp or SOFT/mellow?\n4. bright/high "
              "or dull/muffled?\n5. one-line character summary.")
    print(call([{"type": "text", "text": prompt}, aud(path)], k))


def consult(original, attempt, used_prompt, k):
    intro = ("You are a senior game audio director for an ancient-Egyptian/desert fantasy SLOT "
             "(calm warm orchestral background). SFX are made with ElevenLabs Sound Effects v2 "
             "(text-to-sfx, prompt <=240 chars, integer duration, realistic foley). Goal: cohesive, "
             "high quality, NOT ear-piercing.\n(A) ORIGINAL game sound:")
    ask = (f"\n(B) above is MY attempt; prompt used: \"{used_prompt}\". Analyse ORIGINAL vs attempt, "
           "name the conceptual mistake in my idea/prompt, then OUTPUT EXACTLY two lines:\n"
           "FINAL_PROMPT: <ElevenLabs prompt, max 240 chars>\nDURATION: <integer seconds>")
    out = call([{"type": "text", "text": intro}, aud(original),
                {"type": "text", "text": "(B) MY attempt:"}, aud(attempt),
                {"type": "text", "text": ask}], k)
    print(out)
    pm = re.search(r"FINAL_PROMPT:\s*(.+)", out)
    if pm:
        print("\n>>> use this prompt with venice_sfx.py --prompt \"%s\"" % pm.group(1).strip().strip('"')[:240])


if __name__ == "__main__":
    k = key()
    if len(sys.argv) >= 3 and sys.argv[1] == "describe":
        describe(sys.argv[2], k)
    elif len(sys.argv) >= 5 and sys.argv[1] == "consult":
        consult(sys.argv[2], sys.argv[3], sys.argv[4], k)
    else:
        print(__doc__)
