---
name: slot-gen-audio
description: >
  Generate a full game audio pack (SFX + ambient/background music) for slot games,
  paying ONLY with crypto. Routes music to Google Lyria 2 (AIMLAPI) and sound effects
  to ElevenLabs Sound Effects v2 (Venice.ai), reviews results with Gemini 2.5 Pro
  (audio understanding) + an objective ffmpeg spectral gate, and post-processes to the
  game engine format. Use whenever the user wants to (a) create/replace slot SFX
  (reel spin/stop, scatter, anticipation, wild, win lines, UI clicks, bonus open/close),
  (b) generate background / free-spins / win music, (c) match new sounds to existing
  originals (duration, level, peak/envelope), (d) build "families" of related variations
  (reel_stop_1..5, scatter_1..3), or (e) audit/analyse audio without being able to listen.
  Triggers on "slot sounds", "generate sfx", "reel stop sound", "scatter sound", "background
  music for the game", "make it less harsh / not cut the ears", "match the original", "audio pack".
user-invocable: true
---

# Slot-Gen-Audio Skill

Produce a cohesive slot-game audio pack with **crypto-only** providers, then verify and
fit each sound to the game's engine format. Built and battle-tested on a real production
reskin (ancient-Egyptian / desert fantasy slot).

## The one thing to remember
**The agent cannot hear audio directly.** Never claim a sound is good. The workflow is: generate → measure
objectively → get an LLM's *type/material* read → hand the file to the USER for the final
ear verdict. The user's ears are ground truth, especially for "harsh / cuts the ears".

## Backends (all crypto-payable)

API keys in `~/.codex/.env`: `VENICE_API_KEY`, `AIMLAPI_KEY`, `OPENROUTER_KEY`, `GOOGLE_API_KEY`.

| Need | Provider / model | Why |
|------|------------------|-----|
| **Sound effects** (one-shots, reel, UI, stings) | **Venice.ai → `elevenlabs-sound-effects-v2`** | Foley-realistic quality leader; controllable `duration_seconds`; follows prompts. |
| **Background / ambient / loop music** | **AIMLAPI → `lyria2`** (Google Lyria 2) | Produced, cinematic, instrumental; native 48 kHz; ~30 s/gen. |
| **Music stings / jingles** | Venice `elevenlabs-music` **or** AIMLAPI `lyria2` | Coherent musical phrases. |
| **Audio understanding / QA** | **OpenRouter → `google/gemini-2.5-pro` + reasoning** | Best at *type & material*; far better than flash/gpt-audio on SFX. |

### Model routing rule
- **Music → Lyria 2.** Stable Audio is unreliable for music (collapses to one pole: now orchestral, now EDM, now folk).
- **SFX → ElevenLabs (Venice).** Stable Audio (`stable-audio` on AIMLAPI) "puts experiment over realism" → bright synthetic *chimes* that **cut the ears**. Only use it if Venice is unavailable.
- **No dedicated SFX model exists on AIMLAPI** (ElevenLabs there = music/TTS only). For real SFX you need Venice.
- **Google Lyria cannot do short one-shots** (fixed ~30 s music). Don't ask it for a 0.3 s click.

## API shapes (see `scripts/` for working clients)

**Venice ElevenLabs SFX** — async queue. `prompt` must be **≤ 240 chars**, `duration_seconds` is an **integer**.
```
POST https://api.venice.ai/api/v1/audio/queue   {model, prompt, duration_seconds}   -> {queue_id}
POST https://api.venice.ai/api/v1/audio/retrieve {model, queue_id}  -> 200 JSON {status} (pending) | 200 audio bytes (done)
POST https://api.venice.ai/api/v1/audio/complete {model, queue_id}  (after download)
```
**AIMLAPI Lyria / Stable Audio** — async poll. Cloudflare blocks the default urllib UA → **send a browser `User-Agent`**.
```
POST https://api.aimlapi.com/v2/generate/audio   {model:"lyria2"|"stable-audio", prompt, [seconds_total], [negative_prompt]} -> {id}
GET  https://api.aimlapi.com/v2/generate/audio?generation_id=<id>   -> {status, audio_file:{url}}   # poll ~6 s
```
Get exact model ids live: `GET https://api.aimlapi.com/v1/models` and Venice `GET /api/v1/models?type=music`.
The CDN download URL is **also Cloudflare-protected** — download with `curl -A "<browser UA>"`.

