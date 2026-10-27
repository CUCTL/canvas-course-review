#!/usr/bin/env python3
"""Validate CUOCDR run artifacts and optionally render the Markdown report."""
import argparse
import hashlib
import json
import re
from html import escape
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

CURRENT_REVIEW_SCHEMA = 2
IDS = set(range(1, 44)) - {25}
RATINGS = {'Present', 'Minor Revision', 'Moderate Revision', 'Major Revision', 'N/A'}
REVISIONS = {'Minor Revision', 'Moderate Revision', 'Major Revision'}
PRIORITIES = {'Moderate Revision', 'Major Revision'}
STATES = {'verified', 'not_evidenced', 'not_verified', 'not_applicable'}
OUTCOMES = {'completed', 'partial', 'failed', 'not_started'}
LEVELS = {
    'api_content': '1 — API content + narrative',
    'api_browser': '2 — API content + necessary browser verification + narrative',
    'api_browser_blind': '3 — API content + necessary browser verification + blind assessment + narrative',
}


def report_stem(manifest):
    """Stable, filesystem-safe basename shared by Markdown and PDF deliverables."""
    course = manifest['course']
    def component(value):
        return re.sub(r'[^A-Za-z0-9_-]+', '_', str(value)).strip('_-')
    course_id = component(course['id'])
    code = component(course.get('course_code') or course['name'])
    if not course_id or not code:
        raise ValueError('course identity cannot form a report filename')
    stamp = manifest.get('follow_up', {}).get('updated_at') or manifest['snapshot_at']
    timestamp = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if timestamp.utcoffset() is None:
        raise ValueError('report filename timestamp requires a timezone')
    return f'{course_id}-{code}_review_{int(timestamp.timestamp())}'


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


def writing_review_input(manifest, review, narrative):
    """Freeze audience text and read-only factual context for the style reviewer."""
    fields = ('id', 'rating', 'evidence_status', 'evidence', 'na_reason', 'action_plan',
              'verification_step', 'uncertainty', 'action_links', 'template_placeholder')
    return {
        'course': manifest['course'], 'status': review['status'],
        'limitations': manifest['limitations'] + review['limitations'],
        'narrative': narrative, 'narrative_coverage': review.get('narrative', {}).get('coverage', []),
        'criteria': [{key: c[key] for key in fields if key in c}
                     for c in sorted(review['criteria'], key=lambda c: c['id'])],
        'grammar': review['grammar'],
    }


def writing_review_hash(content):
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def writing_review_errors(root, m, r, narrative, require=False):
    """Validate agent approval independently of legacy report compatibility."""
    errors = []
    def check(condition, message):
        if not condition:
            errors.append(message)
    writing = r.get('writing_review')
    if require and writing is None:
        errors.append('current review requires writing_review metadata')
    if writing is not None:
        if not isinstance(writing, dict):
            errors.append('writing_review must be an object')
        else:
            status = writing.get('status')
            check(status in {'pending', 'passed', 'needs_revision', 'unavailable'}, 'invalid writing review status')
            check(isinstance(writing.get('limitations'), list)
                  and all(nonempty(x) for x in writing.get('limitations', [])), 'invalid writing review limitations')
            if status == 'passed':
                check(nonempty(writing.get('reviewer')), 'writing review requires a separate reviewer')
                current_hash = writing_review_hash(writing_review_input(m, r, narrative))
                check(writing.get('content_sha256') == current_hash, 'writing review is stale; recheck the changed content')
                try:
                    assessment = json.loads(local_file(root, writing.get('report')).read_text())
                    check(isinstance(assessment, dict), 'writing assessment must be an object')
                    if isinstance(assessment, dict):
                        check(assessment.get('status') == 'passed' and assessment.get('issues') == [],
                              'writing assessment has not passed or has unresolved issues')
                        check(assessment.get('content_sha256') == current_hash,
                              'writing assessment does not cover the current content')
                        check(assessment.get('reviewer') == writing.get('reviewer'), 'writing reviewer mismatch')
                except (ValueError, TypeError, OSError) as exc:
                    errors.append(f'writing assessment: {exc}')
            else:
                check(bool(writing.get('limitations')), 'incomplete writing review requires limitations')
                check(r.get('status') != 'completed', 'completed report has incomplete writing style review')
    return errors


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


