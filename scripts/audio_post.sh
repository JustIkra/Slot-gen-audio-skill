#!/usr/bin/env bash
# Post-processing recipes for slot SFX/music. Engine target: 48000 Hz / Float32 / stereo.
# Run with bash (not zsh) so $vars word-split normally; args are quoted anyway.
#
# Subcommands:
#   convert   <in> <out>                       -> 48k/Float32/stereo
#   normalize <in> <out> <peak_db>             -> peak-normalize to <peak_db> dBFS (e.g. -3, -12)
#   music     <in> <out>                       -> loudnorm I=-18 TP=-1.5 (calm bg)
#   dull      <in> <out> <lowpass_hz>          -> tame highs (e.g. 5000); kills "cuts the ears"
#   flatten   <in> <out>                       -> kill crescendo (dynaudnorm)
#   peakshelf <in> <out> <peak_db>             -> CONSTANT peak shelf (match a steady original)
#   family    <base.wav> <outdir> <count>      -> one base -> <prefix>_1..count via micro-pitch
#   fit       <in> <original> <out> [peak_db]  -> match original duration+format, peak-normalize
#   spectral  <file>                           -> high-band energy gate (harshness proxy)
#   envelope  <file>                           -> peak level per ~0.1s window
set -e
ff(){ ffmpeg -y -loglevel error "$@"; }
maxvol(){ ffmpeg -hide_banner -i "$1" -af volumedetect -f null /dev/null 2>&1 | sed -n 's/.*max_volume: \(.*\) dB/\1/p'; }
dur(){ afinfo "$1" 2>/dev/null | sed -n 's/.*estimated duration: \([0-9.]*\).*/\1/p'; }

cmd="$1"; shift
case "$cmd" in
  convert) ff -i "$1" -ar 48000 -ac 2 -c:a pcm_f32le "$2" ;;
  normalize)
    g=$(awk "BEGIN{printf \"%.2f\", ($3)-($(maxvol "$1"))}")
    ff -i "$1" -af "volume=${g}dB" -ar 48000 -ac 2 -c:a pcm_f32le "$2" ;;
  music) ff -i "$1" -af "loudnorm=I=-18:TP=-1.5:LRA=11" -ar 48000 -ac 2 -c:a pcm_f32le "$2" ;;
  dull) ff -i "$1" -af "lowpass=f=$3:poles=2,lowpass=f=$3:poles=2" -ar 48000 -ac 2 -c:a pcm_f32le "$2" ;;
  flatten) ff -i "$1" -af "dynaudnorm=f=120:g=11" -ar 48000 -ac 2 -c:a pcm_f32le "$2" ;;
  peakshelf)
    lin=$(awk "BEGIN{printf \"%.4f\", exp(($3)*0.11512925)}")  # 10^(db/20)
    ff -i "$1" -af "dynaudnorm=f=100:g=15,volume=12dB,alimiter=limit=${lin}:level=disabled" -ar 48000 -ac 2 -c:a pcm_f32le "$2" ;;
  family)
    base="$1"; outdir="$2"; count="$3"
    name=$(basename "$base" .wav); prefix="${name%_base}"
    factors=(1.000 1.020 0.980 1.012 0.988 1.006 0.994 1.024)
    # align to onset so short hits aren't cut to silence
    ff -i "$base" -af "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.01" "$outdir/_fbase.wav"
    for i in $(seq 1 "$count"); do
      p="${factors[$((i-1))]}"; [ -z "$p" ] && p=1.000
      ff -i "$outdir/_fbase.wav" -af "asetrate=48000*${p},aresample=48000" -ar 48000 -ac 2 -c:a pcm_f32le "$outdir/${prefix}_${i}.wav"
    done
    rm -f "$outdir/_fbase.wav"
    echo "wrote ${prefix}_1..${count}.wav in $outdir" ;;
  fit)
    "${PYTHON:-python3}" "$(dirname "$0")/audio_metrics.py" fit "$@" ;;
  spectral)
    full=$(maxvol "$1")
    hi=$(ffmpeg -hide_banner -i "$1" -af "highpass=f=6000,volumedetect" -f null /dev/null 2>&1 | sed -n 's/.*max_volume: //p')
    echo "full max=$full dB ; energy >6kHz max=$hi  (lower >6k = duller = safer)" ;;
  envelope)
    ffmpeg -hide_banner -i "$1" -af "astats=metadata=1:reset=4800,ametadata=print:key=lavfi.astats.Overall.Peak_level" -f null /dev/null 2>&1 | sed -n 's/.*Peak_level=//p' | tr '\n' ' '; echo ;;
  *) echo "unknown subcommand: $cmd"; sed -n '2,20p' "$0" ;;
esac
