import copy
import hashlib
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import sync

def row(url, data=b'original', kind='document'):
    return {'url': url, 'status': 'ok', 'kind': kind, 'title': url,
            'path': 'documents/' + hashlib.sha256(url.encode()).hexdigest()[:12] + '.md',
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

class SyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (sync.ROOT / '.cache').mkdir(exist_ok=True)

    def test_added_changed_retired(self):
        old = {'records': [row('a'), row('b')]}
        new = {'records': [row('a', b'changed'), row('c')]}
        changes = sync.compare(old, new)
        self.assertEqual(changes['added'], ['c'])
        self.assertEqual(changes['changed'], ['a'])
        self.assertEqual(changes['retired'], ['b'])
        self.assertEqual(changes['blocking_failures'], [])

    def test_existing_failures_block_but_new_failures_do_not(self):
        old = {'records': [row('a')]}
        new = {'records': [dict(row('a'), status='failed'), dict(row('new'), status='failed')]}
        self.assertEqual(sync.compare(old, new)['blocking_failures'], ['a'])
        self.assertEqual(sync.compare(old, new)['retired'], [])

    def test_disappearing_index_blocks_retirement(self):
        self.assertEqual(sync.compare({'records': [row('index', kind='index')]}, {'records': []})['blocking_failures'], ['index'])

    def test_corruption_and_path_escape(self):
        with tempfile.TemporaryDirectory(dir=sync.ROOT / '.cache') as temp:
            root = pathlib.Path(temp)
            record = row('a')
            file = root / record['path']
            file.parent.mkdir()
            file.write_bytes(b'original')
            self.assertEqual(sync.verify(root, {'records': [record]}), 1)
            file.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                sync.verify(root, {'records': [record]})
            with self.assertRaises(ValueError):
                sync.safe_path(root, '../escape.md')

    def test_failed_refresh_preserves_live_snapshot(self):
        with tempfile.TemporaryDirectory(dir=sync.ROOT / '.cache') as temp:
            root = pathlib.Path(temp)
            record = row('https://example.invalid/previous.md')
            file = root / record['path']
            file.parent.mkdir()
            file.write_bytes(b'original')
            (root / 'download.py').write_text('# fixture', encoding='utf-8')
            old = {'records': [record]}
            sync.write_json(root / 'manifest.json', old)
            original_manifest = (root / 'manifest.json').read_bytes()
            def fake_download(command):
                stage = pathlib.Path(command[1]).parent
                new = copy.deepcopy(old)
                new['records'][0]['status'] = 'failed'
                sync.write_json(stage / 'manifest.json', new)
                return mock.Mock(returncode=0)
            with mock.patch.object(sync.subprocess, 'run', side_effect=fake_download):
                with self.assertRaises(RuntimeError):
                    sync.update(root, 1)
            self.assertEqual(file.read_bytes(), b'original')
            self.assertEqual((root / 'manifest.json').read_bytes(), original_manifest)
            self.assertTrue((root / '.cache' / 'last-attempt.json').exists())

if __name__ == '__main__':
    unittest.main()
