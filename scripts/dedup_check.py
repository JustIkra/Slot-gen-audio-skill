#!/usr/bin/env python3
"""Check whether numbered SFX variants (x_1..x_n) are duplicates or distinct-but-related.

PCM MD5 catches exact dupes; normalized cross-correlation catches perceptual near-dupes.
Real slot families are distinct-but-related (corr ~0.6-0.8). corr>0.85 = effectively the same.

Usage: python3 dedup_check.py "<folder>" name1 name2 name3 ...   (names without .wav)
"""
import subprocess, sys
from itertools import combinations
import numpy as np


def load(folder, name):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", f"{folder}/{name}.wav",
                          "-ar", "48000", "-ac", "1", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    return a / (np.abs(a).max() + 1e-9)


def md5(folder, name):
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-v", "error", "-i", f"{folder}/{name}.wav",
                          "-ar", "48000", "-ac", "1", "-f", "s16le", "-"], stdout=subprocess.PIPE)
    return subprocess.run(["md5sum"], stdin=p.stdout, capture_output=True, text=True).stdout.split()[0]


def sim(a, b):
    n = min(len(a), len(b)); a, b = a[:n], b[:n]; best = 0.0
    for lag in range(-400, 401, 5):
        x, y = (a[lag:], b[:n - lag]) if lag >= 0 else (a[:n + lag], b[-lag:])
        if len(x) < 10:
            continue
        best = max(best, abs(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9)))
    return best


if __name__ == "__main__":
    folder, names = sys.argv[1], sys.argv[2:]
    md = {n: md5(folder, n) for n in names}
    print("PCM MD5 (identical hash = exact duplicate):")
    for n in names:
        print(f"  {n}: {md[n]}")
    dupe = len(set(md.values())) < len(md)
    print("  -> EXACT DUPLICATES PRESENT" if dupe else "  -> no exact duplicates")
    sig = {n: load(folder, n) for n in names}
    print("\nperceptual cross-correlation:")
    for a, b in combinations(names, 2):
        s = sim(sig[a], sig[b])
        tag = "~SAME" if s > 0.85 else "distinct" if s < 0.6 else "similar"
        print(f"  {a} vs {b}: {s:.2f}  {tag}")
