#!/usr/bin/env python3
"""Validate CUOCDR run artifacts and optionally render the Markdown report."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

IDS = set(range(1, 44)) - {25}
RATINGS = {'Present', 'Minor Revision', 'Moderate Revision', 'Major Revision', 'N/A'}
REVISIONS = {'Minor Revision', 'Moderate Revision', 'Major Revision'}
PRIORITIES = {'Moderate Revision', 'Major Revision'}
STATES = {'verified', 'not_evidenced', 'not_verified', 'not_applicable'}
OUTCOMES = {'completed', 'partial', 'failed', 'not_started'}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def local_file(root, value):
    if not nonempty(value):
        raise ValueError('missing artifact path')
    path = Path(value)
    resolved = (root / path).resolve()
    if path.is_absolute() or '..' in path.parts or not resolved.is_relative_to(root):
        raise ValueError(f'artifact escapes run directory: {value}')
    if not resolved.is_file():
        raise ValueError(f'artifact missing: {value}')
    return resolved


def rubric():
    groups, current = [], None
    for line in (Path(__file__).resolve().parents[1] / 'references/cuocdr-rubric.md').read_text().splitlines():
        cells = [c.strip() for c in line.split('|')]
        if len(cells) > 2 and cells[1].startswith('**'):
            current = (cells[1].strip('*'), [])
            groups.append(current)
        elif len(cells) > 2 and cells[1].rstrip('.').isdigit():
            current[1].append((int(cells[1].rstrip('.')), cells[2]))
    return groups


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def render(manifest, review, narrative):
    course = manifest['course']
    lines = [f"# {course['name']} — CUOCDR review", '', f"Status: **{review['status']}**",
             f"Course ID: {course['id']}", f"Snapshot: {manifest['snapshot_at']}",
             f"Mode: {manifest['mode']}", f"Rubric: {manifest['rubric_version']}"]
    pending = sum(c['rating'] is None and not c['deferred'] for c in review['criteria'])
    deferred = sum(c['deferred'] for c in review['criteria'])
    if review['status'] != 'completed' or pending or deferred or manifest['limitations'] or review['limitations']:
        lines += ['', f"Review note: Pending criterion checks: {pending}; deferred items: {deferred}. "
                  "Read Scope and limitations below for evidence gaps and review boundaries."]
    if narrative:
        lines += ['', '## Faculty-facing narrative draft', '', narrative.strip()]
    records = {c['id']: c for c in review['criteria']}
    for title, items in rubric():
        lines += ['', f'## {title}', '', '| ID | Criterion | Rating | Evidence | Action / verification |',
                  '| --- | --- | --- | --- | --- |']
        for cid, wording in items:
            c = records.get(cid)
            if c is None:
                lines.append(f'| {cid} | {wording} | Unreviewed | Review failed before evaluation. | Resume review. |')
                continue
            label = c['rating'] or ('Deferred' if c['deferred'] else 'Pending verification')
            evidence = f"{c['evidence']} (status: {c['evidence_status']}; sources: {', '.join(c['source_ids'])})"
            action = c['action_plan'] or c['verification_step'] or '—'
            if c['uncertainty']:
                action += f" Uncertainty: {c['uncertainty']}"
            lines.append('| ' + ' | '.join(cell(v) for v in (cid, wording, label, evidence, action)) + ' |')
    lines += ['', '## Priority actions', '']
    lines += [f"- CU {c['id']} ({c['rating']}): {c['action_plan']}" for c in review['criteria'] if c['rating'] in PRIORITIES] or ['No Moderate/Major findings recorded; consult status and limitations.']
    lines += ['', '## Mechanical grammar and spelling', '']
    lines += [f"- Source {g['source_id']}: {g['issue']} Suggested fix: {g['suggested_fix']}" for g in review['grammar']] or [
        'No confirmed mechanical issues found.' if review['stages']['grammar'] == 'completed' else 'Mechanical review incomplete; see limitations.']
    lines += ['', '## Scope and limitations', '', f"Scope: {manifest['scope']}", '']
    lines += [f'- {item}' for item in manifest['limitations'] + review['limitations']] or ['No recorded limitations.']
    lines += ['', '## Stage outcomes', '']
    lines += [f"- {key}: {value}" for key, value in review['stages'].items()]
    # Preserve full provenance internally; omit excluded files from every report listing.
    excluded_files = {f['source_id'] for f in manifest.get('file_reviews', []) if f['check_status'] == 'excluded'}
    excluded_files.update(i['id'] for i in manifest['inventory'] if i['status'] == 'excluded' and i['id'].startswith('file-'))
    def excluded_source(source_id):
        return any(source_id == key or source_id.startswith(key + '-') for key in excluded_files)
    lines += ['', '## Source register', '']
    lines += [f"- {s['id']}: {s['location']} — {s['description']}" for s in manifest['sources'] if not excluded_source(s['id'])]
    visible_files = [f for f in manifest.get('file_reviews', []) if not excluded_source(f['source_id'])]
    if visible_files:
        lines += ['', '## File review checklist', '',
                  '| File / source | Format | Role | Content check | Status | Reason |',
                  '| --- | --- | --- | --- | --- | --- |']
        for f in visible_files:
            lines.append('| ' + ' | '.join(cell(v) for v in (f['name'] + ' / ' + f['source_id'], f['format'], f['role'],
                         'Required' if f['content_check_required'] else f['check_type'], f['check_status'], f['reason'])) + ' |')
    lines += ['', '## Coverage inventory', '']
    lines += [f"- {i['id']}: {i['location']} — {i['status']}; view: {i['view']}; publication: {i['publication_state']}. {i.get('reason', '')}" for i in manifest['inventory']
              if not excluded_source(i['id']) and not any(excluded_source(sid) for sid in i.get('source_ids', []))]
    return '\n'.join(lines) + '\n'


def validate(root, m, r):
    errors = []
    def check(condition, message):
        if not condition:
            errors.append(message)
    for obj, label in ((m, 'manifest'), (r, 'review')):
        check(obj.get('schema_version') == 1, f'{label}: schema_version must be 1')
        check(isinstance(obj.get('limitations'), list) and all(nonempty(x) for x in obj.get('limitations', [])), f'{label}: invalid limitations')
    check(all(nonempty(m.get('course', {}).get(k)) for k in ('id', 'name')), 'course id/name required')
    check(m.get('mode') in {'pre_launch', 'published_view', 'supplied_export'}, 'invalid mode')
    check(nonempty(m.get('scope')), 'scope required')
    check(m.get('rubric_version') == 'CUOCDR v0.9', 'invalid rubric version')
    try:
        check(datetime.fromisoformat(m['snapshot_at'].replace('Z', '+00:00')).utcoffset() is not None, 'snapshot timezone required')
    except (KeyError, ValueError, TypeError, AttributeError):
        errors.append('invalid snapshot_at')
    source_ids = set()
    for s in m.get('sources', []):
        check(all(nonempty(s.get(k)) for k in ('id', 'location', 'description')), 'invalid source record')
        check(s.get('id') not in source_ids, 'duplicate source id')
        source_ids.add(s.get('id'))
        if 'artifact' in s:
            try:
                p = local_file(root, s['artifact'])
                if 'sha256' in s:
                    check(hashlib.sha256(p.read_bytes()).hexdigest() == s['sha256'], f"source hash mismatch: {s['id']}")
            except ValueError as e:
                errors.append(str(e))
        elif 'sha256' in s:
            errors.append('sha256 requires artifact')
    check(bool(source_ids), 'source register required')
    inventory_ids = set()
    check(bool(m.get('inventory')), 'coverage inventory required')
    for i in m.get('inventory', []):
        check(all(nonempty(i.get(k)) for k in ('id', 'location', 'view', 'publication_state')), 'invalid inventory record')
        check(i.get('id') not in inventory_ids, 'duplicate inventory id')
        inventory_ids.add(i.get('id'))
        check(i.get('status') in {'inspected', 'blocked', 'excluded'}, 'invalid inventory status')
        if i.get('status') == 'inspected':
            check(bool(i.get('source_ids')) and set(i.get('source_ids', [])) <= source_ids, 'inventory source references missing/unresolved')
        else:
            check(nonempty(i.get('reason')), 'blocked/excluded inventory needs reason')
    file_ids = set()
    check(isinstance(m.get('file_reviews', []), list), 'file_reviews must be an array')
    for f in m.get('file_reviews', []) if isinstance(m.get('file_reviews', []), list) else []:
        if not isinstance(f, dict):
            errors.append('invalid file review record')
            continue
        check(all(nonempty(f.get(k)) for k in ('source_id', 'file_id', 'name', 'format', 'reason')), 'invalid file review record')
        check(f.get('source_id') in source_ids, 'unresolved file review source')
        check(f.get('file_id') not in file_ids, 'duplicate file review')
        file_ids.add(f.get('file_id'))
        check(type(f.get('content_check_required')) is bool, 'file content_check_required must be boolean')
        check(f.get('role') in {'instructional_document', 'linked_instructional_resource', 'contextual_image_or_media',
                              'instructor_reference', 'unlinked_document_candidate', 'unreferenced_asset'}, 'invalid file role')
        check(f.get('check_type') in {'document_content', 'resource_content', 'contextual_accessibility', 'scope_confirmation', 'inventory_only'}, 'invalid file check type')
        check(f.get('check_status') in {'pending', 'verified', 'blocked', 'excluded'}, 'invalid file check status')
        references = f.get('references')
        check(isinstance(references, list), 'file references must be an array')
        if isinstance(references, list):
            check(all(isinstance(x, dict) and x.get('source_id') in source_ids and type(x.get('instructor_only')) is bool for x in references), 'invalid file reference')
    check(r.get('status') in {'completed', 'partial', 'failed'}, 'invalid report status')
    stages = r.get('stages', {})
    check(set(stages) == {'design', 'grammar', 'narrative'} and all(v in OUTCOMES for v in stages.values()), 'invalid stage outcomes')
    if r.get('status') == 'completed':
        check(all(v == 'completed' for v in stages.values()), 'completed report has unfinished stages')
    else:
        check(bool(r.get('limitations')), 'partial/failed report requires limitations')
    if r.get('status') != 'failed':
        check(not any(v in {'failed', 'not_started'} for v in stages.values()), 'usable report contains failed/unstarted stage')
    records = r.get('criteria', [])
    ids = [c.get('id') for c in records]
    check(all(type(cid) is int and cid in IDS for cid in ids) and len(set(ids)) == len(ids), 'invalid/duplicate criterion ids')
    if r.get('status') != 'failed':
        check(set(ids) == IDS, 'expected all 42 criterion ids (no 25)')
    for c in records:
        prefix = f"CU {c.get('id')}: "
        rating, state = c.get('rating'), c.get('evidence_status')
        check(rating is None or rating in RATINGS, prefix + 'invalid rating')
        check(state in STATES, prefix + 'invalid evidence status')
        check(nonempty(c.get('evidence')), prefix + 'evidence required')
        check(isinstance(c.get('source_ids'), list) and bool(c.get('source_ids')) and set(c.get('source_ids', [])) <= source_ids, prefix + 'missing/unresolved sources')
        check(all(isinstance(c.get(k), str) for k in ('action_plan', 'verification_step', 'uncertainty')), prefix + 'text fields required')
        check(type(c.get('deferred')) is bool, prefix + 'deferred boolean required')
        if rating in REVISIONS:
            check(state in {'verified', 'not_evidenced'} and nonempty(c.get('action_plan')), prefix + 'revision needs established deficiency and action')
        elif rating == 'Present':
            check(state == 'verified', prefix + 'Present requires verified evidence')
        elif rating == 'N/A':
            check(state == 'not_applicable', prefix + 'N/A requires not_applicable')
        elif rating is None:
            check(state == 'not_verified' and nonempty(c.get('verification_step')) and nonempty(c.get('uncertainty')), prefix + 'pending needs verification and uncertainty')
        if c.get('deferred'):
            check(rating is None, prefix + 'deferred cannot be rated')
    check(isinstance(r.get('grammar'), list), 'grammar array required')
    for g in r.get('grammar', []):
        check(g.get('source_id') in source_ids and all(nonempty(g.get(k)) for k in ('issue', 'suggested_fix')), 'invalid grammar record')
    narrative, count, coverage = '', 0, []
    if r.get('status') != 'failed':
        n = r.get('narrative', {})
        check(n.get('file') == 'narrative.md', 'narrative file must be narrative.md')
        try:
            narrative = local_file(root, n.get('file')).read_text()
        except ValueError as e:
            errors.append(str(e))
        count = len(narrative.split())
        check(0 < count <= 600, f'narrative word count {count}; maximum 600')
        first = next((line for line in narrative.splitlines() if line.strip()), '')
        check(first.startswith('Subject:') and m.get('course', {}).get('name', '') in first, 'subject must include exact course name')
        if r.get('status') == 'partial':
            check('partial review' in narrative.lower(), 'narrative must disclose partial review')
        coverage = n.get('coverage', [])
        expected = {c['id'] for c in records if c.get('rating') in PRIORITIES}
        covered = [entry.get('criterion_id') for entry in coverage]
        check(set(covered) == expected and len(covered) == len(expected), 'narrative must map every Moderate/Major criterion exactly once')
        for entry in coverage:
            check(nonempty(entry.get('passage')) and entry['passage'] in narrative, 'coverage passage absent from narrative')
            check(nonempty(entry.get('next_step')) and entry['next_step'] in entry.get('passage', ''), 'mapped next step absent from passage')
        tips = n.get('teaching_tips', [])
        check(len(set(tips)) >= 3 and all(nonempty(t) and t in narrative for t in tips), 'three distinct teaching-tip excerpts required')
        for key in ('strengths_excerpt', 'closing_excerpt'):
            check(nonempty(n.get(key)) and n[key] in narrative, f'{key} absent from narrative')
    return errors, narrative, count, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    root = args.run_directory.resolve()
    if not root.is_dir():
        parser.error('run directory does not exist')
    narrative, count, coverage = '', 0, []
    try:
        m = json.loads(local_file(root, 'manifest.json').read_text())
        r = json.loads(local_file(root, 'review.json').read_text())
        errors, narrative, count, coverage = validate(root, m, r)
        if not errors:
            report = render(m, r, narrative)
            if args.render:
                (root / 'review.md').write_text(report)
            elif local_file(root, 'review.md').read_text() != report:
                errors.append('review.md differs from validated rendering; rerun --render')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        errors = [f'invalid input: {e}']
    result = {'valid': not errors, 'errors': errors, 'narrative_word_count': count, 'narrative_coverage': coverage}
    (root / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'valid': not errors, 'errors': errors, 'narrative_word_count': count}))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
