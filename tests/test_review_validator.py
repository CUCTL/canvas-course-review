"""Synthetic contract tests; these fixtures are not real course assessments."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / '.agents/skills/canvas-course-review/scripts/validate_review.py'
spec = importlib.util.spec_from_file_location('validator', SCRIPT)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'source.html').write_text('<h1>Example source</h1>')
        self.m = {
            'schema_version': 1, 'course': {'id': 'fixture', 'name': 'Fixture Course'},
            'mode': 'supplied_export', 'scope': 'Synthetic fixture only',
            'snapshot_at': '2026-10-13T14:00:00+00:00', 'rubric_version': 'CUOCDR v0.9',
            'sources': [{'id': 's1', 'location': 'source.html', 'description': 'Synthetic source',
                         'artifact': 'source.html', 'sha256': hashlib.sha256((self.root / 'source.html').read_bytes()).hexdigest()}],
            'inventory': [{'id': 'i1', 'location': 'source.html', 'view': 'export',
                           'publication_state': 'unknown', 'status': 'inspected', 'source_ids': ['s1']}],
            'limitations': ['Synthetic validation fixture; not a substantive course review.'],
        }
        narrative = ('Subject: Review of Fixture Course\n\n'
                     'The module sequence provides a clear starting point.\n\n'
                     'For accessible media, add captions to the introduction video.\n\n'
                     'Next term, post a weekly objective summary. Use an exit ticket with explanatory feedback. '
                     'Schedule a discussion and summarize misconceptions.\n\n'
                     'Continue refining the course with institutional teaching support.\n')
        (self.root / 'narrative.md').write_text(narrative)
        self.r = {
            'schema_version': 1, 'status': 'completed',
            'stages': {k: 'completed' for k in ('design', 'grammar', 'narrative')},
            'limitations': [], 'grammar': [],
            'criteria': [{'id': i, 'rating': 'Present', 'evidence_status': 'verified',
                          'source_ids': ['s1'], 'evidence': 'Synthetic criterion evidence',
                          'action_plan': '', 'verification_step': '', 'uncertainty': '', 'deferred': False}
                         for i in sorted(v.IDS)],
            'narrative': {'file': 'narrative.md',
                          'coverage': [{'criterion_id': 21, 'passage': 'For accessible media, add captions to the introduction video.',
                                        'next_step': 'add captions to the introduction video.'}],
                          'teaching_tips': ['post a weekly objective summary.', 'Use an exit ticket with explanatory feedback.',
                                            'Schedule a discussion and summarize misconceptions.'],
                          'strengths_excerpt': 'The module sequence provides a clear starting point.',
                          'closing_excerpt': 'Continue refining the course with institutional teaching support.'},
        }
        c = next(c for c in self.r['criteria'] if c['id'] == 21)
        c.update(rating='Major Revision', action_plan='Add captions to the introduction video.')

    def errors(self):
        return v.validate(self.root, self.m, self.r)[0]

    def test_valid_render_and_consistency(self):
        self.assertEqual([], self.errors())
        for filename, obj in [('manifest.json', self.m), ('review.json', self.r)]:
            (self.root / filename).write_text(json.dumps(obj))
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(0, run('--render').returncode)
        report = (self.root / 'review.md').read_text()
        self.assertIn('Faculty-facing narrative draft', report)
        self.assertEqual(42, sum(line.startswith('| ') and line.split('|')[1].strip().isdigit() for line in report.splitlines()))
        self.assertEqual(0, run().returncode)
        (self.root / 'review.md').write_text(report + 'tampered')
        self.assertNotEqual(0, run().returncode)

    def test_missing_duplicate_or_invented_criterion(self):
        original = copy.deepcopy(self.r)
        for mutation in ('missing', 'duplicate', 'invented'):
            self.r = copy.deepcopy(original)
            if mutation == 'missing': self.r['criteria'].pop()
            elif mutation == 'duplicate': self.r['criteria'].append(self.r['criteria'][0])
            else: self.r['criteria'][0]['id'] = 25
            self.assertTrue(self.errors(), mutation)

    def test_evidence_and_revision_invariants(self):
        c = self.r['criteria'][0]
        c['source_ids'] = ['missing']
        self.assertTrue(self.errors())
        c['source_ids'] = ['s1']
        c['evidence_status'] = 'not_verified'
        self.assertTrue(self.errors())
        c.update(rating=None, verification_step='Inspect source', uncertainty='Source inaccessible')
        self.assertEqual([], self.errors())
        c.update(rating='Moderate Revision', evidence_status='verified', action_plan='')
        self.assertTrue(self.errors())

    def test_narrative_coverage_and_word_limit(self):
        self.r['narrative']['coverage'] = []
        self.assertTrue(self.errors())
        self.r['narrative']['coverage'] = [{'criterion_id': 21, 'passage': 'Invented passage', 'next_step': 'Invented'}]
        self.assertTrue(self.errors())
        (self.root / 'narrative.md').write_text('Subject: Fixture Course\n' + 'word ' * 601)
        self.assertTrue(self.errors())

    def test_source_integrity_and_path_boundary(self):
        (self.root / 'source.html').write_text('changed')
        self.assertTrue(self.errors())
        self.m['sources'][0]['artifact'] = '../outside.html'
        self.assertTrue(self.errors())

    def test_partial_and_failed_do_not_masquerade_as_success(self):
        self.r['stages']['design'] = 'failed'
        self.assertTrue(self.errors())
        self.r['status'] = 'partial'
        self.r['stages']['design'] = 'partial'
        self.r['limitations'] = ['Inspection incomplete']
        self.assertTrue(self.errors())  # narrative lacks disclosure
        with (self.root / 'narrative.md').open('a') as f:
            f.write('\nThis draft is based on a partial review.\n')
        self.assertEqual([], self.errors())
        self.r.update(status='failed', criteria=[], narrative=None)
        self.r['stages'].update(design='failed', grammar='not_started', narrative='not_started')
        self.assertEqual([], self.errors())
        self.assertNotIn('Faculty-facing narrative draft', v.render(self.m, self.r, ''))

    def test_rubric_ids_match_preserved_authority(self):
        self.assertEqual(v.IDS, {i for _, items in v.rubric() for i, _ in items})
        self.assertEqual(7, len(v.rubric()))


if __name__ == '__main__':
    unittest.main()
