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

    def test_named_report_is_safe_stable_and_matches_canonical_output(self):
        self.m['course'] = {'id': '28805', 'name': 'A different course title',
                            'course_code': 'MASTER_BTHT_3023_ONL / Section A'}
        # Keep the fixture narrative's required course-name match.
        self.m['course']['name'] = 'Fixture Course'
        stem = v.report_stem(self.m)
        self.assertEqual('28805-MASTER_BTHT_3023_ONL_Section_A_review_1791900000', stem)
        self.m['snapshot_at'] = '2026-10-13T10:00:00-04:00'
        self.assertEqual(stem, v.report_stem(self.m))
        self.m['follow_up'] = {'updated_at': '2026-10-14T14:00:00+00:00'}
        self.assertNotEqual(stem, v.report_stem(self.m))
        (self.root / 'manifest.json').write_text(json.dumps(self.m))
        (self.root / 'review.json').write_text(json.dumps(self.r))
        command = [sys.executable, str(SCRIPT), str(self.root)]
        result = subprocess.run(command + ['--render'], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout)
        named = self.root / (v.report_stem(self.m) + '.md')
        self.assertEqual((self.root / 'review.md').read_bytes(), named.read_bytes())
        named.write_text('outdated copy')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(named.name, result.stdout)

    def test_conversational_overview_and_navigation_preserve_coverage(self):
        narrative = (self.root / 'narrative.md').read_text().split('\n\n', 1)[1]
        narrative = narrative.replace('For accessible media,', '1. **Accessible media.**')
        narrative = narrative.replace('introduction video.', 'introduction video. [CU 21](#cu-21)', 1)
        self.r['narrative']['format'] = 'report_overview'
        self.r['narrative']['coverage'][0]['passage'] = '1. **Accessible media.** add captions to the introduction video.'
        (self.root / 'narrative.md').write_text(narrative)
        self.assertEqual([], self.errors())
        report = v.render(self.m, self.r, narrative)
        self.assertIn(narrative.strip(), report)
        self.assertIn('[CU 21](#cu-21)', report)
        self.assertIn('<a id="cu-21"></a>', report)
        self.assertLess(report.index('## Faculty overview'), report.index('## Detailed design findings'))
        self.assertNotIn('Subject:', report)
        self.assertNotIn('[ ]', report)
        self.assertNotIn('## Revision checklist', report)
        self.r['narrative']['format'] = 'unsupported'
        self.assertIn('invalid narrative format', self.errors())

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
        self.assertIn('Faculty overview', report)
        self.assertNotIn('## Source register', report)
        self.assertNotIn('## Coverage inventory', report)
        self.assertNotIn('sources: s1', report)
        appendix = (self.root / 'evidence-register.md').read_text()
        self.assertIn('s1: source.html', appendix)
        self.assertIn('### Criterion 21', appendix)
        self.assertNotIn('## Revision checklist', report)
        self.assertNotIn('Subject:', report)
        self.assertIn('| 21 |', report)
        self.assertLess(report.index('Review note:'), report.index('## Faculty overview'))
        self.assertLess(report.index('## Faculty overview'), report.index('## 1. COURSE INFORMATION'))
        self.assertLess(report.index('## Mechanical grammar and spelling'), report.index('## Scope and limitations'))
        self.assertEqual(1, report.count('## Faculty overview'))
        self.assertEqual(42, sum(line.startswith('| ') and line.split('|')[1].strip().isdigit() for line in report.splitlines()))
        self.assertEqual(0, run().returncode)
        (self.root / 'review.md').write_text(report + 'tampered')
        self.assertNotEqual(0, run().returncode)

    def test_table_actions_are_complete_without_duplicate_checklist(self):
        for cid, rating in [(20, 'Major Revision'), (12, 'Moderate Revision'), (17, 'Minor Revision')]:
            c = next(x for x in self.r['criteria'] if x['id'] == cid)
            c.update(rating=rating, action_plan=f'Repair criterion {cid}.')
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        self.assertNotIn('## Revision checklist', report)
        self.assertNotIn('[ ]', report)
        for cid in (20, 12, 17):
            row = next(line for line in report.splitlines() if line.startswith(f'| {cid} |'))
            self.assertIn(f'Repair criterion {cid}.', row)
            self.assertEqual(1, report.count(f'Repair criterion {cid}.'))
        self.assertEqual(42, sum(line.startswith('| ') and line.split('|')[1].strip().isdigit()
                                 for line in report.splitlines()))
        appendix = v.render_evidence(self.m, self.r, {'checks': [{'id': 'q1', 'status': 'blocked',
                    'verification_method': 'browser', 'verification_scope': 'Provider access restricted.', 'source_ids': ['s1']}]})
        self.assertIn('q1: blocked; method: browser', appendix)
        self.assertIn('Provider access restricted.', appendix)

    def test_canvas_action_links_render_once_in_table(self):
        url = 'https://canvas.example.edu/courses/fixture/pages/media%7Cintro'
        self.m['sources'][0]['location'] = url
        c = next(x for x in self.r['criteria'] if x['id'] == 21)
        c['action_links'] = [{'label': 'Introduction [video]', 'url': url, 'source_id': 's1'}]
        self.assertEqual([], self.errors())
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        destination = '[Introduction \\[video\\]](' + url + ')'
        row = next(line for line in report.splitlines() if line.startswith('| 21 |'))
        self.assertIn('Related Canvas: ' + destination, row)
        self.assertEqual(1, report.count(destination))
        # Equivalent percent-encoding and a section anchor still reference the inspected source.
        c['action_links'][0]['url'] = url.replace('%7C', '|') + '#captions'
        self.assertEqual([], self.errors())
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        self.assertIn(url + '#captions', report)

    def test_action_links_reject_unregistered_or_wrong_course_destinations(self):
        url = 'https://canvas.example.edu/courses/fixture/pages/media'
        self.m['sources'][0]['location'] = url
        c = next(x for x in self.r['criteria'] if x['id'] == 21)
        valid = {'label': 'Introduction video', 'url': url, 'source_id': 's1'}
        for changes in ({'source_id': 'unknown'}, {'url': 'javascript:alert(1)'},
                        {'url': url.replace('/fixture/', '/fixture2/')},
                        {'url': url.replace('/media', '/guessed')}, {'label': ''},
                        {'source_id': []}, {'url': None}):
            with self.subTest(changes=changes):
                c['action_links'] = [{**valid, **changes}]
                self.assertTrue(self.errors())
        # Even a registered source in a similarly named course cannot pass the course boundary.
        wrong_course = url.replace('/fixture/', '/fixture2/')
        self.m['sources'][0]['location'] = wrong_course
        c['action_links'] = [{**valid, 'url': wrong_course}]
        self.assertTrue(self.errors())
        for malformed in ('link', [None]):
            c['action_links'] = malformed
            self.assertTrue(self.errors())
        # Existing export/historical records need no invented Canvas destination.
        c.pop('action_links')
        self.assertEqual([], self.errors())

    def test_specific_actions_stay_paired_with_their_own_links(self):
        first = 'https://canvas.example.edu/courses/fixture/pages/intro'
        second = 'https://canvas.example.edu/courses/fixture/pages/followup'
        self.m['sources'][0]['location'] = first
        self.m['sources'].append({'id': 's2', 'location': second, 'description': 'Second affected page'})
        c = next(x for x in self.r['criteria'] if x['id'] == 21)
        c['source_ids'].append('s2')
        c['action_links'] = [
            {'action': 'Add captions & verify <playback>.', 'label': 'Introduction', 'url': first, 'source_id': 's1'},
            {'action': 'Correct the transcript.', 'label': 'Follow-up', 'url': second, 'source_id': 's2'},
        ]
        self.assertEqual([], self.errors())
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        row = next(line for line in report.splitlines() if line.startswith('| 21 |'))
        self.assertIn('<ul><li>Add captions &amp; verify &lt;playback&gt;. — <a href="' + first + '">Introduction</a></li>', row)
        self.assertIn('<li>Correct the transcript. — <a href="' + second + '">Follow-up</a></li></ul>', row)
        self.assertNotIn('Related Canvas:', row)
        self.assertEqual(1, report.count('Add captions &amp; verify &lt;playback&gt;.'))
        self.assertEqual(1, report.count('Correct the transcript.'))
        for action in ('', None):
            c['action_links'][1]['action'] = action
            self.assertTrue(self.errors())
        c['action_links'][1].pop('action')
        self.assertTrue(self.errors())

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

    def test_lower_levels_complete_without_blind_confirmation(self):
        for level in ('api_content', 'api_browser'):
            with self.subTest(level=level):
                self.r.update(review_level=level, level_selection='user_selected')
                # Unresolved behavioral evidence is not a failure of the scoped review.
                self.r['criteria'][0].update(rating=None, evidence_status='not_verified',
                    verification_step='Verify interface behavior in the browser.',
                    uncertainty='Browser evidence is not available within this review.')
                self.r['limitations'] = ['Interface behavior remains unverified.']
                self.assertEqual([], self.errors())
                report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
                self.assertIn(v.LEVELS[level], report)
                self.assertNotIn('Independent blind assessment completed', report)
        self.assertIn('Independent blind assessment was outside', report)

    def test_master_placeholder_is_present_with_preparation_reminder(self):
        self.m['course_type'] = 'master_blueprint'
        c = next(x for x in self.r['criteria'] if x['id'] == 30)
        c.update(evidence='Instructor welcome template explicitly requests a biography before publication.',
                 template_placeholder={'scope': 'Instructor biography and welcome page',
                                       'reminder': 'Instructor: add your biography and publish the welcome page before opening.'})
        self.assertEqual([], self.errors())
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        row = next(line for line in report.splitlines() if line.startswith('| 30 |'))
        self.assertIn('| Present |', row)
        self.assertIn(c['template_placeholder']['reminder'], row)
        reminders = report.split('## Instructor preparation reminders')[1].split('## Mechanical grammar')[0]
        self.assertIn('CU 30:', reminders)
        self.assertNotIn('## Revision checklist', report)

    def test_master_placeholder_does_not_override_other_deficiencies(self):
        self.m['course_type'] = 'master_blueprint'
        c = next(x for x in self.r['criteria'] if x['id'] == 21)
        c['template_placeholder'] = {'scope': 'Personalized welcome introduction',
                                     'reminder': 'Instructor: personalize the welcome introduction before opening.'}
        self.assertEqual([], self.errors())
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        row = next(line for line in report.splitlines() if line.startswith('| 21 |'))
        self.assertIn('| Major Revision |', row)
        self.assertIn(c['template_placeholder']['reminder'], report)

    def test_template_exception_requires_confirmed_scope_and_reminder(self):
        c = self.r['criteria'][0]
        c['template_placeholder'] = {'scope': 'Contact fields', 'reminder': 'Complete contact fields before opening.'}
        self.assertIn('CU 1: template placeholder requires master_blueprint course type', self.errors())
        self.m['course_type'] = 'master_blueprint'
        self.assertEqual([], self.errors())
        c['template_placeholder']['reminder'] = ''
        self.assertIn('CU 1: template placeholder needs scope and instructor reminder', self.errors())
        c['template_placeholder']['reminder'] = 'Complete contact fields before opening.'
        c.update(rating=None, evidence_status='not_verified', deferred=True,
                 verification_step='Complete the contact fields.', uncertainty='Pending assignment.')
        self.assertIn('CU 1: intentional template placeholder must not be deferred', self.errors())

    def test_preparation_links_are_distinct_from_revision_destinations(self):
        self.m['course_type'] = 'master_blueprint'
        revision_url = 'https://canvas.example.edu/courses/fixture/pages/revision'
        preparation_url = 'https://canvas.example.edu/courses/fixture/quizzes/7'
        self.m['sources'][0]['location'] = revision_url
        self.m['sources'].append({'id': 's2', 'location': preparation_url, 'description': 'Saved quiz draft'})
        c = next(x for x in self.r['criteria'] if x['id'] == 21)
        c['source_ids'].append('s2')
        c['action_links'] = [{'label': 'Revision page', 'url': revision_url, 'source_id': 's1'}]
        c['template_placeholder'] = {'scope': 'Quiz draft finalization', 'reminder': 'Finalize the saved quiz draft.',
                                     'action_links': [{'label': 'Syllabus Quiz', 'url': preparation_url, 'source_id': 's2'}]}
        self.assertEqual([], self.errors())
        report = v.render(self.m, self.r, (self.root / 'narrative.md').read_text())
        preparation = report.split('## Instructor preparation reminders')[1].split('## Mechanical grammar')[0]
        self.assertIn(preparation_url, preparation)
        self.assertNotIn(revision_url, preparation)
        c['template_placeholder']['action_links'][0]['source_id'] = 'unknown'
        self.assertTrue(self.errors())

    def test_level_selection_and_default_are_validated(self):
        self.r.update(review_level='api_browser', level_selection='default')
        self.assertEqual([], self.errors())
        self.r['review_level'] = 'api_content'
        self.assertIn('default review level must be api_browser', self.errors())
        self.r['level_selection'] = 'user_selected'
        self.assertEqual([], self.errors())
        self.r['review_level'] = 'invented'
        self.assertIn('invalid review level', self.errors())
        self.r['review_level'] = 'api_browser'
        del self.r['level_selection']
        self.assertIn('invalid level selection', self.errors())
        del self.r['review_level']
        self.r['level_selection'] = 'default'
        self.assertIn('level selection requires review level', self.errors())

    def test_level_three_requires_reconciled_blind_confirmation_for_completion(self):
        self.r.update(review_level='api_browser_blind', level_selection='user_selected')
        self.assertIn('level 3 requires confirmation metadata', self.errors())
        self.r['confirmation'] = {'status': 'pending', 'blind': False,
                                  'limitations': ['Independent assessment is unfinished.']}
        self.assertIn('completed report has incomplete independent confirmation', self.errors())
        self.r.update(status='partial', limitations=['Independent assessment is unfinished.'])
        text = (self.root / 'narrative.md').read_text()
        (self.root / 'narrative.md').write_text(text.replace('The module sequence', 'This partial review finds the module sequence'))
        self.r['narrative']['strengths_excerpt'] = 'the module sequence provides a clear starting point.'
        self.assertEqual([], self.errors())
        folder = self.root / 'confirmation'
        folder.mkdir()
        confirmation = self.r['confirmation']
        for key, filename in [('input_index', 'input-index.json'), ('independent_assessment', 'independent.json'),
                              ('reconciliation', 'reconciliation.md'), ('policy_audit', 'policy-audit.md')]:
            (folder / filename).write_text('Saved evidence for synthetic confirmation')
            confirmation[key] = f'confirmation/{filename}'
        confirmation.update(status='reconciled', blind=True, limitations=[])
        self.r.update(status='completed', limitations=[])
        self.assertEqual([], self.errors())

    def test_lower_levels_cannot_claim_independent_confirmation(self):
        self.r.update(review_level='api_browser', level_selection='user_selected',
                      confirmation={'status': 'pending', 'blind': False, 'limitations': ['Pending.']})
        self.assertIn('levels 1–2 exclude independent confirmation; use level 3', self.errors())

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
        self.assertNotIn('Faculty overview', v.render(self.m, self.r, ''))

    def test_rubric_ids_match_preserved_authority(self):
        self.assertEqual(v.IDS, {i for _, items in v.rubric() for i, _ in items})
        self.assertEqual(7, len(v.rubric()))


if __name__ == '__main__':
    unittest.main()