def action_links(record):
    """Render inspected course destinations; never guess from source IDs."""
    links = []
    for link in record.get('action_links', []):
        label = link['label'].replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('\n', ' ')
        url = quote(link['url'], safe=':/?#@!$&*=+%;,~._-')
        links.append(f'[{label}]({url})')
    return ' · '.join(links)


def action_pairs(record, table=False):
    """Keep each specific task adjacent to its destination in the action list."""
    links = record.get('action_links', [])
    if not links or not all(nonempty(link.get('action')) for link in links):
        return ''
    if table:
        items = []
        for link in links:
            url = quote(link['url'], safe=':/?#@!$&*=+%;,~._-')
            items.append(f'<li>{escape(link["action"])} — '
                         f'<a href="{escape(url, quote=True)}">{escape(link["label"])}</a></li>')
        return '<ul>' + ''.join(items) + '</ul>'
    return '\n'.join(f'  - {link["action"]} — {action_links({"action_links": [link]})}' for link in links)


def render(manifest, review, narrative):
    course = manifest['course']
    lines = [f"# {course['name']} — CUOCDR review", '', f"Status: **{review['status']}**",
             f"Course ID: {course['id']}", f"Snapshot: {manifest['snapshot_at']}",
             f"Mode: {manifest['mode']}", f"Rubric: {manifest['rubric_version']}"]
    level = review.get('review_level')
    if level is not None:
        lines += [f"Review level: {LEVELS[level]} ({review['level_selection']})"]
        if level == 'api_content':
            lines += ['', 'Browser verification and independent blind assessment were outside the selected review scope. Browser-dependent conclusions remain unverified unless supported by supplied evidence within its stated scope.']
        elif level == 'api_browser':
            lines += ['', 'Independent blind assessment was outside the selected review scope.']
    confirmation = review.get('confirmation')
    if confirmation:
        if confirmation['status'] == 'reconciled' and confirmation['blind']:
            lines += ['', 'Confirmation: Independent blind assessment completed, followed by reconciliation and a policy-consistency audit. [Details](confirmation/reconciliation.md)']
        else:
            lines += ['', f"Confirmation: {confirmation['status']}; independent blind confirmation remains incomplete."]
    pending = sum(c['rating'] is None and not c['deferred'] for c in review['criteria'])
    deferred = sum(c['deferred'] for c in review['criteria'])
    if review['status'] != 'completed' or pending or deferred or manifest['limitations'] or review['limitations']:
        lines += ['', f"Review note: Pending criterion checks: {pending}; deferred items: {deferred}. "
                  "Read Scope and limitations below for evidence gaps and review boundaries."]
    if narrative:
        embedded = re.sub(r'^Subject:[^\n]*\n*', '', narrative.strip())
        lines += ['', '## Faculty overview', '', embedded]
    lines += ['', '## Detailed design findings', '',
              'Each action is paired with its course location. Pending verification and instructor preparation remain distinct from confirmed revisions.']
    records = {c['id']: c for c in review['criteria']}
    for title, items in rubric():
        lines += ['', f'## {title}', '', '| CU / ID | Criterion | Rating | Findings / scope | Action / verification |',
                  '| --- | --- | --- | --- | --- |']
        for cid, wording in items:
            c = records.get(cid)
            if c is None:
                lines.append(f'| {cid} | {wording} | Unreviewed | Review failed before evaluation. | Resume review. |')
                continue
            label = c['rating'] or ('Deferred' if c['deferred'] else 'Pending verification')
            evidence = f"{c['evidence']} [Evidence](evidence-register.md#criterion-{cid})"
            action = c['action_plan'] or c['verification_step'] or '—'
            if c['uncertainty']:
                action += f" Uncertainty: {c['uncertainty']}"
            related = action_links(c)
            paired = action_pairs(c, table=True)
            if paired:
                action = paired + (f" Uncertainty: {c['uncertainty']}" if c['uncertainty'] else '')
            elif related:
                action += f'\nRelated locations: {related}'
            if c['rating'] == 'N/A':
                # Historical records keep their rationale in evidence.
                reason = c.get('na_reason', c['evidence']).strip()
                action = reason + (f" Uncertainty: {c['uncertainty']}" if c['uncertainty'] else '')
                if related:
                    action += f'\nRelated locations: {related}'
            placeholder = c.get('template_placeholder')
            if placeholder:
                action += f'\nInstructor preparation reminder: {placeholder["reminder"]}'
                preparation_links = action_links(placeholder)
                if preparation_links:
                    action += f' — {preparation_links}'
            lines.append('| ' + ' | '.join(cell(v) for v in (cid, f'<a id="cu-{cid}"></a>{wording}', label, evidence, action)) + ' |')
    placeholders = [c for c in review['criteria'] if c.get('template_placeholder')]
    if placeholders:
        lines += ['', '## Instructor preparation reminders', '']
        for c in placeholders:
            related = action_links(c['template_placeholder'])
            lines.append(f'- CU {c["id"]}: {c["template_placeholder"]["reminder"]}' +
                         (f' — {related}' if related else ''))
    lines += ['', '## Mechanical grammar and spelling', '']
    lines += [f"- {g['issue']} Suggested fix: {g['suggested_fix']} [Evidence register](evidence-register.md)" for g in review['grammar']] or [
        'No confirmed mechanical issues found.' if review['stages']['grammar'] == 'completed' else 'Mechanical review incomplete; see limitations.']
    lines += ['', '## Scope and limitations', '', f"Scope: {manifest['scope']}", '']
    lines += [f'- {item}' for item in manifest['limitations'] + review['limitations']] or ['No recorded limitations.']
    lines += ['', '## Stage outcomes', '']
    lines += [f"- {key}: {value}" for key, value in review['stages'].items()]
    lines += ['', 'Detailed sources, criterion evidence mappings, and verification coverage are saved in the separate [evidence register](evidence-register.md).']
    return '\n'.join(lines) + '\n'


