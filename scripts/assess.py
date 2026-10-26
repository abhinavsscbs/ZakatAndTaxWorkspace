#!/usr/bin/env python3
"""Run identical cases against both real APIs. Outputs raw evidence and blind review sheets."""
import argparse
import csv
import hashlib
import io
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app import app
from providers import MODELS


def percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, int((len(ordered)-1)*p))] if ordered else None


def run_case(client, case, provider, base):
    headers = {'X-AI-Provider': provider}
    task = case['task']
    if task == 'chat':
        return client.post('/api/chat', json={k:v for k,v in case.items() if k in ('query','selected_doc_ids','selected_areas','translate','history')}, headers=headers)
    if task in ('upload', 'tax'):
        path = base / case['file']
        data = {'file': (io.BytesIO(path.read_bytes()), path.name)}
        if task == 'tax':
            data.update(analysis_mode=case.get('analysis_mode', 'general'), selected_doc_ids=json.dumps(case.get('selected_doc_ids', [])))
        if task == 'upload':
            data.update(doc_id=case['doc_id'], tax_area=case.get('tax_area', 'Unclassified'))
        return client.post('/api/docs' if task == 'upload' else '/api/tax/analyze', data=data, headers=headers)
    if task == 'comparison':
        paths = [base / case[key] for key in ('older','newer')]
        return client.post('/api/comparisons/run', data={'files': [(io.BytesIO(path.read_bytes()),path.name) for path in paths], 'pairs':json.dumps([{'older':paths[0].name,'newer':paths[1].name}])}, headers=headers)
    raise ValueError(f'Unknown task: {task}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=ROOT/'scripts/cases.example.json')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, default=ROOT/'assessment-results')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.repeats < 1: parser.error('--repeats must be positive')
    if args.cases.resolve() == (ROOT / 'scripts/cases.example.json').resolve():
        import importlib.util
        spec = importlib.util.spec_from_file_location('example_fixtures', ROOT / 'scripts/example_fixtures.py')
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        fixtures.prepare()
    cases = json.loads(args.cases.read_text())
    out = args.output / time.strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True, exist_ok=True)
    # Isolate benchmark knowledge and dictionary data from the app's working data.
    import os
    os.environ['DATA_DIR'] = str(out/'knowledge')
    from config import Config
    Config.DICTIONARY_FILE = out/'dictionary.json'
    rng = random.Random(args.seed)
    results, review, mapping = [], [], []
    client = app.test_client()
    for repeat in range(args.repeats):
        order = ['openai', 'cohere']; rng.shuffle(order)
        # Preserve case order so uploads run before questions that depend on them.
        for provider in order:
            for case in cases:
                started = time.perf_counter()
                try:
                    response = run_case(client, case, provider, args.cases.parent)
                    data = response.get_json() or {}
                    failed_pairs = any(not item.get('success') for item in data.get('results',[]))
                    success = response.status_code < 400 and not failed_pairs
                    record = {'case':case['id'], 'task':case['task'], 'repeat':repeat, 'provider':provider, 'http_status':response.status_code, 'success':success, 'wall_ms':round((time.perf_counter()-started)*1000,3), 'response':data}
                except Exception as exc:
                    record = {'case':case['id'], 'task':case['task'], 'repeat':repeat, 'provider':provider, 'success':False, 'wall_ms':round((time.perf_counter()-started)*1000,3), 'error':str(exc), 'response':{}}
                results.append(record)
                text = str(record['response'].get('answer') or '\n\n'.join(item.get('tax_analysis', '') for item in record['response'].get('analysis_results', [])) or json.dumps(record['response'].get('results',{}),ensure_ascii=False))
                terms = case.get('expected_terms', [])
                record['quality_heuristics'] = {'expected_term_coverage':sum(term.lower() in text.lower() for term in terms)/len(terms) if terms else None, 'citation_present': '[' in text and ':' in text if case['task']=='chat' else None, 'note':'Diagnostic proxies, not factual or legal correctness scores.'}
                blind_id = hashlib.sha256(f"{args.seed}:{provider}:{repeat}:{case['id']}".encode()).hexdigest()[:12]
                if case['task'] != 'upload':
                    review.append({'blind_id':blind_id,'case':case['id'],'response':text,'correctness_1_5':'','grounding_1_5':'','completeness_1_5':'','clarity_1_5':'','notes':''})
                    mapping.append({'blind_id':blind_id,'provider':provider,'repeat':repeat,'case':case['id']})
                print(f"{provider:7} {case['id']:24} repeat={repeat} success={record['success']} {record['wall_ms']:.0f}ms", flush=True)
    groups = defaultdict(list)
    for result in results: groups[(result['provider'],result['case'])].append(result)
    summary, steps, usage = [], [], []
    for record in results:
        for index, step in enumerate(record["response"].get("telemetry", {}).get("steps", [])):
            if "usage" in step or "http_status" in step:
                usage.append({"provider":record["provider"], "case":record["case"], "repeat":record["repeat"], "step_index":index, "step":step["name"], "model":step.get("model"), "duration_ms":step["duration_ms"], "http_status":step.get("http_status"), "attempts":step.get("attempts"), "finish_reason":step.get("finish_reason"), "configured_output_limit":step.get("output_limit"), "usage_json":json.dumps(step.get("usage",{})), "rate_limits_json":json.dumps(step.get("rate_limits",{}))})
    for (provider,case), rows in groups.items():
        good = [r for r in rows if r['success']]
        times = [r['wall_ms'] for r in good]
        summary.append({'provider':provider,'case':case,'runs':len(rows),'successes':len(good),'errors':len(rows)-len(good),'mean_ms':statistics.mean(times) if times else None,'p50_ms':statistics.median(times) if times else None,'p95_ms':percentile(times,.95),'note':'Includes retries and lazy index building. Inspect per-step records; small-sample p95 is not an SLA.'})
        names = defaultdict(list)
        for row in good:
            for step in row['response'].get('telemetry',{}).get('steps',[]):
                names[step['name']].append(step['duration_ms'])
        for name, durations in names.items():
            steps.append({'provider':provider,'case':case,'step':name,'calls':len(durations),'mean_ms':statistics.mean(durations),'p50_ms':statistics.median(durations),'p95_ms':percentile(durations,.95)})
    (out/'raw.json').write_text(json.dumps({'models':MODELS,'seed':args.seed,'cases_sha256':hashlib.sha256(args.cases.read_bytes()).hexdigest(),'results':results},ensure_ascii=False,indent=2))
    rng.shuffle(review)
    for name, rows in [('summary',summary),('steps',steps),('usage',usage),('blind_review',review),('review_key',mapping)]:
        if rows:
            with (out/f'{name}.csv').open('w', newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(f'Reports: {out}')
    return 0 if all(r['success'] for r in results) else 1

if __name__ == '__main__':
    raise SystemExit(main())