## Prompting lessons (ElevenLabs SFX)

Describe the **physical sound and material**, not vibes.

- **Avoid "magical / chime / sparkle / shimmer"** unless you truly want a bright bell — those words produce high-frequency synth chimes that cut the ears.
- **The "Sand Trap" (key insight):** do NOT make *sand* the primary material of everything — sand muffles and kills clarity/weight. Split into **material families**:
  - **Mechanical** (reel spin/stop, lever) = heavy **sandstone / sun-bleached wood**; sand is only an *accent* (a puff of dust).
  - **Magical** (scatter, bonus, win) = **light, shimmer, sacred instruments** — e.g. an Egyptian **sistrum**. Not stone, not sand.
  - **Texture** = sand as seasoning, never the main course.
- **Reel SPIN** must be a **continuous rotation/whir**, not rhythmic *thuds* (sounds like drums) and not a low continuous *rumble* (fights the music's bass). Aim for clear mid-range motion, "no deep rumble or bass".
- **Reel STOP** needs **weight + finality** ("heavy block locking into place, deep thud, puff of dust"); words like "switch/toggle/flick" make it thin and weak.
- Reference concrete instruments/objects; state what to avoid ("no metallic", "no high frequencies", "no crackle").
- Min usable length ~0.5 s; generate a bit longer than the target and trim.

## QA: how to evaluate without ears

1. **Type / material** → `scripts/audio_review.py describe <file>` (Gemini 2.5 Pro + reasoning). Reliable for *what it is / what it's made of*. **Unreliable for harshness/energy** — both Gemini and GPT-audio flip-flop and bias toward "metallic chime"; GPT-audio also fails on very short clips.
2. **Harshness ("режет уши")** → **objective spectral gate**, not an LLM. Measure high-band energy:
   `ffmpeg -i f -af "highpass=f=6000,volumedetect" -f null /dev/null` → compare `max_volume`/`mean_volume` vs the full file. Lower high-band = duller = safer.
3. **Peak / envelope match to an original** → `astats` per window:
   `ffmpeg -i f -af "astats=metadata=1:reset=4800,ametadata=print:key=lavfi.astats.Overall.Peak_level" -f null /dev/null`.
   A steady original often shows a **constant peak "shelf"** (e.g. −9 dB the whole time); a bad gen shows a **crescendo**.
4. **The most effective workflow — consult, don't guess:** `scripts/audio_review.py consult <original> <my_attempt> "<prompt I used>"` sends both to Gemini 2.5 Pro and asks it to critique the *idea* and output a corrected ElevenLabs prompt. This is how the "Sand Trap" and "drums-not-a-wheel" mistakes were caught.

## Post-processing (ffmpeg) — `scripts/audio_post.sh`

Target engine format (this project): **48000 Hz, Float32, stereo WAV** (`-ar 48000 -ac 2 -c:a pcm_f32le`). Always check the originals' format first (`afinfo`) and match it.

- **Convert / resample** (Stable Audio is 44.1 kHz): `-ar 48000 -ac 2 -c:a pcm_f32le`.
- **Music normalize:** `loudnorm=I=-18:TP=-1.5:LRA=11` (calm bg around −18…−20 LUFS).
- **SFX peak-normalize:** measure `max_volume`, gain = `target - max` (e.g. events −3 dB, reel sounds −12 dB to sit under calm music).
- **Tame harshness / "cuts the ears":** `lowpass=f=X` (3000–6000) + `treble=g=-N:f=Y`. Stronger = duller.
- **Constant-peak "shelf" (match a steady original):** `dynaudnorm` + `volume <boost>dB` + `alimiter=limit=<linear>` where linear = `10^(dB/20)` (−9 dB = 0.355). ⚠️ The limiter adds high-freq harmonics → slight hiss; a post-limiter low-pass reduces hiss but bends the peak shelf — pick which matters.
- **Kill a crescendo (flat envelope):** `dynaudnorm=f=120:g=11`, then take a steady window with `-ss`.
- **Families of variations from ONE base** (consistent siblings, not 5 unrelated sounds): micro pitch-shift `asetrate=48000*<p>,aresample=48000` with p ≈ 0.965–1.035 + slight level. This mirrors real slot round-robins.
- **Fit duration to original:** `-t <dur>` + short `afade=t=out` at the cut; pad short clips with `apad=whole_dur=<dur>`; align a short hit to its onset with `silenceremove=start_periods=1:start_threshold=-45dB`.
- **Loop-extend background:** `acrossfade=d=4` two copies, then `-t <target>`.

## Dedup check for numbered families — `scripts/dedup_check.py`
Before regenerating `x_1..x_n`, confirm the originals aren't identical: PCM MD5 (`ffmpeg -f s16le | md5sum`) catches exact dupes; pairwise normalized cross-correlation catches perceptual near-dupes. Real slot families are **distinct-but-related** (corr ~0.6–0.8 between siblings) — so regenerate as *one base + micro-variations*, not copies.

## Per-folder workflow

1. **Scratch lives in a repo-relative `./.tmp_<folder>/`** (never `/tmp`).
2. **Dedup check** the numbered groups.
3. **Analyse originals** with Gemini 2.5 Pro (describe) — and for stuck sounds, **consult** (original + attempt + prompt).
4. **Generate** into the tmp folder: music → Lyria; SFX → ElevenLabs (Venice); families = one base + micro-pitch variations.
5. **Measure** (spectral gate + peak/RMS envelope vs original) and **hand to the user** for the ear verdict. Iterate prompt/post per their feedback.
6. **Finalize**: peak-normalize to a balanced level, fit each to the original's exact duration, convert to engine format, **back up originals to `./.tmp_<folder>/_ORIGINALS_backup/`**, then write into `src/assets/sounds/<folder>/`.

## Gotchas (save yourself hours)
- **You can't hear** — measure + delegate the verdict to the user. State that plainly.
- **LLM audio QA is advisory:** great for type/material (Gemini 2.5 Pro + reasoning), unreliable for harshness — use the spectral gate; GPT-audio (`gpt-audio` on AIMLAPI) is not better and dies on short clips. OpenRouter has **no** `openai/gpt-4o-audio-preview`.
- **Codex CLI cannot natively understand audio files** (only voice dictation into the prompt). Route audio to gemini/gpt-audio via API.
- **Cloudflare:** AIMLAPI POST/GET and its CDN need a browser `User-Agent` (else HTTP 403 code 1010).
- **zsh:** unquoted `$VAR` does NOT word-split, so `-t $DUR` reaches ffmpeg as one bad token — write `-t "$dur"` explicitly. **ffmpeg cannot write in place** — output to a temp file then `mv`.
- **Short clips (<~0.4 s):** pad to ~2 s before sending to an audio-LLM or it "doesn't hear" them.
- **Back up originals before overwriting assets.** Always.
- **Costs (cheap):** Stable Audio ≈ $0.0156/gen, Lyria ≈ $0.013/gen, ElevenLabs SFX (Venice) per-generation. Iterate freely.

## Quick commands

```bash
# SFX (Venice / ElevenLabs)
python3 scripts/venice_sfx.py --prompt "A heavy sandstone block locking into place, deep thud, puff of dust. No high-pitched click." --seconds 1 --out ./.tmp/reel_stop_base.wav

# Music (AIMLAPI / Lyria 2)
python3 scripts/aimlapi_music.py --model lyria2 --prompt "Epic fantasy desert free-spins music, 132 BPM, soaring ney flute, building to a climax, no vocals" --out ./.tmp/free_spins_music.wav

# Review
python3 scripts/audio_review.py describe ./.tmp/reel_stop_base.wav
python3 scripts/audio_review.py consult "src/assets/sounds/reel ordinary/reel_stop_1.wav" ./.tmp/reel_stop_base.wav "the prompt I used"

# Post
bash scripts/audio_post.sh family ./.tmp/reel_stop_base.wav ./.tmp 5        # one base -> reel_stop_1..5 (micro-pitch)
bash scripts/audio_post.sh fit ./.tmp/x.wav "src/assets/.../x.wav" out.wav  # match duration+format, peak -3
bash scripts/audio_post.sh peakshelf ./.tmp/spin.wav out.wav -9             # constant-peak shelf like a steady original
python3 scripts/dedup_check.py "src/assets/sounds/reel ordinary" reel_stop_1 reel_stop_2 reel_stop_3 reel_stop_4 reel_stop_5
```

Read `scripts/` for the exact, working implementations.
