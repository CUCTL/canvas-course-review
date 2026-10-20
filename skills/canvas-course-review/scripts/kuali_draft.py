#!/usr/bin/env python3
"""Prepare and verify Kuali draft transfers locally; never sends requests."""
import argparse
import html
import json
import re
from pathlib import Path

IDS = set(range(1, 25)) | set(range(26, 44))
RATINGS = {'Present', 'Minor Revision', 'Moderate Revision', 'Major Revision', 'NA'}
SCHEMA_CACHE = Path(__file__).resolve().parents[1] / 'assets/kuali-cuocdr-form.json'


def read(path):
    return json.loads(Path(path).read_text())


def document(response):
    if response.get('errors'):
        raise ValueError('GraphQL response contains errors')
    doc = response.get('data', {}).get('document')
    if not isinstance(doc, dict) or not doc.get('id') or not isinstance(doc.get('data'), dict):
        raise ValueError('Expected an independent document query response with id, status and data')
    if doc.get('status') != 'saved':
        raise ValueError('Target is not a saved, unsubmitted draft')
    return doc


def map_form(form):
    fields, gadgets, mapping = {}, {}, {}

    def walk(value):
        if isinstance(value, dict):
            if 'formKey' in value and 'details' in value:
                key = value['formKey'].removeprefix('data.')
                if key in gadgets:
                    raise ValueError(f'Duplicate template field: {key}')
                gadgets[key] = value
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(form['template'])
    current = None
    for field in form['schema']:
        key = field['formKey']
        if not key.startswith('data.') or '.' in key[5:]:
            continue  # Derived .id/.label fields are not writable form keys.
        key, label = key[5:], field['label'].strip()
        if key in fields:
            raise ValueError(f'Duplicate schema field: {key}')
        fields[key] = label
        match = re.match(r'#(\d+)\b', label)
        if match:
            current = int(match[1])
            if current in mapping:
                raise ValueError(f'Duplicate criterion: {current}')
            mapping[current] = {'rating_key': key}
        elif label == 'Action Plan':
            if current is None or 'action_key' in mapping[current]:
                raise ValueError('Ambiguous Action Plan mapping; inspect schema manually')
            mapping[current]['action_key'] = key
        else:
            current = None
    if set(mapping) != IDS or any('action_key' not in v for v in mapping.values()):
        raise ValueError('Schema must map all 42 CUOCDR criteria and their action fields')
    special = {}
    for label in ('Course', 'Narrative Summary of Review'):
        matches = [key for key, value in fields.items() if value == label]
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one {label} field')
        special[label] = matches[0]
    return mapping, gadgets, special


