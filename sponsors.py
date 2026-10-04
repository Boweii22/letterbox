"""Optional integrations. Credentials, letters and recordings never enter traces."""
from contextlib import contextmanager
import datetime, functools, json, os, re, secrets, sys, threading, time
from pathlib import Path
import urllib.parse, urllib.request

ROOT=Path(__file__).resolve().parent
WORK=Path(os.environ.get('LETTERBOX_DATA_DIR') or ROOT/'runtime')
KEYS={'GEMMA_API_KEY','SENTRY_DSN','ELEVENLABS_API_KEY','ELEVENLABS_VOICE_ID','SERPAPI_API_KEY','MONGODB_URI','BACKBOARD_API_KEY','TIGER_DATABASE_URL','TABPFN_TOKEN','LETTERBOX_OLLAMA','LETTERBOX_OLLAMA_KEY','LETTERBOX_PUBLIC_ORIGIN'}
def load_config():
    path=WORK/'secrets.json'
    try:
        for k,v in json.loads(path.read_text(encoding='utf-8')).items():
            if k in KEYS and isinstance(v,str) and v:os.environ.setdefault(k,v)
    except (OSError,ValueError):pass
load_config()
if (WORK/'vendor').exists():sys.path.insert(0,str(WORK/'vendor'))
SDK=None
SAFE_DATA={'gen_ai.system','gen_ai.request.model','gen_ai.agent.name','gen_ai.operation.name','gen_ai.usage.input_tokens','gen_ai.usage.output_tokens','letterbox.candidates','letterbox.matched','letterbox.flagged','letterbox.total','letterbox.language'}
LOCK=threading.Lock()
def provider_budget(provider,limit):
    """Bound provider usage across restarts; failed attempts also consume the budget."""
    with LOCK:
        WORK.mkdir(parents=True,exist_ok=True);path=WORK/'provider-usage.json'
        try:usage=json.loads(path.read_text())
        except (OSError,ValueError):usage={}
        day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        if usage.get('day')!=day:usage={'day':day}
        count=usage.get(provider,0)
        if count>=limit:raise ValueError('This public test has reached its daily '+provider+' limit. Try again tomorrow.')
        usage[provider]=count+1
        temporary=WORK/'provider-usage.pending.json';temporary.write_text(json.dumps(usage));temporary.replace(path)
CONFIG_MTIME=None
def refresh_config():
    global CONFIG_MTIME
    try:
        stamp=(WORK/'secrets.json').stat().st_mtime_ns
        if stamp==CONFIG_MTIME:return
        config=json.loads((WORK/'secrets.json').read_text(encoding='utf-8'))
        for k,v in config.items():
            if k in KEYS and isinstance(v,str):
                if v:os.environ[k]=v
                else:os.environ.pop(k,None)
        CONFIG_MTIME=stamp
        init_sentry()
        if os.environ.get('MONGODB_URI') and QUEUE is None:_atlas_worker()
    except (OSError,ValueError):pass
def sanitized_transaction(event,hint=None):
    """Allowlist rather than trying to redact arbitrary prompts and exception locals."""
    clean={k:event[k] for k in ('event_id','type','timestamp','start_timestamp','platform','release','environment') if k in event}
    clean['transaction']='Letterbox analysis'
    trace=event.get('contexts',{}).get('trace',{})
    clean['contexts']={'trace':{k:trace[k] for k in ('trace_id','span_id','parent_span_id','op','status') if k in trace}}
    clean['spans']=[]
    for span in event.get('spans',[]):
        item={k:span[k] for k in ('trace_id','span_id','parent_span_id','start_timestamp','timestamp','status') if k in span}
        item['op']=span.get('op') if span.get('op') in ('gen_ai.request','gen_ai.execute_tool') else 'letterbox.step'
        item['description']=span.get('description') if span.get('description') in ('Select source excerpts','Gemma paraphrase','Check supporting quotes','Read photo','Prepare speech') else 'Letterbox step'
        strings={'gen_ai.system':{'ollama','google'},'gen_ai.request.model':{'gemma3:270m','gemma3:1b','gemma-4-26b-a4b-it'},'gen_ai.agent.name':{'Letterbox'},'gen_ai.operation.name':{'chat'}}
        item['data']={k:v for k,v in span.get('data',{}).items() if k in SAFE_DATA and (isinstance(v,(int,float,bool)) or isinstance(v,str) and v in strings.get(k,set()))}
        clean['spans'].append(item)
    return clean
def init_sentry():
    global SDK
    if not os.environ.get('SENTRY_DSN'):return
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=os.environ['SENTRY_DSN'],traces_sample_rate=1.0,send_default_pii=False,
            stream_gen_ai_spans=False,trace_lifecycle='static',
            default_integrations=False,auto_enabling_integrations=False,include_local_variables=False,
            before_send=lambda event,hint:None,before_send_transaction=sanitized_transaction,
            max_breadcrumbs=0,release='letterbox@2.0',environment=os.environ.get('LETTERBOX_ENV','public-test'))
        SDK=sentry_sdk
    except Exception:SDK=None
init_sentry()

@contextmanager
def span(name,op='gen_ai.execute_tool'):
    if SDK:
        with SDK.start_span(op=op,name=name) as value:yield value
    else:yield None

def instrument(name,op='gen_ai.execute_tool'):
    def decorate(fn):
        @functools.wraps(fn)
        def run(*args,**kwargs):
            with span(name,op) as step:
                result=fn(*args,**kwargs)
                if step and isinstance(result,list):
                    step.set_data('letterbox.candidates',len(result))
                    if name=='Check supporting quotes':
                        step.set_data('letterbox.matched',sum(bool(d.get('matched')) for d in result))
                        step.set_data('letterbox.flagged',sum(bool(d.get('issues')) for d in result))
                return result
        return run
    return decorate

