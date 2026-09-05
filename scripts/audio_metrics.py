import argparse
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path


def probe(file):
    data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'format=duration:stream=sample_rate,channels,codec_name', '-of', 'json', str(file)]))
    if not data.get('streams'):
        raise ValueError('No audio stream')
    stream = data['streams'][0]
    duration = float(data['format']['duration'])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid audio duration')
    return {'duration': duration, 'sample_rate': int(stream['sample_rate']), 'channels': stream['channels'], 'codec': stream['codec_name']}


def peak(file, filters=''):
    chain = (filters + ',' if filters else '') + 'volumedetect'
    result = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(file), '-af', chain, '-f', 'null', '-'], capture_output=True, text=True, check=True)
    match = re.search(r'max_volume:\s*(-?\d+(?:\.\d+)?|-inf) dB', result.stderr)
    if not match:
        raise ValueError('Peak measurement unavailable')
    value = float(match.group(1))
    return value if math.isfinite(value) else None


def measure(file):
    return {**probe(file), 'peak_dbfs': peak(file), 'high_band_peak_dbfs': peak(file, 'highpass=f=6000'), 'spectral_role': 'diagnostic proxy, not a listening-comfort verdict'}


def fit(source, original, output, peak_db=-3, format_mode='reference', profile=None):
    source, original, output = map(Path, (source, original, output))
    if output.resolve() in (source.resolve(), original.resolve()):
        raise ValueError('Output must not overwrite either input')
    reference = probe(original)
    target = reference if format_mode == 'reference' else profile
    if not target or not str(target.get('codec', '')).startswith('pcm_'):
        raise ValueError('Expected an explicit PCM WAV target profile')
    rate, channels = int(target['sample_rate']), int(target['channels'])
    if rate <= 0 or channels <= 0 or not math.isfinite(peak_db) or peak_db > 0:
        raise ValueError('Invalid target format/peak')
    duration = reference['duration']
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.audio-fit-', dir=output.parent) as folder:
        staged = Path(folder) / 'staged.wav'
        rendered = Path(folder) / 'rendered.wav'
        options = ['-ar', str(rate), '-ac', str(channels), '-c:a', target['codec']]
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-af', f'apad=whole_dur={duration},atrim=duration={duration}', *options, str(staged)], check=True)
        measured_peak = peak(staged)
        gain = peak_db-measured_peak if measured_peak is not None else 0
        fade = min(.04, duration)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(staged), '-af', f'volume={gain}dB,afade=t=out:st={duration-fade}:d={fade}', *options, str(rendered)], check=True)
        result = measure(rendered)
        if abs(result['duration']-duration)>1/rate or result['sample_rate']!=rate or result['channels']!=channels or result['codec']!=target['codec']:
            raise ValueError('Rendered audio does not match the target contract')
        os.replace(rendered, output)
    return result


def main():
    parser = argparse.ArgumentParser(description='Measure audio or fit a cue to a reference')
    parser.add_argument('operation', choices=['measure', 'fit'])
    parser.add_argument('input')
    parser.add_argument('original', nargs='?')
    parser.add_argument('output', nargs='?')
    parser.add_argument('peak', nargs='?', type=float, default=-3)
    parser.add_argument('--format', choices=['reference', 'engine'], default='reference')
    parser.add_argument('--profile')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.operation == 'measure':
        result = measure(args.input)
    else:
        if not args.original or not args.output:
            parser.error('fit requires input original output')
        profile = json.loads(Path(args.profile).read_text()) if args.profile else None
        result = fit(args.input, args.original, args.output, args.peak, args.format, profile)
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
