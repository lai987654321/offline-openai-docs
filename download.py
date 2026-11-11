"""Download official llms indexes and their Markdown/text exports (Python 3 stdlib)."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
HOSTS = {'developers.openai.com', 'learn.chatgpt.com', 'platform.openai.com'}
SEEDS = ['https://developers.openai.com/llms.txt', 'https://learn.chatgpt.com/llms.txt']

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def allowed(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and p.hostname in HOSTS and not p.username and p.port in (None, 443)

class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('Redirect outside official host allowlist: ' + newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def location(url):
    p = urllib.parse.urlsplit(url)
    slug = re.sub(r'[^a-zA-Z0-9._-]+', '_', p.path.strip('/'))[-60:]
    ext = '.md' if p.path.endswith('.md') else '.txt'
    digest = hashlib.sha256(url.encode()).hexdigest()[:12]
    folder = 'indexes' if p.path.endswith('/llms.txt') else 'documents'
    return pathlib.Path(folder) / p.hostname / (slug + '--' + digest + ext)

def fetch(item, refresh=False):
    url = item['url']
    record = dict(item, downloaded_at=now())
    rel = location(url)
    target = ROOT / rel
    record['path'] = rel.as_posix()
    if not allowed(url):
        return dict(record, status='failed', error='Disallowed URL')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'OpenAI-Docs-Offline-Archive/1.0', 'Accept': 'text/markdown, text/plain;q=0.9'})
            opener = urllib.request.build_opener(OfficialRedirect())
            with opener.open(req, timeout=60) as response:
                data = response.read()
                content_type = response.headers.get('Content-Type', '')
                final_url = response.geturl()
            text = data.decode('utf-8-sig')
            if not text.strip() or 'text/html' in content_type.lower() or re.match(r'\s*(<!doctype html|<html)', text, re.I):
                raise ValueError('Empty or HTML response instead of documentation')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return dict(record, status='ok', final_url=final_url, content_type=content_type,
                        bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        except Exception as exc:
            record['error'] = str(exc)
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (400, 401, 403, 404, 410):
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
    return dict(record, status='failed')

def discover():
    queue = list(SEEDS)
    seen = set()
    docs = {}
    records = []
    skipped = set()
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        rec = fetch({'url': url, 'title': 'Documentation index', 'kind': 'index'})
        records.append(rec)
        print('INDEX', rec['status'], url, flush=True)
        if rec['status'] != 'ok':
            continue
        body = (ROOT / rec['path']).read_text(encoding='utf-8-sig')
        for title, link in re.findall(r'\[([^\]\n]+)\]\(([^\s)]+)\)', body):
            link = urllib.parse.urljoin(rec.get('final_url', url), link)
            p = urllib.parse.urlsplit(link)
            link = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))
            if not allowed(link):
                skipped.add(link)
                continue
            if p.path.endswith('/llms.txt'):
                if link not in seen:
                    queue.append(link)
            elif p.path.endswith(('.md', '.txt')):
                if link not in docs:
                    docs[link] = {'url': link, 'title': title, 'kind': 'document', 'source_indexes': []}
                docs[link]['source_indexes'].append(url)
            else:
                skipped.add(link)
    plan = {'created_at': now(), 'seeds': SEEDS, 'indexes': records,
            'documents': sorted(docs.values(), key=lambda x: x['url']), 'non_document_links': sorted(skipped)}
    (ROOT / 'download-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print('DISCOVERY', len(records), 'indexes;', len(docs), 'unique documents;', len(skipped), 'non-document links', flush=True)
    return plan

def report(plan, results):
    entries = sorted(plan['indexes'] + results, key=lambda r: (r['kind'], r['url']))
    good = [r for r in entries if r['status'] == 'ok']
    failed = [r for r in entries if r['status'] != 'ok']
    manifest = {'generated_at': now(), 'seeds': SEEDS, 'records': entries}
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'failures.json').write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding='utf-8')
    index = ['# OpenAI offline documentation', '', 'Snapshot retrieval (UTC): ' + now(), '',
             'Original file bytes are preserved. Use manifest.json for source URLs, timestamps, redirects and SHA-256 hashes.', '',
             f'Successful files: {len(good)}; failed URLs: {len(failed)}.', '',
             'Only Markdown/text exports explicitly linked by the recursively discovered llms.txt indexes are included.',
             'Images, videos, linked repositories and arbitrary links inside documents are not downloaded.', '', '## Files', '']
    for r in sorted(good, key=lambda x: (x['kind'], x['url'])):
        title = r['title'].replace('[', '(').replace(']', ')')
        index.append(f"- [{title}]({r['path']}) — [source]({r['url']})")
    (ROOT / 'INDEX.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    summary = {'successful_indexes': sum(r['status'] == 'ok' for r in plan['indexes']),
               'successful_documents': sum(r['status'] == 'ok' for r in results),
               'failed': len(failed), 'total_bytes': sum(r.get('bytes', 0) for r in good)}
    (ROOT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps(summary), flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discover-only', action='store_true')
    parser.add_argument('--refresh', action='store_true', help='Re-fetch indexes and all documents')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    plan_path = ROOT / 'download-plan.json'
    plan = discover() if args.refresh or not plan_path.exists() else json.loads(plan_path.read_text(encoding='utf-8'))
    if args.discover_only:
        return
    journal = ROOT / 'download-log.jsonl'
    previous = {}
    if journal.exists() and not args.refresh:
        for line in journal.read_text(encoding='utf-8').splitlines():
            try:
                rec = json.loads(line)
                path = ROOT / rec['path']
                if rec['status'] == 'ok' and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == rec['sha256']:
                    previous[rec['url']] = rec
            except (ValueError, KeyError):
                pass
    results = [previous[r['url']] for r in plan['documents'] if r['url'] in previous]
    pending = [r for r in plan['documents'] if r['url'] not in previous]
    print('DOWNLOAD', len(pending), 'pending;', len(results), 'verified cached', flush=True)
    with journal.open('a', encoding='utf-8') as log, concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.workers, 12))) as pool:
        futures = {pool.submit(fetch, r): r for r in pending}
        for future in concurrent.futures.as_completed(futures):
            rec = future.result()
            results.append(rec)
            log.write(json.dumps(rec, ensure_ascii=False) + '\n')
            log.flush()
            if rec['status'] != 'ok':
                print('FAILED', rec['url'], rec.get('error', ''), flush=True)
            if len(results) % 50 == 0:
                print('PROGRESS', len(results), '/', len(plan['documents']), flush=True)
    report(plan, results)

if __name__ == '__main__':
    main()