def safe_run(result,elapsed,failed=False):
    metrics=result.get('metrics',{})
    model=result.get('model')
    return {'id':secrets.token_hex(12),'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'model':model if model in ('gemma3:270m','gemma3:1b','gemma-4-26b-a4b-it') else None,
        'elapsed_seconds':round(elapsed,3),'output_tokens':int(metrics.get('output_tokens',0)),
        'matched':int(metrics.get('matched',0)),'total':int(metrics.get('total',0)),
        'flagged':sum(bool(d.get('issues')) for d in result.get('details',[])),
        'failed':bool(failed),'mode':result.get('mode') if result.get('mode') in ('local','cloud','source') else None}

QUEUE=None
def _atlas_worker():
    import queue
    global QUEUE
    QUEUE=queue.Queue(maxsize=64)
    def consume():
        client=None
        while True:
            record=QUEUE.get()
            try:
                if client is None:
                    from pymongo import MongoClient
                    client=MongoClient(os.environ['MONGODB_URI'],serverSelectionTimeoutMS=3000,connectTimeoutMS=3000,socketTimeoutMS=3000)
                client['letterbox']['analysis_metrics'].insert_one(dict(record))
            except Exception:
                pass  # Optional analytics must not break letter analysis.
            finally:QUEUE.task_done()
    threading.Thread(target=consume,daemon=True).start()
if os.environ.get('MONGODB_URI'):_atlas_worker()

def record_run(record):
    try:
        WORK.mkdir(parents=True,exist_ok=True)
        with LOCK:
            p=WORK/'runs.jsonl'
            if p.exists() and p.stat().st_size>2*1024*1024:p.replace(WORK/'runs.previous.jsonl')
            with p.open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
        if QUEUE:
            try:QUEUE.put_nowait(dict(record))
            except Exception:pass
    except OSError:pass

def traced_analysis(fn):
    @functools.wraps(fn)
    def run(*args,**kwargs):
        refresh_config()
        started=time.perf_counter();result={};failed=True
        with SDK.start_transaction(name='Letterbox analysis',op='gen_ai.invoke_agent') if SDK else span('Letterbox analysis'):
            try:
                result=fn(*args,**kwargs);failed=False;return result
            finally:
                record=safe_run(result,time.perf_counter()-started,failed)
                # Only a length, never source text. Available before inference for forecasting.
                source=args[0] if args else kwargs.get('text','')
                if isinstance(source,str):record['input_characters']=len(source)
                record_run(record)
    return run

def integration_status():
    refresh_config()
    return {'elevenlabs':bool(os.environ.get('ELEVENLABS_API_KEY')),
        'serpapi':bool(os.environ.get('SERPAPI_API_KEY')),'sentry':SDK is not None,
        'atlas':bool(os.environ.get('MONGODB_URI')),'backboard':bool(os.environ.get('BACKBOARD_API_KEY'))}

def speech(text,consent):
    refresh_config()
    if consent is not True:raise ValueError('Confirm sharing this explanation with ElevenLabs.')
    key=os.environ.get('ELEVENLABS_API_KEY')
    if not key:raise ValueError('ElevenLabs has not been connected. Use an installed device voice.')
    if not isinstance(text,str) or not 1<=len(text.strip())<=3000:raise ValueError('Speech text must be between 1 and 3,000 characters.')
    voice=os.environ.get('ELEVENLABS_VOICE_ID','JBFqnCBsd6RMkjVDRZzb')
    if not re.fullmatch(r'[A-Za-z0-9]{10,80}',voice):raise ValueError('Choose a valid configured voice.')
    provider_budget('speech',20)
    data={'text':text,'model_id':'eleven_multilingual_v2','voice_settings':{'stability':.45,'similarity_boost':.75,'style':.2,'use_speaker_boost':True}}
    req=urllib.request.Request('https://api.elevenlabs.io/v1/text-to-speech/'+voice+'?output_format=mp3_44100_128',data=json.dumps(data).encode(),headers={'xi-api-key':key,'Content-Type':'application/json','Accept':'audio/mpeg'})
    with span('Prepare speech'):
        with urllib.request.urlopen(req,timeout=45) as response:
            audio=response.read(5*1024*1024+1)
    if not audio or len(audio)>5*1024*1024:raise ValueError('Speech response could not be used.')
    return audio

def official_sources(organisation,consent):
    refresh_config()
    if consent is not True:raise ValueError('Confirm sharing the organisation name with SerpApi.')
    if not isinstance(organisation,str) or not re.fullmatch(r'[A-Za-z][A-Za-z .&\'-]{1,79}',organisation):raise ValueError('Enter only an organisation name, without personal details.')
    key=os.environ.get('SERPAPI_API_KEY')
    if not key:raise ValueError('Official-source lookup has not been connected.')
    provider_budget('search',30)
    params={'engine':'google','q':organisation+' official contact (site:gov.uk OR site:nhs.uk)','api_key':key,'num':'5','gl':'uk'}
    with urllib.request.urlopen('https://serpapi.com/search.json?'+urllib.parse.urlencode(params),timeout=15) as r:data=json.load(r)
    results=[]
    for item in data.get('organic_results',[]):
        link=item.get('link','');parsed=urllib.parse.urlsplit(link);host=parsed.hostname or ''
        if parsed.scheme=='https' and not parsed.username and not parsed.password and (host in ('gov.uk','nhs.uk') or host.endswith(('.gov.uk','.nhs.uk'))):
            results.append({'title':str(item.get('title','Official website'))[:150],'url':link,'snippet':str(item.get('snippet',''))[:350]})
    return {'results':results[:5],'notice':'Search results do not establish that your letter is genuine. Check contact details on the official website.'}

