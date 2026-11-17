"""Offline dashboard contract tests. All agent/model calls are mocked."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi import HTTPException
    from backend import app as backend
    HAS_DASHBOARD = True
except ImportError:
    HAS_DASHBOARD = False
    HTTPException = None
    backend = None


@unittest.skipUnless(HAS_DASHBOARD, "Dashboard dependencies (fastapi/uvicorn) not installed")
class OfflineDashboardIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'sample'
        self.repo.mkdir()
        (self.repo / 'calc.py').write_text('def double(x):\n    return x\n', encoding='utf-8')
        self.old_root = backend.ROOT
        self.old_runs = dict(backend.RUNS)
        backend.ROOT = self.root
        backend.RUNS.clear()

    def tearDown(self):
        backend.ROOT = self.old_root
        backend.RUNS.clear()
        backend.RUNS.update(self.old_runs)
        self.temp.cleanup()

    def test_repository_listing_and_file_read(self):
        listing = backend.repository(backend.RepositoryRequest(repository='sample'))
        self.assertEqual(listing['repository'], 'sample')
        self.assertTrue(any(item['path'] == 'calc.py' for item in listing['files']))
        file = backend.file_content(repository='sample', path='calc.py')
        self.assertIn('return x', file['content'])

    def test_path_traversal_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            backend.safe_repo('..')
        self.assertEqual(ctx.exception.status_code, 400)
        with self.assertRaises(HTTPException) as ctx:
            backend.file_content(repository='sample', path='../calc.py')
        self.assertEqual(ctx.exception.status_code, 400)

    def test_mocked_run_lifecycle_and_artifact_persistence(self):
        request = backend.RunRequest(repository='sample', task='Fix double to return twice its input', attempts=2)
        fake_result = {
            'success': True,
            'files': {'calc.py': 'def double(x):\n    return x * 2\n'},
            'history': [{'attempt': 1, 'passed': False}, {'attempt': 2, 'passed': True}],
        }
        with patch.object(backend.threading, 'Thread') as thread:
            created = backend.create_run(request)
        self.assertEqual(created['status'], 'running')
        thread.return_value.start.assert_called_once()
        run_id = created['id']
        self.assertEqual(backend.get_run(run_id)['status'], 'running')
        with patch.object(backend, 'run_agent', return_value=fake_result) as agent:
            backend.execute(run_id, request)
        agent.assert_called_once()
        record = backend.get_run(run_id)
        self.assertEqual(record['status'], 'completed')
        self.assertTrue(record['result']['success'])
        self.assertEqual(len(record['result']['history']), 2)
        self.assertEqual(backend.list_runs()['runs'][0]['success'], True)
        generated = self.root / '.codepilot-runs' / run_id / 'generated' / 'calc.py'
        self.assertEqual(generated.read_text(), fake_result['files']['calc.py'])
        self.assertEqual((self.repo / 'calc.py').read_text(), 'def double(x):\n    return x\n')

    def test_provider_exception_surfaces_as_run_error(self):
        request = backend.RunRequest(repository='sample', task='Fix double to return twice its input')
        with patch.object(backend.threading, 'Thread'):
            run_id = backend.create_run(request)['id']
        with patch.object(backend, 'run_agent', side_effect=RuntimeError('offline simulated provider failure')):
            backend.execute(run_id, request)
        record = backend.get_run(run_id)
        self.assertEqual(record['status'], 'error')
        self.assertIn('offline simulated provider failure', record['error'])


if __name__ == '__main__':
    unittest.main()
