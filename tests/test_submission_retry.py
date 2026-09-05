import importlib.util
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('aimlapi_music', Path(__file__).resolve().parents[1] / 'scripts/aimlapi_music.py')
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


class SubmissionRetryTests(unittest.TestCase):
    def test_ambiguous_submit_is_not_repeated(self):
        with patch('slotgen_provider.http._open_once', side_effect=TimeoutError('timeout')) as send, patch('time.sleep'):
            with self.assertRaises(RuntimeError):
                music.req(music.GEN, 'fixture', {'model': 'lyria2'}, 'POST')
        self.assertEqual(send.call_count, 1)
