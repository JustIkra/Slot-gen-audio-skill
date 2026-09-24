# Audio operations

Run local measurement and fitting commands in the prepared Python environment with
ffmpeg/ffprobe on PATH. The BB review provider owns OPENROUTER_KEY. Keep credentials
out of arguments and logs.

## Generation agent pending

SFX and music generation will move to BB agents when their generation models
are chosen. Do not submit new generation work through the legacy direct-provider
commands from this skill. Keep existing job records intact so an in-flight task
can be reconciled during migration. SFX prompts should still describe physical
sound and material; the project's actual mood and instruments govern music.

## Measure and fit

    python scripts/audio_metrics.py measure cue.wav --json
    python scripts/audio_metrics.py fit candidate.wav original.wav fitted.wav --format reference
    python scripts/audio_metrics.py fit candidate.wav original.wav fitted.wav --format engine --profile engine.json

An engine profile contains sample_rate, channels and a PCM codec, for example pcm_f32le.
Reference mode copies the reference's PCM format and duration. Outputs are measured before
atomic replacement; either input is protected from overwrite. spectral is a diagnostic;
listening comfort still requires human review. Existing non-fit shell recipes explicitly
target 48k stereo; do not confuse them with reference-format matching.

## Review

Use the installed BB `qwen-review` provider with model
`qwen/qwen3.8-omni-flash`. The provider accepts MP3, WAV, M4A, OGG and FLAC;
it converts non-MP3 audio on the host. Attach complete clips by default. For a
named segment, extract it locally with ffmpeg and record the exact source interval.
Measure digital silence and levels with `audio_metrics.py` before asking for
subjective review. A silent result is a measurement, not listening approval.

Write the review question and game context to a task-local prompt file. Name
each attachment's role in the prompt. For a comparison, attach both the
original and candidate as separate files. Then start one BB child thread:

```bash
bb thread spawn --project "$BB_PROJECT_ID" --environment "$BB_ENVIRONMENT_ID" \
  --parent-self --visibility hidden --provider qwen-review \
  --model qwen/qwen3.8-omni-flash --permission-mode accept-edits \
  --title "Audio review" --prompt-file /absolute/path/review-prompt.md \
  --file /absolute/path/candidate.wav
```

Use `bb thread wait <id> --status idle` and inspect `bb thread log <id> --all --json`.
The thread is the source record. Save its ID, source paths and SHA-256 hashes,
coverage, numerical measurements, model findings and unresolved questions in
the task-local report. For a comparison, request description, issues,
uncertainties and a generation suggestion. An inaccessible-audio claim,
failure, refusal or interrupted turn is incomplete, even if BB marks a turn
completed. Do not silently resubmit unchanged media or switch reviewers.
Exact timing and levels come from measurements; subjective suggestions need
the user's listening check.

### Atlas episodes

Use the matching JSON and audio from the game's actual runtime build. Do not combine an
old source-atlas JSON with a newly packed OGG/MP3. Audiosprite entries are
`[start_ms, duration_ms, optional_loop]`: convert to `[start_ms/1000,
(start_ms+duration_ms)/1000]` before extracting a named segment. Record the soundKey
alongside those bounds in the task manifest/brief. Separate extracted segments are
separate labelled attachments, not a seamless playback sequence.

For a spin, scatter series, bonus transition or win sequence, extract complete keys with
ffmpeg and assemble an episode using the event order, repetitions, start/stop, fades and
mix levels from game configuration. Store an episode manifest with atlas fingerprints,
keys, source bounds and playback intervals. Distinguish a reconstructed episode from a
captured gameplay recording; disclose estimated gaps or excluded background layers.
Then review the resulting episode as a full clip. Do not use a random first-N-second
slice as a substitute for a named cue or full loop. Retain numerical measurements for
silence, levels and timing even when the model's description sounds confident.

Provider reference: [Qwen3.8 Omni Flash](https://openrouter.ai/qwen/qwen3.8-omni-flash/).

For families, inspect originals with dedup_check.py first. Related variants should not
be accidentally identical; pitch changes are one possible technique, not a universal rule.
Keep originals and accepted outputs separate until integration is approved.
