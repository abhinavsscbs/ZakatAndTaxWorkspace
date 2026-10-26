"""Direct global OpenAI and Cohere APIs; credentials never reach the browser."""
import os
import time
import random
import requests
from flask import g
from telemetry import step

MODELS = {
    'openai': {'chat': os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), 'embedding': os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')},
    'cohere': {'chat': os.getenv('COHERE_MODEL', 'command-a-03-2025'), 'embedding': os.getenv('COHERE_EMBEDDING_MODEL', 'embed-v4.0')},
}

class ProviderError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status

class AIClient:
    @property
    def provider(self):
        return g.provider

    def _post(self, endpoint, payload, row):
        key = os.getenv(f'{self.provider.upper()}_API_KEY', '')
        if not key:
            raise ProviderError(f'{self.provider.upper()}_API_KEY is not configured', 503)
        base = 'https://api.openai.com/v1' if self.provider == 'openai' else 'https://api.cohere.com/v2'
        for attempt in range(3):
            row['attempts'] = attempt + 1
            try:
                response = requests.post(base + endpoint, json=payload, headers={'Authorization': f'Bearer {key}'}, timeout=(10, 180))
            except requests.RequestException as exc:
                raise ProviderError('Provider connection failed or timed out') from exc
            row['http_status'] = response.status_code
            row['rate_limits'] = {k: v for k, v in response.headers.items() if k.lower().startswith(('x-ratelimit', 'ratelimit', 'retry-after'))}
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                try:
                    delay = float(response.headers.get('Retry-After', 2 ** attempt))
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(min(max(delay, 0), 30) + random.random() * .2)
                continue
            row['provider_request_id'] = response.headers.get('x-request-id')
            if not response.ok:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                error = body.get('error', {}) if isinstance(body, dict) else {}
                if not isinstance(error, dict):
                    error = {}
                row['provider_error_code'] = error.get('code')
                row['provider_error_param'] = error.get('param')
                reason = error.get('message') or (body.get('message') if isinstance(body, dict) else None) or 'Provider did not return error details'
                reason = str(reason).replace(key, '[redacted]')[:800]
                status = 429 if response.status_code == 429 else 400 if response.status_code == 400 else 502
                raise ProviderError(f'{self.provider} API returned HTTP {response.status_code}: {reason}', status)
            data = response.json()
            row['usage'] = data.get('usage', data.get('meta', {}).get('billed_units', {}))
            row['provider_request_id'] = response.headers.get('x-request-id', data.get('id'))
            return data

    def chat(self, system_prompt, user_prompt, temperature=0.1, step_name="llm_generation"):
        model = MODELS[self.provider]['chat']
        with step(step_name, provider=self.provider, model=model) as row:
            messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}]
            limit = int(os.getenv('MAX_OUTPUT_TOKENS', '4096'))
            if self.provider == 'openai':
                payload = {'model': model, 'messages': messages, 'max_completion_tokens': limit}
                # Reasoning models may accept only their default sampling settings.
                # Keep the requested sampling value for the original GPT-4 defaults.
                configured_temperature = os.getenv('OPENAI_TEMPERATURE', '').strip()
                if configured_temperature:
                    payload['temperature'] = float(configured_temperature)
                elif model.startswith(('gpt-4', 'gpt-3.5')):
                    payload['temperature'] = temperature
                row['temperature'] = payload.get('temperature', 'model default')
                data = self._post('/chat/completions', payload, row)
                choice = data['choices'][0]
                row['finish_reason'] = choice.get('finish_reason')
                text = choice['message']['content']
            else:
                data = self._post('/chat', {'model': model, 'messages': messages, 'temperature': temperature, 'max_tokens': limit}, row)
                row['finish_reason'] = data.get('finish_reason')
                text = ''.join(item.get('text', '') for item in data['message']['content'])
            row['output_limit'] = limit
            if row['finish_reason'] in ('length', 'MAX_TOKENS'):
                raise ProviderError('Model reached the output token limit; increase MAX_OUTPUT_TOKENS or reduce the request', 422)
            if not text or not text.strip():
                raise ProviderError('Provider returned an empty response')
            return text.strip()

    def embed(self, texts, query=False):
        model = MODELS[self.provider]['embedding']
        vectors = []
        for offset in range(0, len(texts), 64):
            batch = texts[offset:offset+64]
            with step('query_embedding' if query else 'document_embedding', provider=self.provider, model=model, inputs=len(batch)) as row:
                if self.provider == 'openai':
                    data = self._post('/embeddings', {'model': model, 'input': batch}, row)
                    vectors.extend(item['embedding'] for item in sorted(data['data'], key=lambda item: item['index']))
                else:
                    data = self._post('/embed', {'model': model, 'texts': batch, 'input_type': 'search_query' if query else 'search_document', 'embedding_types': ['float'], 'truncate': 'NONE'}, row)
                    vectors.extend(data['embeddings']['float'])
        return vectors
