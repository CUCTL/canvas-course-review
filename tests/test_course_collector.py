"""Exercise actual canvasapi models/pagination with a strict GET-only fake transport."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from canvasapi import Canvas

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/canvas-course-review/scripts/collect_course.py'
spec = importlib.util.spec_from_file_location('collector', SCRIPT)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
BASE = 'https://canvas.example.edu'


class Transport:
    base_url = BASE + '/api/v1/'
    new_quizzes_url = BASE + '/api/quiz/v1/'
    def __init__(self):
        self.calls, self.fail = [], set()
        self.routes = {
            ('courses/7', None): {'id': 7, 'name': 'Fixture Course', 'default_view': 'wiki',
                                 'syllabus_body': '<h2>Welcome</h2>', 'enrollments': [{'user_id': 999, 'grades': {'score': 50}}]},
            ('courses/7/settings', None): {'hide_final_grades': True},
            ('courses/7/front_page', None): {'page_id': 2, 'url': 'start', 'title': 'Start', 'body': '<p>Start here</p>', 'published': False},
            ('courses/7/tabs', None): [{'id': 'modules', 'label': 'Modules', 'html_url': BASE + '/courses/7/modules', 'hidden': False}],
            ('courses/7/modules', None): [{'id': 1, 'name': 'Draft module', 'published': False, 'items_count': 101},
                                         {'id': 2, 'name': 'Published module', 'published': True, 'items_count': 1}],
            ('courses/7/modules/1/items', None): [{'id': i, 'title': f'Page {i}', 'type': 'Page', 'page_url': f'p{i}', 'published': False} for i in range(1, 101)],
            ('courses/7/modules/1/items?page=2', None): [{'id': 101, 'title': 'External resource', 'type': 'ExternalUrl', 'external_url': 'https://outside.example/resource?token=secret'}],
            ('courses/7/modules/2/items', None): [{'id': 102, 'title': 'Document', 'type': 'File', 'content_id': 8}],
            ('courses/7/pages', None): [{'page_id': i, 'url': f'p{i}', 'title': f'Page {i}'} for i in range(1, 101)],
            ('courses/7/pages?page=2', None): [{'page_id': 101, 'url': 'p101', 'title': 'Unlinked page'}],
            ('courses/7/assignments', None): [{'id': 3, 'name': 'Assignment'}],
            ('courses/7/assignments/3', None): {'id': 3, 'name': 'Assignment', 'description': '<p>Analyze</p>',
                                             'rubric': [{'id': 'criterion', 'description': 'Evidence'}], 'rubric_settings': {'id': 9}, 'published': False,
                                             'submission': {'user_id': 999, 'grade': 'A'}},
            ('courses/7/discussion_topics', None): [{'id': 4, 'title': 'Discussion'}],
            ('courses/7/discussion_topics/4', None): {'id': 4, 'title': 'Discussion', 'message': '<p>Discuss</p>', 'participants': [{'id': 999}]},
            ('courses/7/quizzes', None): [{'id': 6, 'title': 'Classic quiz'}],
            ('courses/7/quizzes/6', None): {'id': 6, 'title': 'Classic quiz', 'description': '<p>Quiz</p>', 'time_limit': 20, 'access_code': 'secret'},
            ('courses/7/quizzes/6/questions', None): [{'id': 1, 'question_text': '<p>Why?</p>', 'answers': []}],
            ('courses/7/rubrics', None): [{'id': 9, 'title': 'Rubric summary'}],
            ('courses/7/rubrics/9', None): {'id': 9, 'title': 'Rubric', 'data': [{'id': 'criterion', 'description': 'Evidence'}],
                                         'associations': [{'id': 12, 'association_id': 3, 'association_type': 'Assignment', 'use_for_grading': True, 'assessor_name': 'Private'}]},
            ('courses/7/files', None): [{'id': 8, 'filename': 'handout.pdf', 'url': 'https://signed.example?token=secret', 'size': 10}],
            ('courses/7/quizzes', 'new_quizzes'): [{'id': '55', 'title': 'New quiz'}],
            ('courses/7/quizzes/55', 'new_quizzes'): {'id': '55', 'title': 'New quiz', 'instructions': '<p>Explain</p>',
                                                    'quiz_settings': {'has_time_limit': True, 'session_time_limit_in_seconds': 600, 'student_access_code': 'secret'}},
        }
        for i in range(1, 102):
            self.routes[(f'courses/7/pages/p{i}', None)] = {'page_id': i, 'url': f'p{i}', 'title': f'Page {i}', 'published': False,
                'body': '<h1 style="font-size:16px">Text</h1><table><th scope="col">Header</th></table><iframe src="https://media.example/embed"></iframe><img alt="Diagram" src="https://media.example/img.png">'}
    def request(self, method, endpoint, **kwargs):
        if method != 'GET':
            raise AssertionError('Mutation attempted')
        key = (endpoint, kwargs.get('_url'))
        self.calls.append(key)
        if endpoint in self.fail:
            raise RuntimeError('PRIVATE exception payload token=secret')
        data = copy.deepcopy(self.routes[key])
        links = {}
        if endpoint in ('courses/7/pages', 'courses/7/modules/1/items'):
            links = {'next': {'url': self.base_url + endpoint + '?page=2'}}
        return SimpleNamespace(json=lambda: data, links=links)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'run'
        self.transport = Transport()
        canvas = Canvas(BASE, 'unused-fixture-token')
        canvas._Canvas__requester = self.transport
        self.collector = c.Collector(canvas, 7, self.root, BASE)

    def test_paginated_drafts_details_and_no_private_records(self):
        self.assertEqual('completed', self.collector.run())
        manifest = json.loads((self.root / 'manifest.json').read_text())
        objects = json.loads((self.root / 'course.json').read_text())['objects']
        self.assertEqual(101, manifest['collection']['counts']['page']['enumerated'])
        self.assertEqual(101, manifest['collection']['counts']['module-1-items']['enumerated'])
        self.assertFalse(objects['module-1']['published'])
        self.assertFalse(objects['page-p101']['published'])
        self.assertIn('data', objects['rubric-9'])
        self.assertIn('rubric_settings', objects['assignment-3'])
        self.assertIn('question-6-1', objects)
        self.assertEqual(600, objects['new_quiz-55']['quiz_settings']['session_time_limit_in_seconds'])
        html = (self.root / 'source/page-p1-body.html').read_text()
        self.assertIn('scope="col"', html)
        self.assertIn('font-size:16px', html)
        checks = json.loads((self.root / 'browser-checks.json').read_text())['checks']
        self.assertTrue(any(x.get('tag') == 'iframe' for x in checks))
        self.assertTrue(any(x.get('tag') == 'img' and x.get('alt') == 'Diagram' for x in checks))
        combined = '\n'.join(p.read_text() for p in self.root.rglob('*') if p.is_file())
        for forbidden in ('user_id', 'assessor_name', 'student_access_code', 'token=secret', 'PRIVATE exception'):
            self.assertNotIn(forbidden, combined)
        for source in manifest['sources']:
            self.assertTrue((self.root / source['artifact']).is_file())

    def test_later_page_failure_keeps_earlier_evidence(self):
        self.transport.fail.add('courses/7/pages?page=2')
        self.assertEqual('partial', self.collector.run())
        self.assertIn('page-p100', self.collector.objects)
        self.assertNotIn('page-p101', self.collector.objects)
        self.assertEqual('partial', self.collector.counts['page']['status'])
        self.assertEqual(100, self.collector.counts['page']['enumerated'])
        self.assertTrue(any('page' == e['operation'] for e in self.collector.errors))

    def test_blocked_rubric_retains_summary_without_faking_detail(self):
        self.transport.fail.add('courses/7/rubrics/9')
        self.assertEqual('partial', self.collector.run())
        self.assertNotIn('data', self.collector.objects['rubric-9'])
        self.assertTrue(any(x['status'] == 'blocked' and 'rubric detail' in x['reason'] for x in self.collector.inventory))
        self.assertNotIn('PRIVATE', (self.root / 'collection.json').read_text())

    def test_failed_identity_and_unique_directory_boundary(self):
        self.transport.fail.add('courses/7')
        self.assertEqual('failed', self.collector.run())
        self.assertEqual('failed', json.loads((self.root / 'collection.json').read_text())['status'])
        self.assertNotEqual([], self.collector.errors)
        with self.assertRaises(FileExistsError):
            c.Collector(None, 7, self.root, BASE)

    def test_resource_identifiers_survive_credential_redaction(self):
        self.assertEqual('https://video.example/watch?v=abc', c.safe_url('https://video.example/watch?v=abc&token=secret'))
        self.assertEqual({'id': 3, 'external_tool_tag_attributes': None}, c.select({'id': 3, 'external_tool_tag_attributes': None}, 'assignment'))

    def test_missing_sdk_support_is_partial_not_empty_success(self):
        course = SimpleNamespace(id=7, name='Unsupported SDK fixture', default_view='modules',
                                 get_settings=lambda: {}, get_tabs=lambda: [], get_modules=lambda: [])
        self.collector.canvas = SimpleNamespace(get_course=lambda *a, **k: course)
        self.assertEqual('partial', self.collector.run())
        self.assertTrue(any(e['error_type'] == 'AttributeError' for e in self.collector.errors))


if __name__ == '__main__':
    unittest.main()
