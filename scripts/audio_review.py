"""Review complete audio clips or explicit atlas windows with Qwen."""
import argparse
import base64
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audio_metrics import probe

MODEL = "qwen/qwen3.8-omni-flash"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class ReviewFailure(ValueError):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


def prepare_audio(path, segment=None):
    duration = probe(path)["duration"]
    start, end = (0.0, duration) if segment is None else map(float, segment)
    if not 0 <= start < end <= duration:
        raise ValueError("Audio review segment must be within the source duration")
    filters = [f"atrim=start={start}:end={end}", "asetpts=PTS-STARTPTS", "astats=metadata=0:reset=0"]
    padded = end - start < 2
    if padded:
        filters += ["apad=whole_dur=2", "atrim=duration=2"]
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", ",".join(filters),
         "-map_metadata", "-1", "-b:a", "160k", "-f", "mp3", "pipe:1"],
        capture_output=True, check=True,
    )
    peaks = re.findall(rb"Peak level dB:\s*(-?inf|[-+\d.]+)", result.stderr)
    if not peaks or not result.stdout:
        raise ValueError("Could not measure or encode the selected audio")
    peak = float(peaks[-1])
    if math.isnan(peak) or peak == math.inf:
        raise ValueError("Invalid decoded audio peak")
    silent = peak == -math.inf
    return result.stdout, {
        "source_duration": duration, "start": start, "end": end,
        "full": start == 0 and end == duration, "padded": padded,
        "rendered_duration": max(2, end - start), "digital_silence": silent,
        "sample_peak_dbfs": None if silent else peak,
    }


def audio_content(path, segments=None, label=None):
    parts, coverage = [], []
    for segment in segments or [None]:
        audio, window = prepare_audio(path, segment)
        parts.append({"type": "text", "text": json.dumps({
            "clip": label or Path(path).name, "coverage": window,
        })})
        if not window["digital_silence"]:
            parts.append({"type": "input_audio", "input_audio": {
                "data": base64.b64encode(audio).decode(), "format": "mp3",
            }})
        coverage.append(window)
    return parts, coverage


def validate_review(value):
    if not isinstance(value, dict) or value.get("audio_accessible") is not True:
        raise ReviewFailure("Model did not confirm access to the supplied audio", {"model_review": value})
    if not isinstance(value.get("description"), str) or not value["description"].strip():
        raise ReviewFailure("Model returned no audio description", {"model_review": value})
    for field in ("issues", "uncertainties"):
        if not isinstance(value.get(field), list):
            raise ReviewFailure(f"Model review lacks {field}", {"model_review": value})
    if any(not isinstance(issue, dict) or any(not isinstance(issue.get(k), str) or not issue[k].strip()
                                             for k in ("observation", "suggestion")) for issue in value["issues"]):
        raise ReviewFailure("Model returned malformed issues", {"model_review": value})
    if any(not isinstance(item, str) for item in value["uncertainties"]):
        raise ReviewFailure("Model returned malformed uncertainties", {"model_review": value})
    if value.get("comparison") is not None and not isinstance(value["comparison"], str):
        raise ReviewFailure("Model returned a malformed comparison", {"model_review": value})
    prompt = value.get("generation_prompt_en")
    if prompt is not None and (not isinstance(prompt, str) or len(prompt) > 240):
        raise ReviewFailure("Generation prompt exceeds the requested format", {"model_review": value})
    seconds = value.get("suggested_duration_seconds")
    if seconds is not None and (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                                or not math.isfinite(seconds) or seconds <= 0):
        raise ReviewFailure("Model returned an invalid suggested duration", {"model_review": value})
    return value


