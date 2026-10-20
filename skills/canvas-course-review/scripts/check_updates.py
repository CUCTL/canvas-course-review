#!/usr/bin/env python3
"""Compare the installed skill with GitHub without modifying the installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
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


def check(skill_root, source_url=SOURCE_URL, ref='HEAD'):
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
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        # Avoid returning command output that might include credentials or server details.
        result.update(status='check_unavailable', reason=type(error).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-url', default=SOURCE_URL)
    parser.add_argument('--ref', default='HEAD', help='Upstream ref; HEAD follows its default branch.')
    args = parser.parse_args()
    result = check(args.skill_root, args.source_url, args.ref)
    print(json.dumps(result, indent=2))
    return 1 if result['status'] == 'check_unavailable' else 0


if __name__ == '__main__':
    raise SystemExit(main())
