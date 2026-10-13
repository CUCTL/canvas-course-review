#!/usr/bin/env python3
"""Read-only Canvas course-design snapshot via canvasapi; no learner records."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

# Works both as a portable CLI and when loaded by fixture tests.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from file_scope import classify_files

# Select design fields, never serialize SDK internals, enrollments, replies, or grades.
FIELDS = {
    'course': 'id name course_code syllabus_body default_view workflow_state start_at end_at time_zone public_description restrict_enrollments_to_course_dates blueprint',
    'module': 'id name position published unlock_at require_sequential_progress prerequisite_module_ids completion_requirements items_count',
    'item': 'id title type position indent content_id page_url external_url html_url published new_tab content_details completion_requirement',
    'page': 'page_id url title body published front_page html_url editing_roles',
    'assignment': 'id name description html_url published position submission_types allowed_extensions due_at unlock_at lock_at points_possible grading_type rubric rubric_settings rubric_id use_rubric_for_grading has_overrides is_quiz_assignment quiz_id discussion_topic_id external_tool_tag_attributes',
    'discussion': 'id title message html_url published discussion_type delayed_post_at lock_at require_initial_post podcast_enabled assignment_id is_announcement',
    'quiz': 'id title description html_url published quiz_type time_limit shuffle_answers hide_results show_correct_answers show_correct_answers_at hide_correct_answers_at allowed_attempts scoring_policy one_question_at_a_time cant_go_back due_at unlock_at lock_at question_count assignment_id',
    'new_quiz': 'id title instructions quiz_settings assignment_id points_possible grading_type due_at lock_at unlock_at published',
    'question': 'id quiz_id question_name question_type question_text position points_possible answers correct_comments incorrect_comments neutral_comments correct_comments_html incorrect_comments_html neutral_comments_html',
    'rubric': 'id title points_possible free_form_criterion_comments data associations',
    'file': 'id display_name filename content-type size locked hidden locked_for_user hidden_for_user unlock_at lock_at folder_id mime_class',
    'tab': 'id label type html_url position hidden visibility',
    'settings': 'allow_student_discussion_topics allow_student_forum_attachments allow_student_discussion_editing allow_student_organized_groups hide_final_grades syllabus_course_summary restrict_student_past_view restrict_student_future_view',
}


def safe_url(value):
    """Remove credential/signature parameters while retaining resource identifiers."""
    parts = urlsplit(str(value))
    sensitive = re.compile(r'token|access[_-]?code|verifier|signature|credential|secret|api[_-]?key|authorization|^x-amz-|^x-goog-|^(key|auth|sig|expires|policy)$', re.I)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not sensitive.search(k)])
    return urlunsplit((parts.scheme, parts.netloc.rsplit('@', 1)[-1], parts.path, query, ''))


def select(obj, kind):
    values = obj if isinstance(obj, dict) else vars(obj)
    result = {key: values[key] for key in FIELDS[kind].split() if key in values}
    # Nested payloads can include unrelated fields (e.g., rubric assessment data).
    if kind == 'rubric' and isinstance(result.get('associations'), list):
        result['associations'] = [{k: a[k] for k in ('id', 'association_id', 'association_type', 'use_for_grading', 'purpose') if k in a} for a in result['associations']]
    if kind == 'assignment' and isinstance(result.get('external_tool_tag_attributes'), dict):
        result['external_tool_tag_attributes'] = {k: x for k, x in result['external_tool_tag_attributes'].items() if k in ('url', 'new_tab', 'resource_link_id')}
    if kind == 'new_quiz' and isinstance(result.get('quiz_settings'), dict):
        result['quiz_settings'] = {k: x for k, x in result['quiz_settings'].items() if k != 'student_access_code'}
    if kind == 'assignment' and isinstance(result.get('external_tool_tag_attributes'), dict):
        tool = result['external_tool_tag_attributes']
        if 'url' in tool:
            tool['url'] = safe_url(tool['url'])
    for key in ('html_url', 'external_url'):
        if key in result:
            result[key] = safe_url(result[key])
    return result


class HTMLInventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []
        self.text = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        target = attrs.get('href') if tag == 'a' else attrs.get('src')
        if tag in ('a', 'iframe', 'img', 'video', 'audio', 'source', 'track') and target:
            self.resources.append({'tag': tag, 'target': target, 'alt': attrs.get('alt'),
                                   'title': attrs.get('title'), 'kind': attrs.get('kind')})
    def handle_data(self, data):
        self.text.append(data)


class Collector:
    def __init__(self, canvas, course_id, output, base_url, mode='pre_launch'):
        self.canvas, self.course_id = canvas, int(course_id)
        self.root, self.base_url, self.mode = Path(output), base_url.rstrip('/'), mode
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / 'source').mkdir()
        self.sources, self.inventory, self.errors, self.browser_checks = [], [], [], []
        self.file_reviews = []
        self.objects, self.counts = {}, {}
        self.started = datetime.now(timezone.utc).isoformat()
        self.name = f'Course {course_id} (identity unavailable)'
        self.course_ok = False
        self.seen = set()
        self.link_seen = set()

    def location(self, path):
        return f'{self.base_url}/courses/{self.course_id}/{path}'.rstrip('/')

    def write_json(self, path, data):
        target = self.root / path
        temp = target.with_suffix(target.suffix + '.tmp')
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        temp.replace(target)

    def checkpoint(self, final=False):
        status = 'failed' if not self.course_ok else ('partial' if self.errors else 'completed')
        if not final:
            status = 'running'
        limitations = [f"{e['operation']}: {e['error_type']}; verify in browser or retry in a new run." for e in self.errors]
        limitations += ['API evidence is not rendered browser or learner-access verification.',
                        'Files are inventoried as metadata only; linked files/media/external tools require browser inspection.',
                        'New Quiz item/question contents are not exposed by the supported SDK methods; inspect in browser.',
                        'Availability overrides and individual accommodation/access conditions are not collected.']
        manifest = {'schema_version': 1, 'course': {'id': str(self.course_id), 'name': self.name},
                    'mode': self.mode, 'scope': 'Course-wide instructor/API design snapshot, including accessible drafts and unlinked content; published_view requires browser scope resolution.',
                    'snapshot_at': self.started, 'rubric_version': 'CUOCDR v0.9',
                    'sources': self.sources, 'inventory': self.inventory, 'limitations': limitations,
                    'collection': {'status': status, 'counts': self.counts, 'errors': self.errors},
                    'file_reviews': self.file_reviews}
        self.write_json('manifest.json', manifest)
        self.write_json('collection.json', {'status': status, 'counts': self.counts, 'errors': self.errors,
                                           'started_at': self.started, 'updated_at': datetime.now(timezone.utc).isoformat()})
        self.write_json('course.json', {'course_id': self.course_id, 'course_name': self.name, 'objects': self.objects})
        for candidate in self.browser_checks:
            candidate.setdefault('preferred_method', 'api_first')
        self.write_json('browser-checks.json', {'status': 'pending', 'checks': self.browser_checks})
        return status

    def error(self, operation, location, exc):
        # Never write exception messages: server bodies can contain tokens/private data.
        entry = {'operation': operation, 'location': safe_url(location), 'error_type': type(exc).__name__}
        self.errors.append(entry)
        key = f'error-{len(self.errors)}'
        path = f'source/{key}.json'
        self.write_json(path, entry)
        self.source(key, path, location, f'Failed/unsupported read: {operation}')
        self.inventory.append({'id': key, 'location': safe_url(location), 'view': 'API', 'publication_state': 'unknown',
                               'status': 'blocked', 'reason': f'{operation}: {type(exc).__name__}', 'source_ids': [key]})
        self.browser_checks.append({'id': key, 'location': safe_url(location), 'reason': 'Resolve failed/unsupported API read', 'status': 'pending'})
        self.checkpoint()

    def read(self, operation, location, fn):
        try:
            return fn()
        except Exception as exc:
            self.error(operation, location, exc)
            return None

    def iterate(self, operation, location, fn):
        self.counts[operation] = {'enumerated': 0, 'status': 'running'}
        try:
            for obj in fn():  # Exhaust canvasapi PaginatedList; keep items if a later page fails.
                self.counts[operation]['enumerated'] += 1
                yield obj
            self.counts[operation]['status'] = 'completed'
        except Exception as exc:
            self.counts[operation]['status'] = 'partial'
            self.error(operation, location, exc)
        self.checkpoint()

    def source(self, key, path, location, description):
        artifact = self.root / path
        self.sources.append({'id': key, 'location': safe_url(location), 'description': description,
                             'artifact': path, 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()})

    def save(self, obj, kind, ident, location, context=None):
        key = re.sub(r'[^a-zA-Z0-9_-]', '_', f'{kind}-{ident}')
        if key in self.seen:
            return key
        location = urljoin(self.base_url + '/', location)
        data = select(obj, kind)
        required_content = {'page': 'body', 'assignment': 'description', 'discussion': 'message',
                            'quiz': 'description', 'new_quiz': 'instructions', 'rubric': 'data'}.get(kind)
        if required_content and required_content not in data:
            self.error(f'{kind} {ident} missing {required_content} field', location, ValueError())
        self.seen.add(key)
        if context:
            data['collection_context'] = context
        path = f'source/{key}.json'
        self.write_json(path, data)
        self.source(key, path, location, f'API {kind} design evidence; analyze API evidence before browser escalation')
        self.objects[key] = data
        pub = data.get('published')
        state = 'published' if pub is True else 'unpublished' if pub is False else 'unknown'
        self.inventory.append({'id': key, 'location': safe_url(location), 'view': 'API content/metadata',
                               'publication_state': state, 'status': 'inspected', 'source_ids': [key]})
        if kind not in ('question', 'rubric', 'settings'):
            self.browser_checks.append({'id': key, 'location': safe_url(location), 'status': 'pending',
                                        'reason': 'Verify from API/local evidence first; use browser only for an unresolved rendered, interaction, or learner-access question'})
        for field in ('syllabus_body', 'body', 'description', 'message', 'instructions', 'question_text'):
            if isinstance(data.get(field), str):
                html = f'source/{key}-{field}.html'
                (self.root / html).write_text(data[field])
                self.source(f'{key}-{field}', html, location, f'Original API HTML field {field}; not executed')
                parser = HTMLInventory()
                parser.feed(data[field])
                for resource in parser.resources:
                    target = urljoin(location, resource['target'])
                    if urlsplit(target).scheme not in ('http', 'https'):
                        continue
                    target = safe_url(target)
                    token = (key, resource['tag'], target)
                    if token in self.link_seen:
                        continue
                    self.link_seen.add(token)
                    resource.update(target=target, source_id=key, status='pending')
                    self.browser_checks.append({'id': f'linked-{len(self.link_seen)}', 'location': target,
                                                'reason': f"Inspect linked {resource['tag']} resource using API/local evidence first; URL extraction is not validation", **resource})
        if kind == 'item' and data.get('type') in ('File', 'ExternalUrl', 'ExternalTool'):
            self.browser_checks.append({'id': key + '-resource', 'location': safe_url(data.get('external_url') or location),
                                        'status': 'pending', 'reason': f"Inspect module resource: {data['type']}"})
        return key

    def detail_collection(self, course, kind, list_method, detail_method, path, id_field='id', list_kwargs=None, detail_kwargs=None):
        location = self.location(path)
        for obj in self.iterate(kind, location, lambda: getattr(course, list_method)(**(list_kwargs or {}))):
            ident = getattr(obj, id_field, None)
            if ident is None:
                self.error(f'{kind} identity', location, ValueError())
                continue
            obj_location = self.location(f'{path}/{ident}')
            lookup_id = int(ident) if kind == 'new_quiz' else ident
            detail = self.read(f'{kind} detail {ident}', obj_location,
                               lambda: getattr(course, detail_method)(lookup_id, **(detail_kwargs or {}))) if detail_method else obj
            self.save(detail if detail is not None else obj, kind, ident, obj_location)
            if kind == 'quiz' and detail is not None:
                for question in self.iterate(f'quiz-{ident}-questions', obj_location,
                                            lambda: detail.get_questions()):
                    self.save(question, 'question', f'{ident}-{question.id}', obj_location,
                              {'quiz_id': ident})

    def run(self):
        home = self.location('')
        course = self.read('course identity and syllabus', home, lambda: self.canvas.get_course(self.course_id, include=['syllabus_body']))
        if course is None:
            return self.checkpoint(final=True)
        self.course_ok = True
        self.name = getattr(course, 'name', f'Course {self.course_id}')
        self.save(course, 'course', self.course_id, home)
        settings = self.read('course settings', home, course.get_settings)
        if settings is not None:
            self.save(settings, 'settings', self.course_id, home)
        # A front page need not exist when home is modules, syllabus, etc.
        if getattr(course, 'default_view', None) == 'wiki':
            front = self.read('front page', self.location('pages/front_page'), course.show_front_page)
            if front is not None:
                self.save(front, 'page', getattr(front, 'page_id', 'front'), self.location(f"pages/{getattr(front, 'url', 'front_page')}"))
        for tab in self.iterate('tabs', home, course.get_tabs):
            self.save(tab, 'tab', tab.id, getattr(tab, 'html_url', home))
        for module in self.iterate('modules', self.location('modules'), course.get_modules):
            self.save(module, 'module', module.id, self.location(f'modules/{module.id}'))
            for item in self.iterate(f'module-{module.id}-items', self.location(f'modules/{module.id}'),
                                     lambda: module.get_module_items(include=['content_details'])):
                self.save(item, 'item', item.id, getattr(item, 'html_url', self.location(f'modules/items/{item.id}')),
                          {'module_id': module.id, 'module_published': getattr(module, 'published', None)})
            expected = getattr(module, 'items_count', None)
            observed = self.counts[f'module-{module.id}-items']['enumerated']
            if isinstance(expected, int) and expected != observed:
                self.error(f'module {module.id} item count mismatch: expected {expected}, observed {observed}',
                           self.location(f'modules/{module.id}'), ValueError())
        specs = [
            ('page', 'get_pages', 'get_page', 'pages', 'url', None, None),
            ('assignment', 'get_assignments', 'get_assignment', 'assignments', 'id', None, None),
            ('discussion', 'get_discussion_topics', 'get_discussion_topic', 'discussion_topics', 'id', None, None),
            ('quiz', 'get_quizzes', 'get_quiz', 'quizzes', 'id', None, None),
            ('rubric', 'get_rubrics', 'get_rubric', 'rubrics', 'id', None, {'include': ['associations']}),
            ('file', 'get_files', None, 'files', 'id', None, None),
            ('new_quiz', 'get_new_quizzes', 'get_new_quiz', 'assignments', 'id', None, None),
        ]
        for spec in specs:
            self.detail_collection(course, *spec)
        self.file_reviews = classify_files(self.objects, self.browser_checks, self.base_url, self.course_id)
        self.write_readable()
        return self.checkpoint(final=True)

    def write_readable(self):
        lines = [f'# {self.name} — API evidence index', '', 'Original HTML/JSON are authoritative; this text index loses layout and semantics.', '']
        for key, data in self.objects.items():
            lines += [f'## {key}: {data.get("title") or data.get("name") or data.get("display_name") or "Metadata"}',
                      f'Source: source/{key}.json', '']
            for field in ('syllabus_body', 'body', 'description', 'message', 'instructions', 'question_text'):
                if isinstance(data.get(field), str):
                    parser = HTMLInventory()
                    parser.feed(data[field])
                    lines += [' '.join(parser.text), '']
        (self.root / 'course.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course-id', required=True, type=int)
    parser.add_argument('--output-root', type=Path, default=Path('/tmp/canvas-tools/course-review'))
    parser.add_argument('--mode', choices=['pre_launch', 'published_view'], default='pre_launch')
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.course_id <= 0:
        parser.error('course-id must be positive')
    try:
        from canvasapi import Canvas
        if args.env_file:
            from dotenv import load_dotenv
            if not args.env_file.is_file():
                parser.error('env-file does not exist')
            load_dotenv(args.env_file, override=False)
    except ImportError:
        parser.error('Install the skill requirements.txt in your Python environment first')
    base, token = os.getenv('CANVAS_BASE_URL', '').strip().rstrip('/'), os.getenv('CANVAS_API_TOKEN', '').strip()
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.path not in ('', '/') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error('CANVAS_BASE_URL must be an HTTPS institution origin, without /api/v1 or credentials')
    if not token:
        parser.error('Set CANVAS_API_TOKEN in the environment or explicit --env-file')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    root = args.output_root.expanduser().resolve() / str(args.course_id) / run_id
    collector = Collector(Canvas(base, token), args.course_id, root, base, args.mode)
    try:
        status = collector.run()
    except KeyboardInterrupt:
        collector.error('collection interrupted', base, KeyboardInterrupt())
        status = collector.checkpoint(final=True)
    except Exception as exc:
        collector.error('collection interrupted by unexpected error', base, exc)
        status = collector.checkpoint(final=True)
    collection = json.loads((root / 'collection.json').read_text())
    collection['canvasapi_version'] = importlib.metadata.version('canvasapi')
    collector.write_json('collection.json', collection)
    print(json.dumps({'status': status, 'run_directory': str(root), 'error_count': len(collector.errors)}))
    return 0 if status == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
