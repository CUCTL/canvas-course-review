"""Exercise update detection against local Git repositories; no network required."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

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
        cache = patch.dict('os.environ', {'XDG_CACHE_HOME': str(self.root / 'cache')})
        cache.start()
        self.addCleanup(cache.stop)
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

    def publish_update(self):
        source_skill = self.source / u.SKILL_PATH
        (source_skill / 'SKILL.md').write_text('Updated skill\n')
        (source_skill / 'scripts').mkdir(exist_ok=True)
        executable = source_skill / 'scripts/tool.py'
        executable.write_text('print("updated")\n')
        executable.chmod(0o755)
        self.commit(self.source)

    def test_upgrade_copy_retains_backup_and_removes_retired_files(self):
        import shutil
        import tarfile
        retired = self.source / u.SKILL_PATH / 'retired.md'
        retired.write_text('Old reference\n')
        self.commit(self.source)
        standalone = self.root / 'copy'
        shutil.copytree(self.source / u.SKILL_PATH, standalone)
        retired.unlink()
        self.publish_update()
        result = u.check(standalone, str(self.source), upgrade=True)
        self.assertEqual('upgraded', result['status'])
        self.assertTrue(result['installation_modified'])
        self.assertFalse((standalone / 'retired.md').exists())
        self.assertTrue((standalone / 'scripts/tool.py').stat().st_mode & 0o111)
        with tarfile.open(result['backup_path']) as archive:
            self.assertEqual(b'Old reference\n', archive.extractfile('copy/retired.md').read())
        self.assertEqual('up_to_date', u.check(standalone, str(self.source), upgrade=True)['status'])

    def test_upgrade_symlink_keeps_git_state_and_unrelated_work(self):
        self.publish_update()
        before_head = self.git('rev-parse', 'HEAD', cwd=self.checkout)
        before_index = self.git('ls-files', '--stage', cwd=self.checkout)
        notes = self.checkout / 'unrelated.txt'
        notes.write_text('Keep my work\n')
        link = self.root / 'linked'
        link.symlink_to(self.skill, target_is_directory=True)
        result = u.check(link, str(self.source), upgrade=True)
        self.assertEqual('upgraded', result['status'])
        self.assertTrue(link.is_symlink())
        self.assertEqual(before_head, self.git('rev-parse', 'HEAD', cwd=self.checkout))
        self.assertEqual(before_index, self.git('ls-files', '--stage', cwd=self.checkout))
        self.assertEqual('Keep my work\n', notes.read_text())

    def test_upgrade_preserves_local_edits_and_unpublished_commits(self):
        self.publish_update()
        (self.skill / 'SKILL.md').write_text('My local edition\n')
        before = self.snapshot()
        self.assertEqual('upgrade_skipped', u.check(self.skill, str(self.source), upgrade=True)['status'])
        self.assertEqual(before, self.snapshot())
        self.commit(self.checkout)
        before = self.snapshot()
        self.assertEqual('upgrade_skipped', u.check(self.skill, str(self.source), upgrade=True)['status'])
        self.assertEqual(before, self.snapshot())

    def test_failed_swap_restores_installation(self):
        self.publish_update()
        before = self.snapshot()
        real_rename = Path.rename

        def fail_prepared(path, target):
            if path.name == 'prepared':
                raise OSError('Simulated failed swap')
            return real_rename(path, target)

        with patch.object(Path, 'rename', fail_prepared):
            result = u.check(self.skill, str(self.source), upgrade=True)
        self.assertEqual('upgrade_failed', result['status'])
        self.assertFalse(result['installation_modified'])
        self.assertEqual(before, self.snapshot())

    def test_upstream_symlink_is_rejected_without_changes(self):
        (self.source / u.SKILL_PATH / 'outside').symlink_to('/tmp')
        self.commit(self.source)
        before = self.snapshot()
        self.assertEqual('upgrade_failed', u.check(self.skill, str(self.source), upgrade=True)['status'])
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
