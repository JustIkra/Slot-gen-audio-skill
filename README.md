# slot-gen-audio

A Codex skill that generates a full **slot-game audio pack** — SFX + ambient / background
music — using **crypto-payable** providers only, then verifies and fits each sound to the
game engine's format.

It is the distilled, reusable version of a real production reskin (ancient-Egyptian / desert
fantasy slot): reel spin/stop, scatter, anticipation, wild, win lines, UI clicks, bonus
open/close, plus background / free-spins / win music.

## The one thing to remember
**The agent cannot hear audio directly.** The skill never claims a sound is "good". The pipeline is:
generate → measure objectively (ffmpeg spectral gate) → get an LLM's *type/material* read
(Gemini 2.5 Pro) → hand the file to the user for the final ear verdict.

## Backends (all crypto-payable)
Keys live in `~/.codex/.env` (`VENICE_API_KEY`, `AIMLAPI_KEY`, `OPENROUTER_KEY`, `GOOGLE_API_KEY`) — **never committed**.

| Need | Provider / model |
|------|------------------|
| Sound effects (one-shots, reel, UI, stings) | Venice.ai → `elevenlabs-sound-effects-v2` |
| Background / ambient / loop music | AIMLAPI → `lyria2` (Google Lyria 2) |
| Music stings / jingles | Venice `elevenlabs-music` or AIMLAPI `lyria2` |
| Audio understanding / QA | OpenRouter → `google/gemini-2.5-pro` |

## Read first
- `SKILL.md` — the playbook (hard rules, model routing, API shapes, the pipeline).

## Tools (`scripts/`)
| script | what |
|---|---|
| `venice_sfx.py` | generate one-shot SFX via Venice ElevenLabs (async queue). |
| `aimlapi_music.py` | generate ambient/background music via Google Lyria 2 (async poll). |
| `audio_review.py` | LLM audio QA (Gemini 2.5 Pro) — type/material read, prompt suggestions. |
| `dedup_check.py` | catch near-duplicate generations within a family. |
| `audio_post.sh` | post-process to the game engine format (level / peak / envelope match). |

## The rule that wastes the most time
Cloudflare blocks the default urllib User-Agent on AIMLAPI POST/GET **and** its CDN download
URL → HTTP 403 (code 1010). Always send a browser `User-Agent`.
