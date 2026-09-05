import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('audio_review', ROOT / 'scripts/audio_review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class AudioReviewTests(unittest.TestCase):
    def test_full_review_keeps_more_than_the_first_two_seconds(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'long.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', str(source)], check=True)
            audio, coverage = review.prepare_audio(source)
            self.assertEqual(coverage['end'], 3)
            self.assertTrue(coverage['full'])
            decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-ar', '8000', '-ac', '1', '-f', 's16le', 'pipe:1'], input=audio)
            self.assertGreater(len(decoded) / 16000, 2.9)