def render_evidence(manifest, review, checks=None):
    """Reviewer appendix; full machine provenance stays in manifest.json."""
    lines = [f"# {manifest['course']['name']} — Evidence register", '',
             f"Snapshot: {manifest['snapshot_at']}", '',
             'Supporting evidence for [the faculty report](review.md). Source retrieval marked inspected does not itself verify content, accessibility, or learner access. Excluded files remain only in internal JSON artifacts.',
             '', '## Criterion evidence map', '']
    for c in review['criteria']:
        lines += [f"### Criterion {c['id']}", '',
                  f"Rating: {c['rating'] or ('Deferred' if c['deferred'] else 'Pending verification')}; evidence state: {c['evidence_status']}.",
                  f"Sources: {', '.join(c['source_ids'])}", '', c['evidence']]
    if any(c.get('template_placeholder') for c in review['criteria']):
        lines += ['', '## Template interpretation', '',
                  'Internal reviewer interpretation: intentional instructor-completion scaffolds count as Present only when the other criterion requirements are met. This verifies the scaffold, not completed personalization or learner visibility. Preparation reminders are separate from confirmed revisions.']
    lines += ['', '## Grammar evidence map', '']
    lines += [f"- {g['source_id']}: {g['issue']} — {g['suggested_fix']}" for g in review['grammar']] or ['No recorded mechanical findings.']
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
    if checks is not None:
        lines += ['', '## Verification dispositions', '',
                  'Verified means the recorded scope has evidence; blocked means an attempted check could not resolve that scope; excluded means outside scope or consolidated elsewhere. None implies universal accessibility.', '']
        for c in checks.get('checks', []):
            if excluded_source(c.get('file_source_id', c['id'])):
                continue
            lines.append(f"- {c['id']}: {c['status']}; method: {c.get('verification_method', c.get('preferred_method', 'unspecified'))}; {c.get('verification_scope', c.get('scope_reason', c.get('reason', '')))} Sources: {', '.join(c.get('source_ids', []))}")
    writing = review.get('writing_review')
    if writing:
        lines += ['', '## Writing style review', '', f"Status: {writing['status']}."]
        if writing.get('report'):
            lines.append(f"[Agent assessment]({writing['report']})")
        lines += [f'- {limit}' for limit in writing.get('limitations', [])]
    return '\n'.join(lines) + '\n'


