#!/usr/bin/env python3
"""Compare the installed skill with GitHub; optionally upgrade a published version."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

SOURCE_URL = 'https://github.com/yehaisong/canvas-course-review.git'
SKILL_PATH = 'skills/canvas-course-review'


def git(*args, cwd=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    return subprocess.run(['git', *args], cwd=cwd, env=env, check=True,
                          capture_output=True, timeout=60).stdout


def tree(repository, revision, prefix):
    output = git('ls-tree', '-rz', revision, '--', prefix, cwd=repository)
    records = {}
    for entry in output.split(b'\0'):
        if not entry:
            continue
        metadata, path = entry.split(b'\t', 1)
        mode, kind, digest = metadata.decode().split()
        if kind == 'blob':
            records[path.decode()[len(prefix) + 1:]] = (mode, digest)
    return records


def installed_tree(root):
    records = {}
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
            continue
        if path.is_symlink():
            content = os.readlink(path).encode()
            mode = '120000'
        elif path.is_file() and path.suffix != '.pyc':
            content = path.read_bytes()
            mode = '100755' if path.stat().st_mode & 0o111 else '100644'
        else:
            continue
        digest = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        records[relative.as_posix()] = (mode, digest)
    return records


def upgrade_installation(root, repository, commit, current, remote):
    """Stage verified blobs, retain a backup archive, and roll back failed swaps."""
    for name, (mode, _) in remote.items():
        path = Path(name)
        if (path.is_absolute() or '..' in path.parts or
                any(part.startswith('.') for part in path.parts) or
                mode not in ('100644', '100755')):
            raise ValueError('Unsupported upstream path or file mode.')
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('Installation contains symlinks; reconcile manually.')
    cache = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache')))
    backups = cache / 'canvas-course-review' / 'skill-backups'
    backups.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(tempfile.mkdtemp(prefix='upgrade-', dir=backups))
    backup = shutil.make_archive(str(backup_dir / 'skill'), 'gztar',
                                 root_dir=root.parent, base_dir=root.name)
    with tempfile.TemporaryDirectory(prefix='.canvas-review-stage-', dir=root.parent) as staging:
        prepared = Path(staging) / 'prepared'
        previous = Path(staging) / 'previous'
        shutil.copytree(root, prepared)
        for name in current:
            (prepared / name).unlink()
        # Removed files can leave empty directories that conflict with new files.
        for directory in sorted(prepared.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        for name, (mode, _) in remote.items():
            destination = prepared / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(git('show', f'{commit}:{SKILL_PATH}/{name}', cwd=repository))
            destination.chmod(0o755 if mode == '100755' else 0o644)
        if installed_tree(prepared) != remote or installed_tree(root) != current:
            raise ValueError('Staged verification failed or installation changed during update.')
        root.rename(previous)
        try:
            prepared.rename(root)
            if installed_tree(root) != remote:
                raise ValueError('Installed verification failed.')
        except BaseException:
            if root.exists():
                shutil.rmtree(root)
            previous.rename(root)
            raise
    return backup


def upgrade_published(root, source_url, ref, result):
    """Only replace an exact skill tree found in the selected upstream history."""
    with tempfile.TemporaryDirectory(prefix='canvas-review-upgrade-') as temporary:
        git('init', '--bare', temporary)
        git('fetch', '--no-tags', source_url, ref, cwd=temporary)
        commit = git('rev-parse', 'FETCH_HEAD', cwd=temporary).decode().strip()
        if commit != result['upstream_commit']:
            raise ValueError('Upstream changed during check; retry next review.')
        current = installed_tree(root)
        revisions = git('log', '--format=%H', commit, '--', SKILL_PATH,
                        cwd=temporary).decode().splitlines()
        baseline = next((revision for revision in revisions
                         if tree(temporary, revision, SKILL_PATH) == current), None)
        if baseline is None:
            result.update(status='upgrade_skipped',
                          reason='Installed files do not exactly match a published ancestor; preserve local work.')
            return
        backup = upgrade_installation(root, temporary, commit, current,
                                      tree(temporary, commit, SKILL_PATH))
        result.update(status='upgraded', installation_modified=True,
                      installed_commit=commit, previous_published_commit=baseline,
                      backup_path=backup)


def check(skill_root, source_url=SOURCE_URL, ref='HEAD', upgrade=False):
    skill_root = Path(skill_root).resolve()
    result = {'source_url': source_url, 'ref': ref, 'installed_path': str(skill_root),
              'installation_modified': False}
    try:
        with tempfile.TemporaryDirectory(prefix='canvas-review-update-') as temporary:
            git('init', '--bare', temporary)
            git('fetch', '--depth=1', '--no-tags', source_url, ref, cwd=temporary)
            commit = git('rev-parse', 'FETCH_HEAD', cwd=temporary).decode().strip()
            remote = tree(temporary, commit, SKILL_PATH)
        if 'SKILL.md' not in remote:
            raise ValueError('Upstream does not contain the expected skill folder.')
        current = installed_tree(skill_root)
        changed = sorted(key for key in current.keys() | remote.keys() if current.get(key) != remote.get(key))
        baseline = None
        try:
            repository = Path(git('rev-parse', '--show-toplevel', cwd=skill_root).decode().strip())
            prefix = skill_root.relative_to(repository).as_posix()
            baseline = tree(repository, 'HEAD', prefix)
        except (subprocess.SubprocessError, ValueError):
            pass
        if not changed:
            status = 'up_to_date'
        elif baseline == remote:
            status = 'local_changes'
        elif baseline == current:
            status = 'upstream_changes'
        elif baseline is not None:
            status = 'local_and_upstream_changes'
        else:
            status = 'different_no_local_baseline'
        result.update(status=status, upstream_commit=commit, differing_files=changed,
                      local_changes=baseline is not None and current != baseline,
                      upstream_changes=baseline is not None and remote != baseline)
        if upgrade and changed:
            try:
                upgrade_published(skill_root, source_url, ref, result)
            except (OSError, subprocess.SubprocessError, ValueError) as error:
                result.update(status='upgrade_failed', reason=type(error).__name__)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        # Avoid returning command output that might include credentials or server details.
        result.update(status='check_unavailable', reason=type(error).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-url', default=SOURCE_URL)
    parser.add_argument('--ref', default='HEAD', help='Upstream ref; HEAD follows its default branch.')
    parser.add_argument('--upgrade', action='store_true',
                        help='Upgrade exact published versions, retaining a rollback archive.')
    args = parser.parse_args()
    result = check(args.skill_root, args.source_url, args.ref, upgrade=args.upgrade)
    print(json.dumps(result, indent=2))
    return 1 if result['status'] in ('check_unavailable', 'upgrade_failed') else 0


if __name__ == '__main__':
    raise SystemExit(main())
