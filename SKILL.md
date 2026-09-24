---
name: slot-gen-audio
description: >
  Use when creating or replacing slot-game SFX or music with crypto-payable providers,
  matching reference duration and levels, making sound families, reviewing audio,
  defining sound palettes/event maps, or integrating sound through Urso/Zephyr.
---

# Slot audio

Deliver a coherent sound pack or a scoped cue replacement. Do not introduce an obligatory
team of agents or an audio manager when the existing game sound system is sufficient.

## Setup and brief

Read the game's memory index and existing sound references. For one cue, record its event
and reference; for a pack, also establish materials/instruments, musical direction and mix.
Store the brief in the game's .memory-base/ and candidates/jobs in .tmp_<task>/.

Use the Python environment containing the sibling slotgen-provider package:
    python -m pip install -e ../slot-gen -r requirements.txt

ffmpeg and ffprobe must be on PATH. The prepared shared interpreter is
/Users/maksim/MorningCat/.local/skills-venv/bin/python. Keys are VENICE_API_KEY,
AIMLAPI_KEY and OPENROUTER_KEY
in the environment or ~/.codex/.env; do not expose values.

## Routes

| Task | Command |
|---|---|
| SFX | scripts/venice_sfx.py |
| Music/ambient | scripts/aimlapi_music.py |
| Measurements | scripts/audio_metrics.py measure <file> --json |
| Duration/format match | scripts/audio_metrics.py fit <candidate> <reference> <output> |
| Type/material comparison | scripts/audio_review.py describe or consult, with --out |
| Numbered-family deduplication | scripts/dedup_check.py |
| Existing processing recipes | scripts/audio_post.sh |

Configured defaults are Venice/ElevenLabs SFX, AIMLAPI/Lyria music and
OpenRouter/Qwen3.8-Omni-Flash audio understanding (`qwen/qwen3.8-omni-flash`).
Provider details, explicit formats and examples:
[audio operations](references/audio-operations.md). Do not silently substitute providers
or models; check current provider capabilities before changing the configured route.

Audio review has no alternate model or automatic fallback; it does not generate audio.

## Event and mix contract

- Map trigger → soundKey → action → loop/relaunch → stop/fade trigger; record duration,
  priority and visual counterpart. Do not invent unsupported engine config fields.
- Judge music and SFX together. Repeated reel/UI cues should not mask feature cues.
  Define ducking/restoration and limits on overlapping repetitions.
- Every loop needs an end condition. Check normal completion, skips, supported turbo/autoplay,
  scene transitions and mute/unmute; avoid stacked music or orphaned anticipation.
- Important game state and awards remain understandable with audio muted. Use visual
  counterparts; captions are needed when spoken information carries meaning.
- Spectral measurements are diagnostics, not proof of comfort. AI reviews are advisory;
  do not claim subjective listening acceptance without the user's review.

## Processing and audit

fit defaults to the reference PCM format; --format engine requires a profile JSON with
sample_rate, channels and codec. It pads/trims, fades the tail, measures the rendered output
and refuses input overwrite. Legacy non-fit shell recipes have an explicit 48k stereo target.

Review game sounds as episodes built from the matching runtime audio atlas and its JSON
sound keys. Derive cue boundaries from the atlas and ordering/loops from game events;
label reconstructed timing and omitted mix layers. For an isolated cue, send the whole cue.
See the atlas recipe in [audio operations](references/audio-operations.md).

Audio review preserves full clips by default, or records --segments coverage. It measures
digital silence locally and omits silent windows from model input. --brief supplies the
game context; --out must be a new report path. Qwen returns structured descriptions,
issues and uncertainties; consult also returns a comparison and generation suggestion.
--max-tokens is optional; when omitted, no completion cap is sent. An explicit
value is passed unchanged. HTTP 200 can carry
an error event: only a complete, non-refused response with audio_accessible=true is a model
review. Failures and interrupted requests remain in the report; do not silently retry or
switch models. Timing, silence and levels come from measurements, not model guesses.

Generation uses saved job records with submit/resume/download/auto. Resume existing jobs;
submission_unknown is not permission to submit again. Check generated format and preserve
originals before installation.

## Integration only when requested

Use getSoundsConfig() in the game's sound config and existing audio-atlas pipeline.
Components emit observer events; config owns soundKey/action selection. Verify packed keys,
cue boundaries, loop joins and memory budgets. Through zephyr-launcher-session, check real
desktop/mobile audio unlock, mute/unmute, foreground recovery and start/stop behavior.

Asset-only delivery ends with files, measurements and listening review. Integrated delivery
also needs runtime evidence; a design document alone does not prove that audio works.
