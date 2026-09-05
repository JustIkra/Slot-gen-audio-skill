import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AudioPostTests(unittest.TestCase):
    def test_short_input_is_padded_and_matches_reference_format(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, duration in [('short', '0.25'), ('original', '1')]:
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}', '-ar', '22050', '-ac', '1', str(root / f'{name}.wav')], check=True)
            subprocess.run(['bash', str(ROOT / 'scripts/audio_post.sh'), 'fit', str(root/'short.wav'), str(root/'original.wav'), str(root/'fitted.wav')], check=True, capture_output=True)
            report = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=sample_rate,channels', '-of', 'json', str(root/'fitted.wav')]))
            self.assertLessEqual(abs(float(report['format']['duration'])-1), 1/22050)
            self.assertEqual(report['streams'][0]['sample_rate'], '22050')
            self.assertEqual(report['streams'][0]['channels'], 1)