def parse_response(payload):
    from slotgen_provider.review import response_text
    try:
        text = payload.decode("utf-8").strip()
        streaming = not text.startswith("{")
        if streaming:
            chunks, done, data = [], False, []
            for line in text.splitlines() + [""]:
                if line.startswith("data:"):
                    data.append(line[5:].lstrip())
                elif not line and data:
                    event = "\n".join(data)
                    data = []
                    if event == "[DONE]":
                        done = True
                    else:
                        chunks.append(json.loads(event))
        else:
            chunks, done = [json.loads(text)], True
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReviewFailure("Malformed or truncated provider response") from error
    content, refusal, finish = [], None, None
    metadata = {}
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ReviewFailure("Malformed provider event")
        if chunk.get("error"):
            raise ReviewFailure("Provider returned an error event", {**metadata, "provider_error": chunk["error"]})
        for field in ("id", "model", "usage", "meta"):
            if chunk.get(field) is not None:
                metadata[field] = chunk[field]
        choices = chunk.get("choices") or []
        if not isinstance(choices, list) or any(not isinstance(choice, dict) for choice in choices):
            raise ReviewFailure("Malformed provider choices", metadata)
        for choice in choices:
            if choice.get("index", 0) != 0:
                continue
            message = choice.get("delta", choice.get("message", {})) or {}
            if not isinstance(message, dict):
                raise ReviewFailure("Malformed provider message", metadata)
            part = message.get("content")
            if isinstance(part, list):
                if any(not isinstance(p, dict) or not isinstance(p.get("text", ""), str) for p in part):
                    raise ReviewFailure("Malformed provider content", metadata)
                part = "".join(p.get("text", "") for p in part if p.get("type") == "text")
            if isinstance(part, str):
                content.append(part)
            refusal = refusal or message.get("refusal")
            if choice.get("finish_reason") is not None:
                finish = choice["finish_reason"]
    details = {**metadata, "finish_reason": finish, "text": "".join(content)}
    if streaming and not done:
        raise ReviewFailure("Provider stream ended without its terminal marker", details)
    try:
        review_text = response_text({"choices": [{"finish_reason": finish, "message": {
            "content": details["text"], "refusal": refusal,
        }}]})
        cleaned = review_text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.splitlines()[1:-1])
        value = json.loads(cleaned)
        review = validate_review(value)
    except (ValueError, TypeError) as error:
        extra = error.details if isinstance(error, ReviewFailure) else {}
        raise ReviewFailure(str(error), {**details, **extra}) from error
    return {**details, "review": review}


