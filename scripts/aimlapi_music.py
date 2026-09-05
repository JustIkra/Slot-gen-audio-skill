#!/usr/bin/env python3
"""aimlapi audio jobs; defaults preserve the existing provider/model route."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audio_jobs import main, run_audio, aimlapi_request

GEN = "https://api.aimlapi.com/v2/generate/audio"
req = aimlapi_request

def generate(model, prompt, out, seconds=None, negative=None, convert=True):
    return run_audio("aimlapi", model=model, prompt=prompt, output=out, seconds=seconds, negative=negative, raw_only=not convert)

if __name__ == "__main__":
    try:
        main("aimlapi")
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        raise SystemExit(str(error))
