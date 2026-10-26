#!/usr/bin/env python3
"""Prepare a local writing-review snapshot; never approves writing or calls an AI API."""
import argparse
import json
from pathlib import Path

from validate_review import CURRENT_REVIEW_SCHEMA, local_file, writing_review_hash, writing_review_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--out', required=True, help='Fresh directory relative to the review run')
    args = parser.parse_args()
    root = args.run_directory.resolve()
    try:
        manifest = json.loads(local_file(root, 'manifest.json').read_text())
        review = json.loads(local_file(root, 'review.json').read_text())
        if review.get('schema_version') != CURRENT_REVIEW_SCHEMA:
            raise ValueError('writing revisions require review schema_version 2; prepare a copy of the legacy review first')
        if review.get('status') == 'failed':
            raise ValueError('a failed review has no usable narrative for writing assessment')
        narrative = local_file(root, 'narrative.md').read_text()
        content = writing_review_input(manifest, review, narrative)
        snapshot = {'content_sha256': writing_review_hash(content), 'content': content}
        relative = Path(args.out)
        output = (root / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not output.is_relative_to(root):
            raise ValueError('writing-review output must stay inside the review run')
        output.mkdir(parents=True, exist_ok=False)
        (output / 'input.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'input': str(output / 'input.json'), 'content_sha256': snapshot['content_sha256'],
                          'approval_generated': False}))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