def call(content, max_tokens=None):
    from slotgen_provider.env import provider_key
    from slotgen_provider.http import request_bytes
    if max_tokens is not None and max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    key = provider_key("OPENROUTER_KEY")
    body = {"model": MODEL, "stream": True, "stream_options": {"include_usage": True},
            "modalities": ["text"], "temperature": 0.2,
            "messages": [{"role": "user", "content": content}]}
    if max_tokens is not None:
        body["max_completion_tokens"] = max_tokens
    payload, _ = request_bytes("POST", ENDPOINT, token=key,
                               allowed_origins={"https://openrouter.ai"}, body=body, timeout=300)
    return parse_response(payload.replace(key.encode(), b"[REDACTED]"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["describe", "consult"])
    parser.add_argument("original")
    parser.add_argument("attempt", nargs="?")
    parser.add_argument("used_prompt", nargs="?")
    parser.add_argument("--brief")
    coverage = parser.add_mutually_exclusive_group()
    coverage.add_argument("--full", action="store_true")
    coverage.add_argument("--segments", help="JSON list of [start,end] seconds applied to each input")
    parser.add_argument("--out", required=True, help="New task-local review report JSON")
    parser.add_argument("--max-tokens", type=int, help="Optional explicit completion limit")
    args = parser.parse_args(argv)
    output = Path(args.out)
    if output.exists():
        raise ValueError("Review report already exists; use a new path for an intentional new request")
    if args.max_tokens is not None and args.max_tokens <= 0:
        parser.error("--max-tokens must be positive")
    from slotgen_provider.review import input_fingerprints
    from slotgen_provider.http import SubmissionUnknown
    brief = Path(args.brief).read_text() if args.brief else "Match the provided game reference; do not assume a theme."
    segments = json.loads(Path(args.segments).read_text()) if args.segments else None
    if segments is not None and (not isinstance(segments, list) or not segments):
        parser.error("--segments must contain at least one interval")
    prompt = (
        "Review the audible type, material, event order, repetition, coherence and mix role of this game audio. "
        "Separate observations from hypotheses. Use the supplied measured durations and segment boundaries; "
        "start/end are source-file coordinates; each encoded window starts at zero. "
        "sample_peak_dbfs measures the whole source window, not individual events or perceived loudness. "
        "Do not invent measurements, BPM or exact timing. Padding to two seconds is only for analysis, not an asset defect. "
        "A clip marked digital_silence is measured silence and is deliberately represented by metadata only. "
        "Do not invent sounds on silence or claim human listening acceptance. If active audio cannot be analyzed, "
        "set audio_accessible=false. Do not invent issues just to fill the report.\nBrief:\n" + brief
    )
    files = [("original", args.original)]
    if args.operation == "consult":
        if not args.attempt or args.used_prompt is None:
            parser.error("consult requires original attempt used_prompt")
        files.append(("candidate", args.attempt))
        prompt += ("\nCompare original and candidate without assuming the candidate is worse. "
                   "Suggest an English generation prompt of at most 240 characters and a duration.\n"
                   "Candidate generation prompt: " + args.used_prompt)
    prompt += ('\nReturn one JSON object without Markdown: {"audio_accessible":true, '
               '"description":"audible observations", "issues":[{"observation":"specific property", '
               '"suggestion":"actionable adjustment or check"}], "uncertainties":["limitations"]')
    if args.operation == "consult":
        prompt += (', "comparison":"specific audible comparison", '
                   '"generation_prompt_en":"English prompt, at most 240 characters", '
                   '"suggested_duration_seconds":1.0')
    prompt += '}. Use the language of the brief for prose.'
    content, windows = [{"type": "text", "text": prompt}], {}
    for label, file in files:
        parts, window = audio_content(file, segments, label=label)
        content.extend(parts)
        windows[label] = {"path": str(Path(file).resolve()), "windows": window}
    report = {
        "inputs": [{**fp, "label": label, "path": str(Path(file).resolve())}
                   for (label, file), fp in zip(files, input_fingerprints([f for _, f in files]))],
        "coverage": windows, "brief": brief, "operation": args.operation,
        "candidate_prompt": args.used_prompt if args.operation == "consult" else None,
        "model": MODEL, "provider": "OpenRouter", "endpoint": ENDPOINT,
        "max_tokens": args.max_tokens, "provider_called": False, "status": "prepared",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    if not any(part["type"] == "input_audio" for part in content):
        report.update(status="digital_silence", review={
            "description": "All selected windows contain measured digital silence; no model was called.",
            "issues": [], "uncertainties": [],
        })
    else:
        report.update(status="submitted", provider_called=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        try:
            result = call(content, args.max_tokens)
            if args.operation == "consult" and any(result["review"].get(field) in (None, "")
                                                    for field in ("comparison", "generation_prompt_en", "suggested_duration_seconds")):
                raise ReviewFailure("Comparison response is missing requested fields", result)
            report.update(status="complete", returned_model=result.get("model"),
                          request_id=result.get("id"), finish_reason=result["finish_reason"],
                          usage=result.get("usage"), meta=result.get("meta"), review=result["review"])
        except (ValueError, RuntimeError) as error:
            report.update(status="submission_unknown" if isinstance(error, SubmissionUnknown) else "failed",
                          error_type=type(error).__name__, error=str(error), http_status=getattr(error, "status", None))
            if isinstance(error, ReviewFailure):
                report["failure"] = error.details
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            raise
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report["review"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, ImportError, RuntimeError) as error:
        raise SystemExit(str(error))
