import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from codepilot.agent import apply_edits, run_agent
from codepilot.repository_analyzer import repository_map


class MultiFileTests(unittest.TestCase):
    def test_create_modify_delete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'old.py').write_text('OLD = 1\n')
            (root / 'service.py').write_text('from old import OLD\n')
            edits = [
                {'path': 'old.py', 'operation': 'delete'},
                {'path': 'new.py', 'operation': 'create', 'content': 'VALUE = 2\n'},
                {'path': 'service.py', 'operation': 'modify', 'content': 'from new import VALUE\n'},
            ]
            self.assertEqual(len(apply_edits(root, edits, {'old.py', 'service.py'})), 3)
            self.assertFalse((root / 'old.py').exists())
            self.assertEqual((root / 'new.py').read_text(), 'VALUE = 2\n')

    def test_atomic_preflight_across_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'a.py').write_text('x = 1\n')
            with self.assertRaises(SyntaxError):
                apply_edits(root, [
                    {'path': 'a.py', 'content': 'x = 2\n'},
                    {'path': 'b.py', 'operation': 'create', 'content': 'def broken(\n'},
                ], {'a.py'})
            self.assertEqual((root / 'a.py').read_text(), 'x = 1\n')
            self.assertFalse((root / 'b.py').exists())

    def test_reject_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'safe.py').write_text('x=1\n')
            (root / 'link').symlink_to(root, target_is_directory=True)
            for path in ['../outside.py', '/tmp/outside.py', 'link/new.py']:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    apply_edits(root, [{'path': path, 'operation': 'create', 'content': 'x=1\n'}], {'safe.py'})

    def test_repository_map(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'mod.py').write_text('import json\ndef convert(x): return x\n')
            result = repository_map(d)
            self.assertIn('mod.py', result)
            self.assertIn('convert', result)
            self.assertIn('json', result)

    def test_end_to_end_three_file_feature(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'models.py').write_text('def user_role(): return "viewer"\n')
            (root / 'service.py').write_text('from models import user_role\ndef can_edit(): return False\n')
            (root / 'tests').mkdir()
            (root / 'tests' / 'test_feature.py').write_text(
                'import unittest\nfrom service import can_edit\nfrom api import authorize\n'
                'class Feature(unittest.TestCase):\n'
                '    def test_admin(self): self.assertTrue(authorize("admin"))\n'
                '    def test_viewer(self): self.assertFalse(authorize("viewer"))\n'
                '    def test_service(self): self.assertTrue(can_edit())\n')
            edits = [
                {'path': 'models.py', 'content': 'def user_role(): return "admin"\n'},
                {'path': 'service.py', 'content': 'from models import user_role\ndef can_edit(): return user_role() == "admin"\n'},
                {'path': 'api.py', 'operation': 'create', 'content': 'def authorize(role): return role == "admin"\n'},
            ]
            with patch('codepilot.agent.ask_model', return_value=json.dumps({'edits': edits})):
                result = run_agent(root, 'implement authorization across modules', attempts=1)
            self.assertTrue(result['success'], result['history'])
            self.assertEqual(set(result['history'][0]['changed_files']), {'models.py', 'service.py', 'api.py'})
            self.assertFalse((root / 'api.py').exists())


if __name__ == '__main__':
    unittest.main()
