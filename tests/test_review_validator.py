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

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/canvas-course-review/scripts/validate_review.py'
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

    def test_file_scope_contract_and_rendering(self):
        self.m['file_reviews'] = [{'source_id': 's1', 'file_id': '8', 'name': 'reading.pdf', 'format': '.pdf',
                                  'role': 'instructional_document', 'content_check_required': True,
                                  'check_type': 'document_content', 'check_status': 'pending',
                                  'reason': 'Required reading.', 'references': [{'source_id': 's1', 'instructor_only': False}]}]
        self.assertEqual([], self.errors())
        rendered = v.render_evidence(self.m, self.r)
        self.assertIn('File review checklist', rendered)
        self.assertIn('reading.pdf / s1', rendered)
        self.m['file_reviews'][0]['check_status'] = 'inspected'
        self.assertIn('invalid file check status', self.errors())

    def test_excluded_files_hidden_from_all_report_listings(self):
        self.m['sources'].append({'id': 'file-9', 'location': 'unused-banner.png', 'description': 'File metadata'})
        self.m['inventory'].append({'id': 'file-9', 'location': 'unused-banner.png', 'view': 'API metadata',
                                    'publication_state': 'unknown', 'status': 'inspected', 'source_ids': ['file-9']})
        self.m['file_reviews'] = [{'source_id': 'file-9', 'file_id': '9', 'name': 'unused-banner.png', 'format': '.png',
                                  'role': 'unreferenced_asset', 'content_check_required': False, 'check_type': 'inventory_only',
                                  'check_status': 'excluded', 'reason': 'No instructional reference.', 'references': []}]
        self.assertEqual([], self.errors())
        before = copy.deepcopy(self.m)
        report = v.render_evidence(self.m, self.r)
        self.assertNotIn('unused-banner.png', report)
        self.assertNotIn('file-9', report)
        self.assertNotIn('File review checklist', report)
        self.assertIn('s1: source.html', report)
        self.assertEqual(before, self.m)
        self.m['file_reviews'][0]['check_status'] = 'pending'
        report = v.render_evidence(self.m, self.r)
        self.assertIn('unused-banner.png', report)

    def test_valid_render_and_consistency(self):
        self.assertEqual([], self.errors())
        for filename, obj in [('manifest.json', self.m), ('review.json', self.r)]:
            (self.root / filename).write_text(json.dumps(obj))
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(0, run('--render').returncode)
        report = (self.root / 'review.md').read_text()
        self.assertIn('Faculty-facing narrative draft', report)
        self.assertNotIn('## Source register', report)
        self.assertNotIn('## Coverage inventory', report)
        self.assertNotIn('sources: s1', report)
        appendix = (self.root / 'evidence-register.md').read_text()
        self.assertIn('s1: source.html', appendix)
        self.assertIn('### Criterion 21', appendix)
        checklist = report.split('## Revision checklist')[1].split('## Mechanical grammar')[0]
        self.assertIn('CU 21 (Major Revision)', checklist)
        self.assertNotIn('CU 1 (Present)', checklist)
        self.assertLess(report.index('Review note:'), report.index('## Faculty-facing narrative draft'))
        self.assertLess(report.index('## Faculty-facing narrative draft'), report.index('## 1. COURSE INFORMATION'))
        self.assertLess(report.index('## Mechanical grammar and spelling'), report.index('## Scope and limitations'))
        self.assertEqual(1, report.count('## Faculty-facing narrative draft'))
        self.assertEqual(42, sum(line.startswith('| ') and line.split('|')[1].strip().isdigit() for line in report.splitlines()))
        self.assertEqual(0, run().returncode)
        (self.root / 'review.md').write_text(report + 'tampered')
        self.assertNotEqual(0, run().returncode)

    def test_revision_checklist_prioritizes_accessibility_and_omits_passes(self):
        for cid, rating in [(20, 'Major Revision'), (12, 'Moderate Revision'), (17, 'Minor Revision')]:
            c = next(x for x in self.r['criteria'] if x['id'] == cid)
            c.update(rating=rating, action_plan=f'Repair criterion {cid}.')
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        checklist = report.split('## Revision checklist')[1].split('## Mechanical grammar')[0]
        self.assertLess(checklist.index('CU 20'), checklist.index('CU 17'))
        self.assertLess(checklist.index('CU 17'), checklist.index('CU 12'))
        self.assertNotIn('CU 1 (Present)', checklist)
        appendix = v.render_evidence(self.m, self.r, {'checks': [{'id': 'q1', 'status': 'blocked',
                    'verification_method': 'browser', 'verification_scope': 'Provider access restricted.', 'source_ids': ['s1']}]})
        self.assertIn('q1: blocked; method: browser', appendix)
        self.assertIn('Provider access restricted.', appendix)

    def test_evidence_register_consistency_is_checked(self):
        for filename, obj in [('manifest.json', self.m), ('review.json', self.r)]:
            (self.root / filename).write_text(json.dumps(obj))
        command = [sys.executable, str(SCRIPT), str(self.root)]
        self.assertEqual(0, subprocess.run(command + ['--render'], capture_output=True).returncode)
        (self.root / 'evidence-register.md').write_text('Altered supporting evidence')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('evidence-register.md differs', (self.root / 'validation.json').read_text())

    def test_confirmation_cannot_claim_blind_completion_without_artifacts(self):
        self.r['confirmation'] = {'status': 'reconciled', 'blind': False, 'limitations': [],
                                  'input_index': 'confirmation/input-index.json',
                                  'independent_assessment': 'confirmation/independent.json',
                                  'reconciliation': 'confirmation/reconciliation.md',
                                  'policy_audit': 'confirmation/policy-audit.md'}
        self.assertTrue(self.errors())
        folder = self.root / 'confirmation'
        folder.mkdir()
        for filename in ('input-index.json', 'independent.json', 'reconciliation.md', 'policy-audit.md'):
            (folder / filename).write_text('Saved assessment evidence')
        self.r['confirmation']['blind'] = True
        self.assertEqual([], self.errors())
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        self.assertIn('Independent blind assessment completed', report)
        self.r['confirmation'].update(status='unavailable', blind=False, limitations=['Reviewer unavailable.'])
        self.assertIn('completed report has incomplete independent confirmation', self.errors())
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        self.assertNotIn('Independent blind assessment completed', report)

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