def validate(root, m, r):
    errors = []
    def check(condition, message):
        if not condition:
            errors.append(message)
    for obj, label in ((m, 'manifest'), (r, 'review')):
        allowed = {1} if label == 'manifest' else {1, CURRENT_REVIEW_SCHEMA}
        check(type(obj.get('schema_version')) is int and obj.get('schema_version') in allowed,
              f'{label}: unsupported schema_version')
        check(isinstance(obj.get('limitations'), list) and all(nonempty(x) for x in obj.get('limitations', [])), f'{label}: invalid limitations')
    check(all(nonempty(m.get('course', {}).get(k)) for k in ('id', 'name')), 'course id/name required')
    check(m.get('mode') in {'pre_launch', 'published_view', 'supplied_export'}, 'invalid mode')
    if 'course_type' in m:
        check(m.get('course_type') in ('master_blueprint', 'course_offering'), 'invalid course type')
    check(nonempty(m.get('scope')), 'scope required')
    check(m.get('rubric_version') == 'CUOCDR v0.9', 'invalid rubric version')
    try:
        check(datetime.fromisoformat(m['snapshot_at'].replace('Z', '+00:00')).utcoffset() is not None, 'snapshot timezone required')
    except (KeyError, ValueError, TypeError, AttributeError):
        errors.append('invalid snapshot_at')
    source_ids = set()
    source_records = {}
    for s in m.get('sources', []):
        check(all(nonempty(s.get(k)) for k in ('id', 'location', 'description')), 'invalid source record')
        check(s.get('id') not in source_ids, 'duplicate source id')
        source_ids.add(s.get('id'))
        source_records[s.get('id')] = s
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
    inspected_sources = {sid for item in m.get('inventory', []) if item.get('status') == 'inspected'
                         for sid in item.get('source_ids', [])}
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
    confirmation = r.get('confirmation')
    level = r.get('review_level')
    if 'review_level' in r:
        check(isinstance(level, str) and level in LEVELS, 'invalid review level')
        selection = r.get('level_selection')
        check(selection in ('user_selected', 'default'), 'invalid level selection')
        if selection == 'default':
            check(level == 'api_browser', 'default review level must be api_browser')
        if level in ('api_content', 'api_browser'):
            check(confirmation is None, 'levels 1–2 exclude independent confirmation; use level 3')
        if level == 'api_browser_blind' and r.get('status') != 'failed':
            check(isinstance(confirmation, dict), 'level 3 requires confirmation metadata')
    elif 'level_selection' in r:
        errors.append('level selection requires review level')
    if confirmation is not None:
        if not isinstance(confirmation, dict):
            errors.append('confirmation must be an object')
        else:
            check(confirmation.get('status') in {'reconciled', 'pending', 'unavailable'}, 'invalid confirmation status')
            check(type(confirmation.get('blind')) is bool, 'confirmation blind must be boolean')
            check(isinstance(confirmation.get('limitations'), list) and all(nonempty(x) for x in confirmation.get('limitations', [])), 'invalid confirmation limitations')
            if confirmation.get('status') == 'reconciled':
                check(confirmation.get('blind') is True, 'reconciled confirmation requires an independent blind assessment')
                for field in ('input_index', 'independent_assessment', 'reconciliation', 'policy_audit'):
                    try:
                        local_file(root, confirmation.get(field, ''))
                    except (ValueError, TypeError) as e:
                        errors.append(f'confirmation {field}: {e}')
                check(confirmation.get('reconciliation') == 'confirmation/reconciliation.md', 'confirmation reconciliation must use its report link path')
            else:
                check(bool(confirmation.get('limitations')), 'incomplete confirmation requires limitations')
                check(r.get('status') != 'completed', 'completed report has incomplete independent confirmation')
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
        groups = [c.get('action_links', [])]
        placeholder = c.get('template_placeholder')
        if isinstance(placeholder, dict):
            groups.append(placeholder.get('action_links', []))
        for links in groups:
            check(isinstance(links, list), prefix + 'action_links must be an array')
            paired = isinstance(links, list) and any(isinstance(link, dict) and 'action' in link for link in links)
            for link in links if isinstance(links, list) else []:
                if not isinstance(link, dict):
                    errors.append(prefix + 'invalid action link')
                    continue
                check(all(nonempty(link.get(k)) for k in ('label', 'url', 'source_id')), prefix + 'action link label/url/source_id required')
                if paired:
                    check(nonempty(link.get('action')), prefix + 'paired action links each need a specific action')
                sid = link.get('source_id')
                check(isinstance(sid, str) and sid in c.get('source_ids', []), prefix + 'action link needs a criterion source')
                try:
                    target = urlsplit(link.get('url', ''))
                    record = source_records.get(sid, {})
                    source = urlsplit(record.get('location', ''))
                    course_path = f"/courses/{m.get('course', {}).get('id')}"
                    path = unquote(target.path)
                    in_course = path == course_path or path.startswith(course_path + '/')
                    external_document = (record.get('kind') == 'external_document'
                                         and record.get('course_id') == m.get('course', {}).get('id')
                                         and sid in inspected_sources
                                         and not re.match(r'^/courses(?:/|$)', path))
                    check(target.scheme == 'https' and bool(target.netloc) and not target.username and not target.password
                          and '..' not in path.split('/') and (in_course or external_document)
                          and (target.scheme, target.netloc, unquote(target.path), target.query) ==
                              (source.scheme, source.netloc, unquote(source.path), source.query),
                          prefix + 'action link must match its registered HTTPS course source or inspected external document')
                except (ValueError, TypeError, AttributeError):
                    errors.append(prefix + 'invalid action link URL/source')
        if rating in REVISIONS:
            check(state in {'verified', 'not_evidenced'} and nonempty(c.get('action_plan')), prefix + 'revision needs established deficiency and action')
        elif rating == 'Present':
            check(state == 'verified', prefix + 'Present requires verified evidence')
        elif rating == 'N/A':
            check(state == 'not_applicable', prefix + 'N/A requires not_applicable')
            check(nonempty(c.get('na_reason', c.get('evidence'))),
                  prefix + 'N/A requires an explanation for the actions column')
        if 'na_reason' in c:
            check(rating == 'N/A' and nonempty(c['na_reason']),
                  prefix + 'na_reason requires an N/A rating and a nonempty explanation')
        if rating is None:
            check(state == 'not_verified' and nonempty(c.get('verification_step')) and nonempty(c.get('uncertainty')), prefix + 'pending needs verification and uncertainty')
        if c.get('deferred'):
            check(rating is None, prefix + 'deferred cannot be rated')
        if 'template_placeholder' in c:
            placeholder = c['template_placeholder']
            check(m.get('course_type') == 'master_blueprint', prefix + 'template placeholder requires master_blueprint course type')
            check(isinstance(placeholder, dict) and all(nonempty(placeholder.get(k)) for k in ('scope', 'reminder')),
                  prefix + 'template placeholder needs scope and instructor reminder')
            check(c.get('deferred') is False, prefix + 'intentional template placeholder must not be deferred')
            check(rating != 'N/A', prefix + 'template placeholder is not a reason for N/A')
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
        narrative_format = n.get('format', 'email')
        check(narrative_format in {'email', 'report_overview'}, 'invalid narrative format')
        if narrative_format == 'email':
            check(first.startswith('Subject:') and m.get('course', {}).get('name', '') in first, 'subject must include exact course name')
        else:
            check(not first.startswith('Subject:'), 'report overview must omit email subject')
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
        check(isinstance(tips, list) and len(tips) >= 3
              and all(nonempty(t) and t in narrative for t in tips)
              and len({t.strip().casefold() for t in tips if nonempty(t)}) == len(tips),
              'at least three distinct teaching-tip excerpts must be present in the narrative')
        for key in ('strengths_excerpt', 'closing_excerpt'):
            check(nonempty(n.get(key)) and n[key] in narrative, f'{key} absent from narrative')
    errors.extend(writing_review_errors(root, m, r, narrative,
                                       require=r.get('schema_version') == CURRENT_REVIEW_SCHEMA and r.get('status') != 'failed'))
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
        if args.render and r.get('schema_version') != CURRENT_REVIEW_SCHEMA:
            errors.append('rendering requires review schema_version 2 and a current writing review; preserve the legacy report and revise a copy')
        if not errors:
            report = render(m, r, narrative)
            queue_path = root / 'browser-checks.json'
            checks = json.loads(local_file(root, 'browser-checks.json').read_text()) if queue_path.exists() else None
            evidence = render_evidence(m, r, checks)
            outputs = [('review.md', report), ('evidence-register.md', evidence)]
            # Existing runs remain valid without a named copy until explicitly rendered.
            named_report = report_stem(m) + '.md'
            if args.render or (root / named_report).exists():
                outputs.append((named_report, report))
            for filename, content in outputs:
                if args.render:
                    (root / filename).write_text(content)
                elif local_file(root, filename).read_text() != content:
                    errors.append(f'{filename} differs from validated rendering; rerun --render')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        errors = [f'invalid input: {e}']
    result = {'valid': not errors, 'errors': errors, 'narrative_word_count': count, 'narrative_coverage': coverage}
    if not errors:
        result['report_basename'] = report_stem(m)
    (root / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'valid': not errors, 'errors': errors, 'narrative_word_count': count}))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
