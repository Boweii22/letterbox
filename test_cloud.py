import io, json, os, unittest
from unittest.mock import patch
import gemma_cloud

class CloudAdapterTests(unittest.TestCase):
    def data(self):
        return {'model': gemma_cloud.MODEL, 'messages': [{'content': 'Fictional sentence. Return JSON.'}],
            'format': {'properties': {'s0': {'type': 'string'}}}}
    def invoke(self, response):
        with patch.dict(os.environ, {'GEMMA_API_KEY': 'test-only-not-a-key'}), \
             patch('sponsors.refresh_config'), patch('sponsors.provider_budget'), \
             patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as call:
            result = gemma_cloud.request('/api/chat', self.data(), timeout=180)
            req = call.call_args.args[0]
            self.assertEqual(req.full_url, gemma_cloud.ENDPOINT + ':generateContent')
            self.assertEqual(call.call_args.kwargs['timeout'], 45)
            self.assertNotIn('test-only-not-a-key', req.full_url)
            return result
    def test_json_output_and_thought_exclusion(self):
        result = self.invoke({'candidates': [{'content': {'parts': [
            {'thought': True, 'text': 'internal'}, {'text': '```json\n{"s0":"Bring the letter."}\n```'}]}}],
            'usageMetadata': {'promptTokenCount': 12, 'candidatesTokenCount': 7}})
        self.assertEqual(json.loads(result['message']['content']), {'s0': 'Bring the letter.'})
        self.assertEqual(result['eval_count'], 7)
    def test_unexpected_claim_key_rejected(self):
        with self.assertRaises(ValueError):
            self.invoke({'candidates': [{'content': {'parts': [{'text': '{"s0":"OK","s1":"Invented"}'}]}}]})
    def test_no_paid_model_fallback(self):
        with patch.dict(os.environ, {'GEMMA_API_KEY': 'test-only'}), patch('sponsors.refresh_config'):
            data = self.data(); data['model'] = 'gemini-paid'
            with self.assertRaises(ValueError): gemma_cloud.request('/api/chat', data)
    def test_missing_key_does_not_advertise_connection(self):
        with patch.dict(os.environ, {}, clear=True), patch('sponsors.refresh_config'):
            self.assertEqual(gemma_cloud.request('/api/tags')['models'], [])

if __name__ == '__main__': unittest.main()
