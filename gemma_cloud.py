"""Hosted Gemma adapter. No local engine or paid model fallback."""
import json, os, re, urllib.request
import sponsors

MODEL = 'gemma-4-26b-a4b-it'
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/' + MODEL

def request(path, data=None, timeout=5):
    sponsors.refresh_config()
    key = os.environ.get('GEMMA_API_KEY')
    if path == '/api/tags':
        return {'models': [{'name': MODEL}] if key else []}
    if path != '/api/chat' or not key or data.get('model') != MODEL:
        raise ValueError('The hosted Gemma connection is not configured.')
    sponsors.provider_budget('gemma', 60)
    payload = {'contents': [{'role': 'user', 'parts': [{'text': '\n'.join(
        item['content'] for item in data['messages'])}]}],
        'generationConfig': {'temperature': 0, 'maxOutputTokens': 1500,
            'thinkingConfig': {'thinkingLevel': 'minimal'}}}
    req = urllib.request.Request(ENDPOINT + ':generateContent',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    with sponsors.span('Gemma paraphrase', 'gen_ai.request') as span:
        with urllib.request.urlopen(req, timeout=min(timeout, 45)) as response:
            result = json.load(response)
        parts = result.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        content = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip())
        parsed = json.loads(content)
        expected = data['format']['properties']
        if not isinstance(parsed, dict) or set(parsed) != set(expected) or any(not isinstance(v, str) for v in parsed.values()):
            raise ValueError('Gemma returned an unexpected format. Check the original and retry.')
        usage = result.get('usageMetadata', {})
        if span:
            span.set_data('gen_ai.system', 'google'); span.set_data('gen_ai.request.model', MODEL)
            span.set_data('gen_ai.operation.name', 'chat')
            span.set_data('gen_ai.usage.input_tokens', usage.get('promptTokenCount', 0))
            span.set_data('gen_ai.usage.output_tokens', usage.get('candidatesTokenCount', 0))
        return {'message': {'content': json.dumps(parsed)},
            'eval_count': usage.get('candidatesTokenCount', 0),
            'prompt_eval_count': usage.get('promptTokenCount', 0)}
