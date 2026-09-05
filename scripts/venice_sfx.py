#!/usr/bin/env python3
"""venice audio jobs; defaults preserve the existing provider/model route."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audio_jobs import main, run_audio, aimlapi_request

MODEL = "elevenlabs-sound-effects-v2"

def generate(prompt, seconds, out, model=MODEL, raw_only=False):
    return run_audio("venice", model=model, prompt=prompt, output=out, seconds=seconds, raw_only=raw_only)

if __name__ == "__main__":
    try:
        main("venice")
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        raise SystemExit(str(error))
