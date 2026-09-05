"""Review audio through OpenRouter with explicit clip coverage and no silent truncation."""
import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audio_metrics import probe

OR = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-pro"


def prepare_audio(path, segment=None):
    duration = probe(path)["duration"]
    start, end = (0.0, duration) if segment is None else map(float, segment)
    if not 0 <= start < end <= duration:
        raise ValueError("Audio review segment must be within the source duration")
    args = ["ffmpeg", "-v", "error", "-i", str(path)]
    if segment is not None:
        args += ["-ss", str(start), "-t", str(end-start)]
    if end-start < 2:
        args += ["-af", "apad=whole_dur=2", "-t", "2"]
    args += ["-b:a", "160k", "-f", "mp3", "pipe:1"]
    audio = subprocess.check_output(args)
    return audio, {"source_duration": duration, "start": start, "end": end,
                   "full": start == 0 and end == duration, "padded": end-start < 2}


def audio_content(path, segments=None):
    parts, coverage = [], []
    for segment in segments or [None]:
        audio, window = prepare_audio(path, segment)
        parts += [{"type": "text", "text": json.dumps({"clip": Path(path).name, "coverage": window})},
                  {"type": "input_audio", "input_audio": {"data": base64.b64encode(audio).decode(), "format": "mp3"}}]
        coverage.append(window)
    return parts, coverage


def call(content, max_tokens=None):
    from slotgen_provider.env import provider_key
    from slotgen_provider.http import request_json
    from slotgen_provider.review import response_text
    body = {"model": MODEL, "reasoning": {"effort": "high", "exclude": True},
            "messages": [{"role": "user", "content": content}]}
    if max_tokens is not None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        body["max_tokens"] = max_tokens
    response = request_json("POST", OR, token=provider_key("OPENROUTER_KEY"),
                            allowed_origins={"https://openrouter.ai"}, body=body, timeout=300)
    return response_text(response), response.get("usage"), response.get("model")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["describe", "consult"])
    parser.add_argument("original")
    parser.add_argument("attempt", nargs="?")
    parser.add_argument("used_prompt", nargs="?")
    parser.add_argument("--brief")
    coverage = parser.add_mutually_exclusive_group()
    coverage.add_argument("--full", action="store_true")
    coverage.add_argument("--segments", help="JSON list of [start,end] seconds applied to each input")
    parser.add_argument("--out", required=True, help="Task-local review report JSON")
    parser.add_argument("--max-tokens", type=int)
    args = parser.parse_args()
    from slotgen_provider.review import input_fingerprints
    brief = Path(args.brief).read_text() if args.brief else "Match the provided game reference; do not assume a theme."
    segments = json.loads(Path(args.segments).read_text()) if args.segments else None
    if segments is not None and (not isinstance(segments, list) or not segments):
        parser.error("--segments must contain at least one interval")
    prompt = "Review the type, material, coherence and mix role of this slot-game audio. Listening comfort needs human review. State the limits of the supplied coverage.\nBrief:\n" + brief
    files = [args.original]
    if args.operation == "consult":
        if not args.attempt or args.used_prompt is None:
            parser.error("consult requires original attempt used_prompt")
        files.append(args.attempt)
        prompt += "\nCompare original and attempt. Suggest a corrected sound prompt (maximum 240 characters) and duration; do not assume that the attempt is wrong.\nAttempt prompt: " + args.used_prompt
    content = [{"type": "text", "text": prompt}]
    windows = {}
    for file in files:
        parts, window = audio_content(file, segments)
        content.extend(parts)
        windows[Path(file).name] = window
    text, usage, returned_model = call(content, args.max_tokens)
    report = {"inputs": input_fingerprints(files), "coverage": windows, "brief": brief,
              "model": MODEL, "returned_model": returned_model, "max_tokens": args.max_tokens,
              "finish_reason": "stop", "usage": usage, "review": text}
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(text)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, ImportError, RuntimeError) as error:
        raise SystemExit(str(error))
