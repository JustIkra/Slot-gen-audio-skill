# Audio operations

Run scripts in the environment containing slotgen-provider and numpy, with ffmpeg/ffprobe
on PATH. Credentials: VENICE_API_KEY, AIMLAPI_KEY and OPENROUTER_KEY; no values in
arguments/logs.

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

Default: `qwen/qwen3.8-omni-flash` via OpenRouter
(`POST https://openrouter.ai/api/v1/chat/completions`, authenticated with
`OPENROUTER_KEY`).
Send audio as raw Base64 in `input_audio.data` with `format: "mp3"`. The helper decodes
the source, measures the selected window and encodes MP3 for transport. Request streaming
text output, temperature 0.2 and `max_completion_tokens: 16384` unless the user
supplies another budget via `--max-tokens`. No automatic fallback is used.

Qwen3.5 comparison route: pass `--model alibaba/qwen3.5-omni-plus` explicitly.
It uses AIMLAPI and `AIMLAPI_KEY`, with the same supplied audio but `max_tokens`
as the provider's budget field. The former bare `qwen3.8-omni-flash` selector
remains an alias for the OpenRouter route. Neither route generates audio. Never
fall back to Qwen3.5 silently.

See [Qwen Omni comparison](qwen-omni-comparison.md) for the full decision table and
official references. To compare models, use the same input files, segments, brief
and `--max-tokens`, then compare the saved JSON reports and perform a listening check.

    python scripts/audio_review.py describe cue.wav --full --brief brief.md --out .tmp_audio/review.json
    python scripts/audio_review.py consult original.wav candidate.wav "generation prompt" --brief brief.md --out .tmp_audio/comparison.json
    python scripts/audio_review.py describe episode.wav --brief brief.md --out .tmp_audio/qwen38-review.json
    python scripts/audio_review.py describe episode.wav --model alibaba/qwen3.5-omni-plus \
      --brief brief.md --out .tmp_audio/qwen35-review.json

Without --segments the whole clip is supplied; short clips are padded only for analysis.
An explicit segments JSON contains a list of [start,end] seconds applied to each input.
The report distinguishes original/candidate even when their filenames match. It records
source paths, input hashes, coverage, padding, decoded sample peaks, requested/returned
model, request ID and available usage/cost. `review` is a JSON object with description,
issues, uncertainties and optional comparison/generation fields. Exact timing is supplied
as metadata; suggestions are advisory and need a listening check.

Digital silence is checked before model invocation: silent windows are represented by
metadata, and an entirely silent request returns `status: digital_silence` locally with
`provider_called: false`. This is a measurement result, not subjective approval. Very quiet
nonzero audio is not automatically classified as silence.

Reports use a new --out path per intentional request. A submitted record is written before
the provider call. HTTP 200 error events, missing terminal markers, truncated outputs,
refusals and audio_accessible=false fail the review and retain available error details.
`submission_unknown` means transport was interrupted and completion/billing is uncertain;
inspect the provider's request/usage history before submitting again. Do not silently lower
--max-tokens, convert an audio failure to a text-only success, or switch to another reviewer.

### Atlas episodes

Use the matching JSON and audio from the game's actual runtime build. Do not combine an
old source-atlas JSON with a newly packed OGG/MP3. Audiosprite entries are
`[start_ms, duration_ms, optional_loop]`: convert to `[start_ms/1000,
(start_ms+duration_ms)/1000]` for --segments. Record the soundKey alongside those bounds in
the task manifest/brief. Separate --segments are delivered as separate labelled windows,
not concatenated into a seamless playback sequence.

For a spin, scatter series, bonus transition or win sequence, extract complete keys with
ffmpeg and assemble an episode using the event order, repetitions, start/stop, fades and
mix levels from game configuration. Store an episode manifest with atlas fingerprints,
keys, source bounds and playback intervals. Distinguish a reconstructed episode from a
captured gameplay recording; disclose estimated gaps or excluded background layers.
Then review the resulting episode as a full clip. Do not use a random first-N-second
slice as a substitute for a named cue or full loop. Retain numerical measurements for
silence, levels and timing even when the model's description sounds confident.

API references: [OpenRouter Qwen3.8](https://openrouter.ai/qwen/qwen3.8-omni-flash/),
[OpenRouter chat completions](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request),
[AIMLAPI Qwen3.5](https://docs.aimlapi.com/api-references/text-models-llm/alibaba-cloud/qwen3.5-omni-plus).

For families, inspect originals with dedup_check.py first. Related variants should not
be accidentally identical; pitch changes are one possible technique, not a universal rule.
Keep originals and accepted outputs separate until integration is approved.
