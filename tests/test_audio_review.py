import importlib.util
import base64
import json
import io
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('audio_review', ROOT / 'scripts/audio_review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class AudioReviewTests(unittest.TestCase):
    def tone(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.3', str(path)], check=True)

    def stream(self, content, finish='stop', done=True, model='qwen/qwen3.8-omni-flash'):
        events = [
            {'id': 'request-test', 'model': model, 'choices': [{'index': 0, 'delta': {'content': content[:10]}, 'finish_reason': None}]},
            {'choices': [{'index': 0, 'delta': {'content': content[10:]}, 'finish_reason': finish}]},
            {'choices': [], 'usage': {'prompt_tokens': 50, 'completion_tokens': 20}, 'meta': {'usage': {'usd_spent': 0.001}}},
        ]
        text = ''.join('data: ' + json.dumps(e) + '\n\n' for e in events)
        return (text + ('data: [DONE]\n\n' if done else '')).encode()

    def answer(self):
        return {'audio_accessible': True, 'description': 'Three ascending metallic cues.',
                'issues': [], 'uncertainties': [], 'comparison': None,
                'generation_prompt_en': None, 'suggested_duration_seconds': None}

    def test_qwen38_uses_openrouter_raw_audio_and_explicit_completion_budget(self):
        audio = b'example MP3 bytes'
        content = [{'type': 'input_audio', 'input_audio': {'data': base64.b64encode(audio).decode(), 'format': 'mp3'}}]
        payload = self.stream(json.dumps(self.answer()))
        with patch('slotgen_provider.env.provider_key', return_value='test-credential') as credential, patch(
            'slotgen_provider.http.request_bytes', return_value=(payload, {'content-type': 'text/event-stream'})
        ) as request:
            result = review.call(content, max_tokens=9876)
        credential.assert_called_once_with('OPENROUTER_KEY')
        self.assertEqual(request.call_args.args, ('POST', 'https://openrouter.ai/api/v1/chat/completions'))
        self.assertEqual(request.call_args.kwargs['allowed_origins'], {'https://openrouter.ai'})
        body = request.call_args.kwargs['body']
        self.assertEqual(body['model'], 'qwen/qwen3.8-omni-flash')
        self.assertTrue(body['stream'])
        self.assertEqual(body['modalities'], ['text'])
        self.assertEqual(body['max_completion_tokens'], 9876)
        self.assertNotIn('max_tokens', body)
        self.assertNotIn('reasoning', body)
        self.assertEqual(base64.b64decode(body['messages'][0]['content'][0]['input_audio']['data']), audio)
        self.assertEqual(result['review']['description'], self.answer()['description'])
        self.assertEqual(result['usage']['prompt_tokens'], 50)
        self.assertEqual(result['meta']['usage']['usd_spent'], 0.001)

    def test_default_request_has_no_completion_cap(self):
        payload = self.stream(json.dumps(self.answer()))
        with patch('slotgen_provider.env.provider_key', return_value='test-credential') as credential, patch(
            'slotgen_provider.http.request_bytes', return_value=(payload, {})
        ) as request:
            review.call([])
        credential.assert_called_once_with('OPENROUTER_KEY')
        body = request.call_args.kwargs['body']
        self.assertEqual(body['model'], 'qwen/qwen3.8-omni-flash')
        self.assertNotIn('max_completion_tokens', body)
        self.assertNotIn('max_tokens', body)

    def test_removed_qwen35_cli_route_is_rejected_before_provider_call(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'cue.wav', Path(folder) / 'review.json'
            self.tone(source)
            with patch('slotgen_provider.http.request_bytes', return_value=(self.stream(json.dumps(self.answer())), {})) as request, patch('sys.stderr', new_callable=io.StringIO), patch('sys.stdout', new_callable=io.StringIO), self.assertRaises(SystemExit) as error:
                review.main(['describe', str(source), '--model', 'alibaba/qwen3.5-omni-plus', '--out', str(output)])
            self.assertEqual(error.exception.code, 2)
            request.assert_not_called()

    def test_stream_errors_after_partial_text_are_not_reviews(self):
        payload = self.stream('partial', done=False) + b'data: {"error":{"message":"Invalid audio URL","request_id":"failed-id"}}\n\ndata: [DONE]\n\n'
        with self.assertRaises(ValueError):
            review.parse_response(payload)

    def test_stream_without_terminal_done_is_incomplete(self):
        with self.assertRaises(ValueError):
            review.parse_response(self.stream(json.dumps(self.answer()), done=False))

    def test_malformed_choices_are_a_review_failure(self):
        for choices in [{'index': 0}, ['invalid']]:
            with self.subTest(choices=choices), self.assertRaises(ValueError):
                review.parse_response(json.dumps({'choices': choices}).encode())

    def test_invalid_issue_shape_is_rejected(self):
        answer = {**self.answer(), 'issues': [42]}
        with self.assertRaises(ValueError):
            review.parse_response(self.stream(json.dumps(answer)))

    def test_truncation_refusal_and_unavailable_audio_are_incomplete(self):
        for answer, finish in [(self.answer(), 'length'), ({**self.answer(), 'audio_accessible': False}, 'stop'), ({**self.answer(), 'description': ''}, 'stop')]:
            with self.subTest(answer=answer, finish=finish), self.assertRaises(ValueError):
                review.parse_response(self.stream(json.dumps(answer), finish=finish))
        with self.assertRaises(ValueError):
            review.parse_response(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'refusal': 'Cannot analyze', 'content': json.dumps(self.answer())}}]}).encode())

    def test_silence_is_measured_only_in_selected_window(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'mixed.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-af', 'apad=whole_dur=2', '-t', '2', str(source)], check=True)
            _, tone = review.prepare_audio(source, [0, 0.5])
            _, silence = review.prepare_audio(source, [1.2, 2])
            self.assertFalse(tone['digital_silence'])
            self.assertTrue(silence['digital_silence'])
            self.assertEqual(silence['rendered_duration'], 2)

    def test_silent_input_creates_local_report_without_provider_call(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'silent.wav', Path(folder) / 'report.json'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', '1', str(source)], check=True)
            with patch.object(review, 'call') as call, patch('sys.stdout', new_callable=io.StringIO):
                review.main(['describe', str(source), '--out', str(output)])
            call.assert_not_called()
            report = json.loads(output.read_text())
            self.assertEqual(report['status'], 'digital_silence')
            self.assertFalse(report['provider_called'])
            self.assertEqual(report['model'], 'qwen/qwen3.8-omni-flash')
            self.assertEqual(report['provider'], 'OpenRouter')
            self.assertEqual(report['endpoint'], 'https://openrouter.ai/api/v1/chat/completions')
            self.assertIsNone(report['max_tokens'])

    def test_existing_report_is_preserved_before_network_call(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'source.wav', Path(folder) / 'report.json'
            output.write_text('keep existing evidence')
            with patch.object(review, 'call') as call, self.assertRaises(ValueError):
                review.main(['describe', str(source), '--out', str(output)])
            call.assert_not_called()
            self.assertEqual(output.read_text(), 'keep existing evidence')

    def test_transport_interruption_is_recorded_without_retry(self):
        from slotgen_provider.http import SubmissionUnknown
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'cue.wav', Path(folder) / 'report.json'
            self.tone(source)
            with patch('slotgen_provider.env.provider_key', return_value='test-credential'), patch(
                'slotgen_provider.http.request_bytes', side_effect=SubmissionUnknown('interrupted')
            ) as request, self.assertRaises(SubmissionUnknown):
                review.main(['describe', str(source), '--out', str(output)])
            self.assertEqual(request.call_count, 1)
            self.assertEqual(json.loads(output.read_text())['status'], 'submission_unknown')

    def test_provider_error_id_is_saved_without_accepting_partial_output(self):
        payload = b'data: {"error":{"message":"bad URL","request_id":"provider-42"}}\n\ndata: [DONE]\n\n'
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'cue.wav', Path(folder) / 'report.json'
            self.tone(source)
            with patch('slotgen_provider.env.provider_key', return_value='test-credential'), patch(
                'slotgen_provider.http.request_bytes', return_value=(payload, {})
            ), self.assertRaises(ValueError):
                review.main(['describe', str(source), '--out', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['failure']['provider_error']['request_id'], 'provider-42')

    def test_comparison_preserves_same_basename_inputs_and_both_audio_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / 'original/cue.wav'
            candidate = Path(folder) / 'candidate/cue.wav'
            self.tone(original)
            self.tone(candidate)
            output = Path(folder) / 'comparison.json'
            answer = {**self.answer(), 'comparison': 'Equivalent cues', 'generation_prompt_en': 'A short tonal cue', 'suggested_duration_seconds': 0.3}
            with patch('slotgen_provider.env.provider_key', return_value='test-credential'), patch(
                'slotgen_provider.http.request_bytes', return_value=(self.stream(json.dumps(answer)), {})
            ) as request, patch('sys.stdout', new_callable=io.StringIO):
                review.main(['consult', str(original), str(candidate), 'cue prompt', '--out', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(report['status'], 'complete')
            self.assertNotEqual(report['coverage']['original']['path'], report['coverage']['candidate']['path'])
            self.assertEqual(len([p for p in request.call_args.kwargs['body']['messages'][0]['content'] if p['type'] == 'input_audio']), 2)

    def test_describe_does_not_request_consult_only_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'cue.wav', Path(folder) / 'review.json'
            self.tone(source)
            with patch('slotgen_provider.env.provider_key', return_value='test-credential'), patch(
                'slotgen_provider.http.request_bytes', return_value=(self.stream(json.dumps(self.answer())), {})
            ) as request, patch('sys.stdout', new_callable=io.StringIO):
                review.main(['describe', str(source), '--out', str(output)])
            prompt = request.call_args.kwargs['body']['messages'][0]['content'][0]['text']
            self.assertNotIn('generation_prompt_en', prompt)
            self.assertNotIn('suggested_duration_seconds', prompt)

    def test_full_review_keeps_more_than_the_first_two_seconds(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'long.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', str(source)], check=True)
            audio, coverage = review.prepare_audio(source)
            self.assertEqual(coverage['end'], 3)
            self.assertTrue(coverage['full'])
            decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-ar', '8000', '-ac', '1', '-f', 's16le', 'pipe:1'], input=audio)
            self.assertGreater(len(decoded) / 16000, 2.9)
