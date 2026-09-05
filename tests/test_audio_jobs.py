import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audio_jobs import run_audio


class Response:
    def __init__(self,payload,kind='application/json'):
        self.status=200;self.headers={'content-type':kind};self.body=io.BytesIO(payload)
    def read(self,n=-1):return self.body.read(n)
    def close(self):pass


class AudioJobsTests(unittest.TestCase):
    def test_venice_queue_and_binary_retrieve_keep_one_submission(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fixture=root/'fixture.wav'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.1',str(fixture)],check=True)
            payload=fixture.read_bytes();sent=[]
            def send(method,url,headers,body,timeout):
                sent.append(url)
                if url.endswith('/queue'):return Response(b'{"queue_id":"task-2"}')
                if url.endswith('/retrieve'):return Response(payload,'audio/wav')
                if url.endswith('/complete'):return Response(b'{}')
                self.fail('Unexpected request')
            output=root/'accepted.wav';job=root/'job.json'
            with patch('slotgen_provider.env.provider_key',return_value='fixture-key'),patch('slotgen_provider.http._open_once',side_effect=send):
                run_audio('venice',prompt='fixture',output=output,job_file=job,poll_interval=0)
                count=len(sent)
                run_audio('venice',job_file=job,action='resume')
            self.assertEqual(sum(url.endswith('/queue') for url in sent),1)
            self.assertEqual(len(sent),count)
            self.assertEqual(json.loads(job.read_text())['status'],'downloaded')

    def test_adapter_resume_uses_saved_job_without_duplicate_submit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fixture=root/'fixture.wav'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.1',str(fixture)],check=True)
            payload=fixture.read_bytes();sent=[]
            def send(method,url,headers,body,timeout):
                sent.append((method,url,headers))
                if method=='POST':return Response(b'{"id":"task-1"}')
                if 'generation_id=' in url:return Response(b'{"status":"completed","audio_file":{"url":"https://cdn.example/audio.wav"}}')
                return Response(payload,'audio/wav')
            output=root/'accepted.wav';job=root/'job.json'
            with patch('slotgen_provider.env.provider_key',return_value='fixture-key'),patch('slotgen_provider.http._open_once',side_effect=send):
                run_audio('aimlapi',prompt='fixture',output=output,job_file=job,poll_interval=0,max_polls=2)
                count=len(sent)
                run_audio('aimlapi',job_file=job,action='resume')
            self.assertEqual(len(sent),count)
            self.assertEqual(sum(method=='POST' for method,_,_ in sent),1)
            self.assertNotIn('Authorization',sent[-1][2])
            self.assertNotIn('fixture-key',job.read_text())
            self.assertEqual(json.loads(job.read_text())['status'],'downloaded')
            self.assertGreater(output.stat().st_size,100)
