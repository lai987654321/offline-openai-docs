"""Maintain a versioned offline mirror. Python 3.10+, standard library only."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent

def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def safe_path(root, rel):
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path outside snapshot: ' + rel)
    return path

def verify(root, manifest):
    count = 0
    paths = set()
    for row in manifest['records']:
        if row['status'] != 'ok':
            continue
        path = safe_path(root, row['path'])
        if row['path'] in paths:
            raise ValueError('Duplicate source path: ' + row['path'])
        paths.add(row['path'])
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Content checksum mismatch: ' + row['path'])
        count += 1
    return count

def compare(old, new):
    before = {r['url']: r for r in old['records'] if r['status'] == 'ok'}
    after = {r['url']: r for r in new['records'] if r['status'] == 'ok'}
    failed = {r['url']: r for r in new['records'] if r['status'] != 'ok'}
    missing_indexes = [u for u, r in before.items() if r['kind'] == 'index' and u not in after]
    blocked = sorted(set(before) & set(failed) | set(missing_indexes))
    return {'from_snapshot': old.get('generated_at'), 'to_snapshot': new.get('generated_at'),
            'added': sorted(set(after) - set(before)),
            'changed': sorted(u for u in set(before) & set(after) if before[u]['sha256'] != after[u]['sha256']),
            'retired': sorted(set(before) - set(after) - set(failed)),
            'failed': sorted(failed), 'blocking_failures': blocked}

def entry(row):
    title = row['title'].replace('[', '(').replace(']', ')')
    return f"- [{title}]({row['path']}) — [source]({row['url']})"

def render(root, manifest, retired):
    records = manifest['records']
    date = manifest['generated_at']
    good = sorted((r for r in records if r['status'] == 'ok'), key=lambda r: (r['kind'], r['url']))
    failures = sorted((r for r in records if r['status'] != 'ok'), key=lambda r: r['url'])
    index = ['# OpenAI offline documentation', '', 'Snapshot (UTC): ' + date, '',
             'Original source bytes are preserved. Provenance and hashes: manifest.json.', '',
             f'Successful files: {len(good)}; unavailable URLs: {len(failures)}.', '', '## Files', '']
    index += [entry(r) for r in good]
    (root / 'INDEX.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    tokens = ['/codex-manual.md', '/config-file/', '/agent-configuration/', '/build-skills.md', '/auth.md',
              '/agent-approvals-security.md', '/mcp.md', '/developer-settings.md', '/developer-commands.md',
              '/enterprise/managed-configuration.md']
    start = ['# Codex 離線文件入口', '', 'Snapshot (UTC): ' + date, '',
             '完整清單：[INDEX.md](INDEX.md)。先閱讀設定參考、基本設定與安全權限；跨主題問題可參考 Codex manual。', '']
    start += [entry(r) for r in good if r['kind'] == 'document' and any(t in r['url'] for t in tokens)]
    (root / 'CODEX-START.md').write_text('\n'.join(start) + '\n', encoding='utf-8')
    missing = ['# 未成功下載的來源', '', 'Snapshot (UTC): ' + date, '']
    missing += [f"- {r['url']} — {r.get('error', 'Unavailable')}" for r in failures]
    (root / 'MISSING.md').write_text('\n'.join(missing) + '\n', encoding='utf-8')
    retired_text = ['# 不再列於目前索引的文件', '',
                    '保留最後成功下載的內容供查閱；不代表這些文件仍是現行官方指引。', '']
    retired_text += [entry(r) for r in retired]
    if not retired:
        retired_text.append('目前沒有。')
    (root / 'RETIRED.md').write_text('\n'.join(retired_text) + '\n', encoding='utf-8')

def update(root, workers):
    old = read_json(root / 'manifest.json', {'records': []})
    verify(root, old)
    cache = root / '.cache'
    cache.mkdir(exist_ok=True)
    # Stage all network results before publishing a validated snapshot.
    with tempfile.TemporaryDirectory(prefix='sync-', dir=cache) as temp:
        stage = pathlib.Path(temp)
        shutil.copy2(root / 'download.py', stage / 'download.py')
        result = subprocess.run([sys.executable, str(stage / 'download.py'), '--refresh', '--workers', str(workers)])
        if result.returncode:
            raise RuntimeError('Download process failed; current snapshot is unchanged')
        new = read_json(stage / 'manifest.json')
        verify(stage, new)
        changes = compare(old, new)
        # Both seed indexes are mandatory even when bootstrapping an empty mirror.
        good_urls = {r['url'] for r in new['records'] if r['status'] == 'ok'}
        for seed in ('https://developers.openai.com/llms.txt', 'https://learn.chatgpt.com/llms.txt'):
            if seed not in good_urls and seed not in changes['blocking_failures']:
                changes['blocking_failures'].append(seed)
        write_json(cache / 'last-attempt.json', changes)
        if changes['blocking_failures']:
            raise RuntimeError('Previously available source/index failed; snapshot unchanged. See .cache/last-attempt.json')
        retired_map = {r['url']: r for r in read_json(root / 'retired.json', [])}
        for r in old['records']:
            if r['url'] in changes['retired']:
                retired_map[r['url']] = dict(r, retired_at=new['generated_at'])
        for url in good_urls:
            retired_map.pop(url, None)
        retired = sorted(retired_map.values(), key=lambda r: r['url'])
        render(stage, new, retired)
        write_json(stage / 'changes.json', changes)
        write_json(stage / 'retired.json', retired)
        # No old document is deleted. Retired sources remain traceable and readable.
        for file in sorted(stage.rglob('*')):
            if not file.is_file() or file.name in ('download.py', 'download-log.jsonl'):
                continue
            rel = file.relative_to(stage)
            dest = safe_path(root, str(rel))
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.read_bytes() == file.read_bytes():
                continue
            temporary = dest.with_name(dest.name + '.sync-tmp')
            shutil.copyfile(file, temporary)
            temporary.replace(dest)
        print('Verified source files:', verify(root, new))
        print(json.dumps({k: len(changes[k]) for k in ('added', 'changed', 'retired', 'failed')}, indent=2))
        print('Review git diff, then commit the update when ready.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['update', 'verify', 'render'])
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    if args.command == 'update':
        update(ROOT, max(1, min(args.workers, 12)))
    else:
        manifest = read_json(ROOT / 'manifest.json')
        count = verify(ROOT, manifest)
        retired = read_json(ROOT / 'retired.json', [])
        count_retired = verify(ROOT, {'records': retired})
        if args.command == 'render':
            render(ROOT, manifest, retired)
        print(f'Verified {count} current source files and {count_retired} retired files.')

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
