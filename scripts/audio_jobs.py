import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
AIML = 'https://api.aimlapi.com/v2/generate/audio'
VENICE = 'https://api.venice.ai/api/v1'


def aimlapi_request(url, key, data=None, method='GET'):
    from slotgen_provider.http import request_json
    for attempt in range(1 if method == 'POST' else 5):
        try:
            return request_json(method, url, token=key, allowed_origins={'https://api.aimlapi.com'}, body=data, timeout=90, user_agent=UA)
        except OSError:
            if attempt == 4 or method == 'POST':
                raise
            time.sleep(4)


def run_audio(provider, *, prompt=None, model=None, seconds=2, output=None, negative=None,
              raw_only=False, job_file=None, action='auto', max_polls=70, poll_interval=6):
    from slotgen_provider.env import provider_key
    from slotgen_provider.http import request_bytes, download_artifact
    from slotgen_provider.jobs import load_job, submit_job, resume_job
    job = Path(job_file) if job_file else Path(str(output)+'.job.json') if output else None
    if job is None or max_polls < 1 or poll_interval < 0:
        raise ValueError('Expected job/output path and valid polling parameters')

    def venice(path, body):
        return request_bytes('POST', VENICE+path, token=provider_key('VENICE_API_KEY'), allowed_origins={'https://api.venice.ai'}, body=body, user_agent=UA)

    if action in ('auto', 'submit'):
        if not prompt or not output:
            raise ValueError('Submission requires prompt and output; use resume for an existing job')
        if provider == 'venice' and (len(prompt)>240 or not 0.5<=seconds<=30):
            raise ValueError('Venice SFX requires at most 240 prompt characters and 0.5..30 seconds')
        model = model or ('lyria2' if provider=='aimlapi' else 'elevenlabs-sound-effects-v2')
        meta = {'provider': provider, 'model': model, 'prompt': prompt, 'seconds': seconds, 'negative': negative,
                'output': str(Path(output).resolve()), 'raw_only': raw_only}
        def submit():
            if provider == 'aimlapi':
                body = {'model': model, 'prompt': prompt}
                if model == 'stable-audio' and seconds:
                    body['seconds_total'] = int(seconds)
                if negative:
                    body['negative_prompt'] = negative
                receipt = aimlapi_request(AIML, provider_key('AIMLAPI_KEY'), body, 'POST')
                return {'id': receipt.get('id') or receipt.get('generation_id')}
            payload, _ = venice('/audio/queue', {'model': model, 'prompt': prompt, 'duration_seconds': max(1,int(round(seconds)))})
            return {'id': json.loads(payload).get('queue_id')}
        if action == 'auto' and job.exists():
            if load_job(job)['metadata'] != meta:
                raise ValueError('Existing job uses different inputs; choose a new job file explicitly')
        else:
            submit_job(job, meta, submit)
        if action == 'submit':
            return str(job)
    state = load_job(job)
    if state['metadata']['provider'] != provider:
        raise ValueError('Job provider mismatch')

    def poll(state):
        if action == 'download':
            raise ValueError('Job not ready; resume polling first')
        if provider == 'aimlapi':
            data = aimlapi_request(AIML+'?generation_id='+str(state['id']), provider_key('AIMLAPI_KEY'))
            if data.get('status') == 'completed':
                url = (data.get('audio_file') or {}).get('url')
                if not url:
                    raise ValueError('Completed audio job has no URL')
                return {'status': 'ready', 'url': url}
        else:
            payload, headers = venice('/audio/retrieve', {'model': state['metadata']['model'], 'queue_id': state['id']})
            if any(kind in headers.get('content-type','') for kind in ('audio','octet-stream')):
                source = job.resolve().with_name(job.name+'.source')
                with tempfile.NamedTemporaryFile(dir=job.parent, delete=False) as temporary:
                    temporary.write(payload)
                    tempname = temporary.name
                os.replace(tempname, source)
                return {'status': 'ready', 'source': str(source)}
            data = json.loads(payload)
        return {'status': 'failed' if str(data.get('status','')).lower() in ('failed','error','canceled') else 'running'}

    def download(state):
        meta = state['metadata']
        target = Path(meta['output'])
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.audio-download-',dir=target.parent) as folder:
            source = Path(state['source']) if provider=='venice' else Path(folder)/'source'
            if provider == 'aimlapi':
                download_artifact(state['url'], source, allowed_hosts={urlsplit(state['url']).hostname}, user_agent=UA)
            rendered = Path(folder)/'rendered.wav'
            if meta['raw_only']:
                import shutil
                shutil.copyfile(source,rendered)
            else:
                subprocess.run(['ffmpeg','-v','error','-i',str(source),'-ar','48000','-ac','2','-c:a','pcm_f32le',str(rendered)],check=True)
            from audio_metrics import probe
            probe(rendered)
            os.replace(rendered,target)
        if provider == 'venice':
            try:
                venice('/audio/complete',{'model':meta['model'],'queue_id':state['id']})
            except (ValueError,RuntimeError,OSError):
                print('Artifact saved; provider completion acknowledgement could not be confirmed',flush=True)

    for _ in range(max_polls):
        state = resume_job(job,poll,download)
        print(json.dumps({'id':state['id'],'status':state['status']}),flush=True)
        if state['status']=='downloaded':
            return state['metadata']['output']
        time.sleep(poll_interval)
    raise TimeoutError('Audio still pending; resume the saved job instead of submitting again')


def main(provider):
    parser=argparse.ArgumentParser(description='Persistent audio jobs: submit, resume or download without duplicate generation')
    parser.add_argument('--action',choices=['auto','submit','resume','download'],default='auto')
    parser.add_argument('--prompt')
    parser.add_argument('--out')
    parser.add_argument('--job-file')
    parser.add_argument('--model')
    parser.add_argument('--seconds',type=float,default=2 if provider == 'venice' else None)
    parser.add_argument('--negative')
    parser.add_argument('--raw',action='store_true')
    parser.add_argument('--max-polls',type=int,default=70)
    parser.add_argument('--poll-interval',type=float,default=6)
    args=parser.parse_args()
    print(run_audio(provider,prompt=args.prompt,model=args.model,seconds=args.seconds,output=args.out,negative=args.negative,
                    raw_only=args.raw,job_file=args.job_file,action=args.action,max_polls=args.max_polls,poll_interval=args.poll_interval))