def narrative_html(text):
    text = re.sub(r'\[([^]]+)\]\(#cu-(\d+)\)', lambda m: f'{m[1]} (CU {m[2]})', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    return ''.join('<p>' + html.escape(p).replace('\n', '<br>') + '</p>'
                   for p in text.strip().split('\n\n'))


def action_text(criterion):
    """Transfer tasks and destinations, including legacy links and pending checks."""
    rating = criterion['rating']
    if rating in ('Present', 'N/A'):
        return ''
    links = criterion.get('action_links', [])
    paired = any('action' in link for link in links)
    tasks, actions = [], []
    if paired:
        for link in links:
            task = link.get('action')
            if not isinstance(task, str) or not task.strip():
                raise ValueError(f'CU {criterion["id"]} paired links each require an action')
            task = task.strip()
            tasks.append(task)
            actions.append(task + ('\n' + link['url'] if link.get('url') else ''))
    else:
        # Older reports store one action plan beside a separate list of links.
        task = criterion.get('action_plan', '').strip()
        if task:
            tasks.append(task)
            actions.append(task)
    verification = criterion.get('verification_step', '').strip()
    if verification and not any(verification in task for task in tasks):
        tasks.append(verification)
        actions.append(verification)
    if not tasks:
        raise ValueError(f'CU {criterion["id"]} requires an action or verification task')
    if not paired:
        for link in links:
            if link.get('url'):
                label = link.get('label', '').strip()
                actions.append((label + ': ' if label else '') + link['url'])
    text = '\n\n'.join(dict.fromkeys(actions))
    if re.search(r'(?im)^\s*(finding|evidence|limit|verification|instructor preparation)\s*:', text):
        raise ValueError(f'CU {criterion["id"]} action contains reviewer metadata; rewrite it as actions only')
    return text


def prepare(review, narrative, response, course_code, replace_fields=()):
    doc = document(response)
    mapping, gadgets, special = map_form(doc['form'])
    course_key = special['Course']
    course = doc['data'].get(course_key)
    if not isinstance(course, dict) or course.get('id') != course_code:
        raise ValueError('Selected Kuali course does not match --course-code exactly')
    records = review['criteria']
    if len(records) != 42 or {c['id'] for c in records} != IDS:
        raise ValueError('Review must contain each of the 42 criterion IDs exactly once')
    desired, unresolved, blank_ratings = {}, [], []
    for criterion in records:
        cid, rating = criterion['id'], criterion['rating']
        item = mapping[cid]
        if rating is None:
            unresolved.append(cid)
            blank_ratings.append(item['rating_key'])
        else:
            label = 'NA' if rating == 'N/A' else rating
            if label not in RATINGS:
                raise ValueError(f'Unsupported rating: {rating}')
            options = gadgets[item['rating_key']]['details']['options']
            options = [o for o in options if o.get('lbl') == label]
            if len(options) != 1:
                raise ValueError(f'Unmapped or ambiguous rating option for CU {cid}')
            desired[item['rating_key']] = {'id': options[0]['key'], 'label': label}
        desired[item['action_key']] = action_text(criterion)
    desired[special['Narrative Summary of Review']] = narrative_html(narrative)
    replace_fields = set(replace_fields)
    if replace_fields - desired.keys():
        raise ValueError('Replacement selection includes an unknown/non-target field')
    payload, conflicts = {}, []
    baseline = doc['data']
    for key, value in desired.items():
        old = baseline.get(key)
        if old == value or (old in (None, '') and value == ''):
            continue
        if old not in (None, '') and key not in replace_fields:
            conflicts.append({'field': key, 'existing': old, 'proposed': value})
        else:
            payload[key] = value
    # A null assessment cannot silently erase an existing human-selected rating.
    for key in blank_ratings:
        if baseline.get(key) not in (None, ''):
            conflicts.append({'field': key, 'existing': baseline[key], 'proposed': None,
                              'reason': 'Resolve an existing rating for an unverified criterion manually'})
    return {'document_id': doc['id'], 'form_id': doc['form']['id'],
            'course_key': course_key, 'course': course, 'baseline': baseline,
            'mapping': mapping, 'unresolved_criteria': unresolved,
            'blank_rating_keys': blank_ratings, 'desired': desired,
            'payload': payload, 'conflicts': conflicts, 'ready': not conflicts}


def verify(plan, response):
    doc = document(response)
    if not plan['ready'] or doc['id'] != plan['document_id']:
        raise ValueError('Conflicted plan or wrong document ID')
    if doc.get('form', {}).get('id') not in (None, plan['form_id']):
        raise ValueError('Form version changed; refresh schema and remap')
    data, errors, conditional = doc['data'], [], []
    for key, expected in plan['desired'].items():
        actual = data.get(key)
        if actual == expected or (expected == '' and actual in (None, '')):
            continue
        errors.append(key)
    for key in plan['blank_rating_keys']:
        if data.get(key) not in (None, ''):
            errors.append(key)
    for item in plan['mapping'].values():
        rating = data.get(item['rating_key'])
        if isinstance(rating, dict) and rating.get('label') == 'Present' and item['action_key'] not in data:
            conditional.append(item['action_key'])
    empty_actions = {item['action_key'] for item in plan['mapping'].values()
                     if plan['desired'].get(item['action_key']) == ''}
    changes = [k for k in sorted(plan['baseline'].keys() | data.keys())
               if k not in plan['payload'] and plan['baseline'].get(k) != data.get(k)
               and not (k in empty_actions and plan['baseline'].get(k) in (None, '')
                        and data.get(k) in (None, ''))]
    return {'api_verified': not errors and not changes,
            'status': doc['status'], 'target_mismatches': errors,
            'unrequested_changes': changes, 'hidden_present_actions_omitted': conditional,
            'browser_reload_required': True, 'submitted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    prep = subs.add_parser('prepare')
    prep.add_argument('run_directory', type=Path)
    prep.add_argument('--state', required=True, type=Path)
    prep.add_argument('--schema', type=Path, default=SCHEMA_CACHE,
                      help='Cached form metadata; refresh only on schema failure')
    prep.add_argument('--course-code', required=True)
    prep.add_argument('--out', required=True, type=Path)
    prep.add_argument('--replace-field', action='append', default=[])
    check = subs.add_parser('verify')
    check.add_argument('--plan', required=True, type=Path)
    check.add_argument('--readback', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            state = read(args.state)
            doc = document(state)
            # Normal reads need no schema request. A supplied fresh form wins.
            if not doc.get('form'):
                doc['form'] = read(args.schema)
            plan = prepare(read(args.run_directory / 'review.json'),
                           (args.run_directory / 'narrative.md').read_text(),
                           state, args.course_code, args.replace_field)
            args.out.mkdir(parents=True, exist_ok=False)
            def save(name, value):
                (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
            save('plan.json', plan)
            if not plan['ready']:
                print(json.dumps({'ready': False, 'conflicts': len(plan['conflicts']),
                                  'out': str(args.out), 'mutation_generated': False}))
                return 2
            save('variables.json', {'data': plan['payload']})
            (args.out / 'mutation.graphql').write_text(
                'mutation SaveReviewDraft($data: JSON!) {\n'
                '  updateDocument(args: {id: ' + json.dumps(plan['document_id']) +
                ', data: $data}) {id status data}\n}\n')
            (args.out / 'readback.graphql').write_text(
                'query ReadReviewDraft { document(id: ' + json.dumps(plan['document_id']) +
                ') {id status data} }\n')
            print(json.dumps({'ready': plan['ready'], 'fields_to_write': len(plan['payload']),
                              'conflicts': len(plan['conflicts']), 'out': str(args.out)}))
            return 0 if plan['ready'] else 2
        result = verify(read(args.plan), read(args.readback))
        print(json.dumps(result, indent=2))
        return 0 if result['api_verified'] else 2
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
