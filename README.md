# Slot audio tools

Sound direction, crypto-payable generation, post-processing, measurement, advisory
review and Urso/Zephyr audio integration. Read [SKILL.md](SKILL.md) and
[audio operations](references/audio-operations.md).

Install the sibling slotgen-provider package and requirements.txt in the working
Python environment. ffmpeg/ffprobe must be on PATH. Preserve credentials privately.

Generation commands save job IDs and support resume without another paid submission.
Audio review records full/selected coverage; fit measures actual duration/format before
publishing the output. Measurements do not replace the user's listening acceptance.

Tests: python -m unittest discover -s tests. No test requires real credentials or spending.
