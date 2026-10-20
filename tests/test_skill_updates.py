"""Exercise update detection against local Git repositories; no network required."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/canvas-course-review/scripts/check_updates.py'
spec = importlib.util.spec_from_file_location('updates', SCRIPT)
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


class UpdateTests(unittest.TestCase):
    def git(self, *args, cwd=None):
        return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True).stdout

    def commit(self, repository):
        self.git('add', '.', cwd=repository)
        self.git('-c', 'user.name=Update fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-m', 'Fixture version', cwd=repository)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'upstream'
        self.git('init', str(self.source))
        upstream_skill = self.source / u.SKILL_PATH
        upstream_skill.mkdir(parents=True)
        (upstream_skill / 'SKILL.md').write_text('Initial skill\n')
        self.commit(self.source)
        self.checkout = self.root / 'installed'
        self.git('clone', str(self.source), str(self.checkout))
        self.skill = self.checkout / u.SKILL_PATH

    def snapshot(self):
        return (self.git('status', '--porcelain=v1', cwd=self.checkout),
                self.git('show-ref', cwd=self.checkout),
                {str(p.relative_to(self.skill)): p.read_bytes()
                 for p in self.skill.rglob('*') if p.is_file()})

    def check(self, source=None):
        before = self.snapshot()
        result = u.check(self.skill, str(source or self.source))
        self.assertEqual(before, self.snapshot(), 'Check changed installation, index, or refs')
        self.assertFalse(result['installation_modified'])
        return result

    def test_identical_and_unpublished_local_changes(self):
        self.assertEqual('up_to_date', self.check()['status'])
        (self.skill / 'SKILL.md').write_text('Unpublished local work\n')
        result = self.check()
        self.assertEqual('local_changes', result['status'])
        self.assertEqual(['SKILL.md'], result['differing_files'])
        self.assertTrue(result['local_changes'])
        self.assertFalse(result['upstream_changes'])

    def test_upstream_and_diverged_changes_preserve_local_work(self):
        (self.source / u.SKILL_PATH / 'SKILL.md').write_text('Upstream revision\n')
        self.commit(self.source)
        result = self.check()
        self.assertEqual('upstream_changes', result['status'])
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.source).decode().strip(),
                         result['upstream_commit'])
        (self.skill / 'local-notes.md').write_text('Keep this work\n')
        self.assertEqual('local_and_upstream_changes', self.check()['status'])

    def test_unavailable_source_preserves_installation(self):
        result = self.check(self.root / 'missing-repository')
        self.assertEqual('check_unavailable', result['status'])
        self.assertNotIn('upstream_commit', result)

    def test_standalone_copy_and_symlink_installation(self):
        standalone = self.root / 'standalone'
        standalone.mkdir()
        (standalone / 'SKILL.md').write_bytes((self.skill / 'SKILL.md').read_bytes())
        self.assertEqual('up_to_date', u.check(standalone, str(self.source))['status'])
        (standalone / 'SKILL.md').write_text('Copied installation with changes\n')
        self.assertEqual('different_no_local_baseline', u.check(standalone, str(self.source))['status'])
        link = self.root / 'skill-link'
        link.symlink_to(self.skill, target_is_directory=True)
        self.assertEqual('up_to_date', u.check(link, str(self.source))['status'])


if __name__ == '__main__':
    unittest.main()
