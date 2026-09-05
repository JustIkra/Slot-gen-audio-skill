# Audio operations

Run scripts in the environment containing slotgen-provider and numpy, with ffmpeg/ffprobe
on PATH. Credentials: VENICE_API_KEY, AIMLAPI_KEY, OPENROUTER_KEY; no values in arguments/logs.

## Generate and resume

    python scripts/venice_sfx.py --prompt "A short wooden latch closing, soft low impact" --seconds 1 --out .tmp_audio/click.wav
    python scripts/aimlapi_music.py --model lyria2 --prompt "Instrumental background matching the approved game brief" --out .tmp_audio/music.wav
    python scripts/venice_sfx.py --action resume --job-file .tmp_audio/click.wav.job.json

The configured SFX route is Venice/elevenlabs-sound-effects-v2; music is AIMLAPI/lyria2.
Use --action submit to save the task ID without waiting, resume to poll/download, download
for a ready task and auto for the normal workflow. A different candidate needs an explicitly
new job/output path. Existing downloaded outputs are checked by checksum.

SFX prompts describe physical sound/material. Theme examples are not global requirements:
use the project's actual mood and instruments. Short generated material can be fitted
afterward. Check current API limits before changing models or parameters; do not use old
price estimates as authorization to spend.

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

    python scripts/audio_review.py describe cue.wav --full --brief brief.md --out .tmp_audio/review.json
    python scripts/audio_review.py consult original.wav candidate.wav "generation prompt" --brief brief.md --out .tmp_audio/comparison.json

Without --segments the whole clip is supplied; short clips are padded only for analysis.
An explicit segments JSON contains a list of [start,end] seconds applied to each input.
The report records coverage and input hashes. --max-tokens is never reduced automatically.
Provider failures, refusals and incomplete responses do not count as completed reviews.

For families, inspect originals with dedup_check.py first. Related variants should not
be accidentally identical; pitch changes are one possible technique, not a universal rule.
Keep originals and accepted outputs separate until integration is approved.
