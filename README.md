# Slot audio tools

Sound direction, crypto-payable generation, post-processing, measurement, advisory
review and Urso/Zephyr audio integration. Read [SKILL.md](SKILL.md) and
[audio operations](references/audio-operations.md).

Install the sibling slotgen-provider package and requirements.txt in the working
Python environment. ffmpeg/ffprobe must be on PATH. Preserve credentials privately.
The BB `qwen-review` provider owns `OPENROUTER_KEY` for review.

Generation agents and models are planned for a later stage; legacy job records
remain available for reconciliation.
Audio review uses a BB child thread on Qwen3.8 Omni Flash. Record full or
selected coverage and check digital silence locally.
Fit measures actual duration/format before publishing the output.
Measurements do not replace the user's listening acceptance.

Tests: python -m unittest discover -s tests. No test requires real credentials or spending.
