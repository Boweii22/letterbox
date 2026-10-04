"""Separate public testing gateway. Keeps the original private server unchanged."""
import collections
import datetime
import json
from pathlib import Path
import re
import socket
import threading
import time
import server as app

WORK=app.sponsors.WORK/'public-test'
EXPENSIVE=threading.BoundedSemaphore(1)
RATE_LOCK=threading.Lock()
RATE={}
PORT=int(app.os.environ.get('PORT','8780'))
BIND=app.os.environ.get('LETTERBOX_BIND','127.0.0.1')

def public_origin():
    try:
        configured=app.os.environ.get('LETTERBOX_PUBLIC_ORIGIN','').rstrip('/')
        if not configured and re.fullmatch(r'[a-z0-9-]+\.onrender\.com',app.os.environ.get('RENDER_EXTERNAL_HOSTNAME','')):configured='https://'+app.os.environ['RENDER_EXTERNAL_HOSTNAME']
        if configured and re.fullmatch(r'https://[a-z0-9.-]+(?::[0-9]+)?',configured):return configured
        value=(WORK/'url.txt').read_text().strip()
        return value if re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com',value) else ''
    except OSError:return ''

def allow_request(ip):
    now=time.monotonic()
    with RATE_LOCK:
        for key in list(RATE):
            if not RATE[key] or RATE[key][-1]<now-60:del RATE[key]
        if ip not in RATE and len(RATE)>=1024:return False
        events=RATE.setdefault(ip,collections.deque())
        while events and events[0]<now-60:events.popleft()
        if len(events)>=6:return False
        events.append(now)
        return True

class PublicHandler(app.Handler):
    def setup(self):
        super().setup();self.connection.settimeout(50)

    def local_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{PORT}',f'localhost:{PORT}',public_origin().removeprefix('https://'))

    def do_GET(self):
        if not self.local_host():return self.send({'error':'Invalid host.'},403)
        if self.path=='/health':return self.send({'ok':True})
        if self.path=='/api/status':
            try:
                models=[m['name'] for m in app.ollama_request('/api/tags').get('models',[]) if m['name'] in app.ALLOWED_MODELS]
                free=app.memory_info()['available_gib']
                preferred='gemma3:1b' if free is None or free>=1.8 else 'gemma3:270m'
                models.sort(key=lambda m:m!=preferred)
            except Exception:models=[]
            return self.send({'token':app.TOKEN,'connected':bool(models),'models':models,'memory':{'total_gib':None,'available_gib':None},'ocr_available':app.os.name=='nt' or app.shutil.which('tesseract') is not None,'public':True,'integrations':app.sponsors.integration_status()})
        return super().do_GET()

    def do_POST(self):
        origin=self.headers.get('Origin')
        if not self.local_host() or self.headers.get('X-Letterbox-Token')!=app.TOKEN or origin not in (None,public_origin(),f'http://127.0.0.1:{PORT}'):
            return self.send({'error':'Use the public Letterbox page to make this request.'},403)
        allowed={'/api/analyze','/api/ocr','/api/demo','/api/calendar','/api/save-calendar','/api/feedback','/api/speech','/api/official-sources'}
        if self.path not in allowed:return self.send({'error':'Not found.'},404)
        if not allow_request(self.headers.get('CF-Connecting-IP',self.client_address[0])):
            return self.send({'error':'Please wait a minute before trying again.'},429)
        acquired=False
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=15*1024*1024:return self.send({'error':'Invalid request size.'},413)
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('Invalid request.')
            if self.path in ('/api/analyze','/api/ocr','/api/speech'):
                if self.path!='/api/speech' and data.get('publicConsent') is not True:return self.send({'error':'Read the public sharing notice and confirm before submitting input.'},400)
                acquired=EXPENSIVE.acquire(blocking=False)
                if not acquired:return self.send({'error':'Someone else is using the test engine. Please try again shortly.'},429)
            if self.path=='/api/speech':return self.send(app.sponsors.speech(data.get('text'),data.get('speechConsent')),content_type='audio/mpeg')
            if self.path=='/api/official-sources':return self.send(app.sponsors.official_sources(data.get('organisation'),data.get('searchConsent')))
            if self.path=='/api/ocr':return self.send(app.ocr_image(data.get('image','')))
            if self.path=='/api/analyze':
                text=str(data.get('text','')).strip()
                if not 30<=len(text)<=9000:raise ValueError('Use one page, between 30 and 9,000 characters.')
                return self.send(app.analyze(text,data.get('model','gemma3:1b'),data.get('language','English')))
            if self.path in ('/api/calendar','/api/save-calendar'):
                calendar=app.make_calendar(data.get('date'),str(data.get('title','Letter reminder')),str(data.get('quote','')),data.get('confirmed'))
                if self.path=='/api/calendar':return self.send(calendar,content_type='text/calendar; charset=utf-8')
                return self.send({'calendar':calendar,'file_name':'letterbox-reminder.ics','saved_to':None})
            if self.path=='/api/demo':
                sample=app.SAMPLES.get(data.get('sample'))
                if not sample:raise ValueError('Unknown sample.')
                details=app.verify_details(sample['text'],sample)
                return self.send({'title':sample['name'],'details':details,'mode':'sample','model':None,'language':'English','metrics':{'elapsed_seconds':0,'matched':len(details),'total':len(details),'output_tokens':0}})
            if self.path=='/api/feedback':
                if data.get('helpful') not in ('Yes','A little','No','Only tried the example'):raise ValueError('Choose a feedback answer.')
                text=str(data.get('text','')).strip()
                if not 5<=len(text)<=1000:raise ValueError('Use between 5 and 1,000 characters.')
                WORK.mkdir(exist_ok=True,parents=True)
                record={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'helpful':data['helpful'],'text':text}
                with RATE_LOCK:
                    path=WORK/'feedback.jsonl'
                    if path.exists() and path.stat().st_size>2*1024*1024:return self.send({'error':'Feedback collection is full.'},503)
                    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
                return self.send({'received':True})
        except ValueError as error:self.send({'error':str(error)},400)
        except Exception:self.send({'error':'The test engine could not finish. Please try again or use a fictional example.'},503)
        finally:
            if acquired:EXPENSIVE.release()

class LimitedServer(app.ThreadingHTTPServer):
    daemon_threads=True
    slots=threading.BoundedSemaphore(12)
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            request.close();return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()

if __name__=='__main__':
    LimitedServer((BIND,PORT),PublicHandler).serve_forever()
