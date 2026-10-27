"""Offline transfer invariants; no credentials or live service calls."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/canvas-course-review/scripts/kuali_draft.py'
spec = importlib.util.spec_from_file_location('kuali_draft', SCRIPT)
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)
validation_spec = importlib.util.spec_from_file_location('transfer_validation', SCRIPT.with_name('validate_review.py'))
v = importlib.util.module_from_spec(validation_spec)
validation_spec.loader.exec_module(v)


class KualiTransferTests(unittest.TestCase):
    def setUp(self):
        schema = [{'formKey': 'data.course', 'label': 'Course'},
                  {'formKey': 'data.course.id', 'label': 'Course - ID'}]
        gadgets, records = [], []
        for cid in sorted(k.IDS):
            schema += [{'formKey': f'data.r{cid}', 'label': f'#{cid} Criterion'},
                       {'formKey': f'data.r{cid}.label', 'label': 'Derived label'},
                       {'formKey': f'data.a{cid}', 'label': 'Action Plan'}]
            gadgets.append({'formKey': f'r{cid}', 'details': {'options': [
                {'key': 'p', 'lbl': 'Present'}, {'key': 'm', 'lbl': 'Minor Revision'},
                {'key': 'na', 'lbl': 'NA'}]}})
            records.append({'id': cid, 'rating': 'Present', 'evidence': 'NOT AN ACTION',
                            'template_placeholder': {'reminder': 'DO NOT COPY'},
                            'action_plan': '', 'action_links': []})
        schema.append({'formKey': 'data.narrative', 'label': 'Narrative Summary of Review'})
        self.response = {'data': {'document': {'id': 'doc-one', 'status': 'saved',
            'data': {'course': {'id': 'COURSE 100', 'label': 'Test Course'}, 'unrelated': 'keep'},
            'form': {'id': 'version-one', 'schema': schema, 'template': {'children': gadgets}}}}}
        self.review = {'criteria': records}

    def prepare(self, **kwargs):
        return k.prepare(self.review, 'Design feedback <safe>.', self.response, 'COURSE 100', **kwargs)

    def write_approved_cli_fixture(self, root, narrative):
        """Synthetic style approval used only to exercise the CLI boundary."""
        manifest={'course':{'id':'1','name':'Synthetic Course'},'limitations':[]}
        self.review.update(schema_version=2,status='completed',limitations=[],grammar=[],narrative={'coverage':[]})
        digest=v.writing_review_hash(v.writing_review_input(manifest,self.review,narrative))
        report={'status':'passed','reviewer':'synthetic-style-reviewer','content_sha256':digest,'issues':[]}
        (root/'assessment.json').write_text(json.dumps(report))
        self.review['writing_review']={key:report[key] for key in ('status','reviewer','content_sha256')}
        self.review['writing_review'].update(report='assessment.json',limitations=[])
        for name,data in (('manifest.json',manifest),('review.json',self.review),('state.json',self.response)):
            (root/name).write_text(json.dumps(data))
        (root/'narrative.md').write_text(narrative)

    def test_actions_only_and_real_option_mapping(self):
        c = self.review['criteria'][0]
        c.update(rating='Minor Revision', action_links=[{'action': 'Revise directions.', 'url': 'https://example.test/task'}])
        self.review['criteria'][1].update(rating='N/A',
            na_reason='This optional training has no graded assignments.')
        self.review['criteria'][2].update(rating=None, verification_step='Check the caption accuracy.')
        plan = self.prepare()
        self.assertEqual(plan['payload']['r1'], {'id': 'm', 'label': 'Minor Revision'})
        self.assertEqual(plan['payload']['a1'], 'Revise directions.\nhttps://example.test/task')
        self.assertEqual(plan['payload']['r2']['label'], 'NA')
        self.assertEqual(plan['payload']['a2'], 'This optional training has no graded assignments.')
        self.assertNotIn('r3', plan['desired'])
        self.assertNotIn('course', plan['payload'])
        self.assertNotIn('NOT AN ACTION', str(plan['payload']))
        self.assertIn('&lt;safe&gt;', plan['payload']['narrative'])

    def test_pending_tasks_transfer_without_rating_or_reviewer_metadata(self):
        criterion = self.review['criteria'][0]
        criterion.update(rating=None, verification_step='Check that the captions match the speech.',
                         uncertainty='INTERNAL UNCERTAINTY')
        plan = self.prepare()
        self.assertTrue(plan['ready'])
        self.assertEqual([1], plan['unresolved_criteria'])
        self.assertNotIn('r1', plan['payload'])
        self.assertEqual('Check that the captions match the speech.', plan['payload']['a1'])
        self.assertNotIn('INTERNAL UNCERTAINTY', str(plan['payload']))

    def test_legacy_links_retain_action_plan_and_all_destinations(self):
        self.review['criteria'][0].update(rating='Minor Revision',
            action_plan='Make the assignment and guide instructions agree.',
            action_links=[{'label': 'Assignment', 'url': 'https://canvas.example.test/courses/1/assignments/2'},
                          {'label': 'Instructor guide', 'url': 'https://example.sharepoint.com/guide.docx'}])
        text = self.prepare()['payload']['a1']
        self.assertEqual(1, text.count('Make the assignment and guide instructions agree.'))
        self.assertIn('https://canvas.example.test/courses/1/assignments/2', text)
        self.assertIn('https://example.sharepoint.com/guide.docx', text)

    def test_verification_tasks_are_retained_without_exact_duplicates(self):
        task = 'Check that the captions match the speech.'
        self.review['criteria'][0].update(rating=None, verification_step=task,
            action_links=[{'action': task, 'url': 'https://example.test/video'}])
        self.assertEqual(1, self.prepare()['payload']['a1'].count(task))
        self.review['criteria'][0]['verification_step'] = 'Ask CTL to check keyboard access.'
        text = self.prepare()['payload']['a1']
        self.assertIn(task, text)
        self.assertIn('Ask CTL to check keyboard access.', text)

    def test_missing_tasks_and_reviewer_metadata_are_rejected(self):
        criterion = self.review['criteria'][0]
        criterion.update(rating='Minor Revision', action_links=[{'url': 'https://example.test/task'}])
        with self.assertRaises(ValueError):
            self.prepare()
        criterion.update(rating=None, verification_step='Verification: reviewer details')
        with self.assertRaises(ValueError):
            self.prepare()
        criterion.update(action_links=[{'action': None}])
        with self.assertRaises(ValueError):
            self.prepare()

    def test_conflicts_require_exact_replacement(self):
        self.response['data']['document']['data']['narrative'] = 'Human edit'
        self.assertFalse(self.prepare()['ready'])
        plan = self.prepare(replace_fields=['narrative'])
        self.assertTrue(plan['ready'])
        self.assertEqual(plan['baseline']['narrative'], 'Human edit')
        with self.assertRaises(ValueError):
            self.prepare(replace_fields=['course'])

    def test_schema_drift_course_and_status_rejected(self):
        for alteration in ('duplicate', 'missing', 'course', 'status', 'option'):
            with self.subTest(alteration=alteration):
                original = copy.deepcopy(self.response)
                doc = self.response['data']['document']
                if alteration == 'duplicate':
                    doc['form']['schema'].append({'formKey': 'data.other', 'label': '#1 Duplicate'})
                elif alteration == 'missing':
                    doc['form']['schema'] = [x for x in doc['form']['schema'] if x['formKey'] != 'data.a1']
                elif alteration == 'course':
                    doc['data']['course']['id'] = 'WRONG'
                elif alteration == 'status':
                    doc['status'] = 'submitted'
                else:
                    doc['form']['template']['children'][0]['details']['options'] = []
                with self.assertRaises(ValueError):
                    self.prepare()
                self.response = original

    def test_null_never_erases_human_rating(self):
        self.review['criteria'][0].update(rating=None, verification_step='Check the course introduction.')
        self.response['data']['document']['data']['r1'] = {'id': 'p', 'label': 'Present'}
        plan = self.prepare()
        self.assertFalse(plan['ready'])
        self.assertNotIn('r1', plan['payload'])

    def test_readback_hidden_fields_and_collateral_change(self):
        plan = self.prepare()
        readback = copy.deepcopy(self.response)
        data = readback['data']['document']['data']
        data.update(plan['payload'])
        # Hidden empty action fields can be omitted by the server.
        for cid in k.IDS:
            data.pop(f'a{cid}', None)
        self.assertTrue(k.verify(plan, readback)['api_verified'])
        data['unrelated'] = 'changed'
        self.assertFalse(k.verify(plan, readback)['api_verified'])
        data['unrelated'] = 'keep'
        data['r1'] = {'id': 'm', 'label': 'Minor Revision'}
        self.assertIn('r1', k.verify(plan, readback)['target_mismatches'])
        readback['data']['document']['form']['id'] = 'new-version'
        with self.assertRaises(ValueError):
            k.verify(plan, readback)

    def test_cached_schema_and_data_only_readback(self):
        cached = k.read(k.SCHEMA_CACHE)
        mapping, _, _ = k.map_form(cached)
        self.assertEqual(set(mapping), k.IDS)
        plan = self.prepare()
        readback = copy.deepcopy(self.response)
        readback['data']['document']['data'].update(plan['payload'])
        del readback['data']['document']['form']
        self.assertTrue(k.verify(plan, readback)['api_verified'])

    def test_existing_empty_actions_may_be_omitted_or_null(self):
        self.response['data']['document']['data'].update(a1='', a2='')
        plan = self.prepare()
        for empty_value in ('omitted', None, ''):
            with self.subTest(empty_value=empty_value):
                readback = copy.deepcopy(self.response)
                data = readback['data']['document']['data']
                data.update(plan['payload'])
                if empty_value == 'omitted':
                    data.pop('a1')
                    data.pop('a2')
                else:
                    data.update(a1=empty_value, a2=empty_value)
                self.assertTrue(k.verify(plan, readback)['api_verified'])

    def test_na_explanation_supports_legacy_records_and_rejects_missing_comments(self):
        criterion = self.review['criteria'][1]
        criterion.update(rating='N/A', evidence='No authored data tables are used in this course.')
        self.assertEqual(criterion['evidence'], self.prepare()['payload']['a2'])
        criterion['evidence'] = ''
        with self.assertRaisesRegex(ValueError, 'N/A requires an explanation'):
            self.prepare()
        criterion['evidence'] = 'Legacy explanation.'
        for invalid in ('', None, 17):
            with self.subTest(invalid=invalid):
                criterion['na_reason'] = invalid
                with self.assertRaisesRegex(ValueError, 'N/A requires an explanation'):
                    self.prepare()

    def test_na_comments_cannot_be_normalized_to_empty_on_readback(self):
        self.review['criteria'][1].update(rating='N/A',
            na_reason='This optional training has no graded assignments.')
        plan = self.prepare()
        for value in ('kept', 'omitted', None, ''):
            with self.subTest(value=value):
                readback = copy.deepcopy(self.response)
                data = readback['data']['document']['data']
                data.update(plan['payload'])
                if value == 'omitted':
                    data.pop('a2')
                elif value != 'kept':
                    data['a2'] = value
                self.assertEqual(value == 'kept', k.verify(plan, readback)['api_verified'])

    def test_empty_normalization_does_not_hide_lost_tasks_or_unrelated_changes(self):
        self.review['criteria'][0].update(rating='Minor Revision', action_plan='Revise the prompt.')
        self.response['data']['document']['data'].update(a1='Revise the prompt.', unrelated_empty='')
        plan = self.prepare()
        readback = copy.deepcopy(self.response)
        data = readback['data']['document']['data']
        data.update(plan['payload'])
        data.pop('a1')
        result = k.verify(plan, readback)
        self.assertFalse(result['api_verified'])
        self.assertIn('a1', result['target_mismatches'])
        self.assertIn('a1', result['unrequested_changes'])
        data['a1'] = 'Revise the prompt.'
        data.pop('unrelated_empty')
        result = k.verify(plan, readback)
        self.assertFalse(result['api_verified'])
        self.assertEqual(['unrelated_empty'], result['unrequested_changes'])

    def test_cli_prepares_and_verifies_a_local_draft_transfer(self):
        self.review['criteria'][0].update(rating=None, verification_step='Check caption accuracy.')
        narrative = ('Thank you for the clear course structure.\n\n'
                     'Next term, summarize weekly goals. Show an example before the assignment. '
                     'Invite questions in the existing discussion.\n\nPlease let us know if you need help.')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_approved_cli_fixture(root,narrative)
            out = root / 'transfer'
            command = [sys.executable, str(SCRIPT)]
            result = subprocess.run(command + ['prepare', str(root), '--state', str(root / 'state.json'),
                '--course-code', 'COURSE 100', '--out', str(out)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            plan = json.loads((out / 'plan.json').read_text())
            payload = json.loads((out / 'variables.json').read_text())['data']
            self.assertEqual('Check caption accuracy.', payload['a1'])
            self.assertIn('summarize weekly goals', payload['narrative'])
            self.assertNotIn('r1', payload)
            self.assertIn('updateDocument', (out / 'mutation.graphql').read_text())
            readback = copy.deepcopy(self.response)
            readback['data']['document']['data'].update(payload)
            for cid in k.IDS - {1}:
                readback['data']['document']['data'].pop(f'a{cid}', None)
            (root / 'readback.json').write_text(json.dumps(readback))
            result = subprocess.run(command + ['verify', '--plan', str(out / 'plan.json'),
                '--readback', str(root / 'readback.json')], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(json.loads(result.stdout)['api_verified'])
            self.assertEqual(self.response['data']['document']['data'], plan['baseline'])

    def test_cli_refuses_legacy_missing_or_stale_style_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.write_approved_cli_fixture(root,'Saved faculty narrative.')
            command=[sys.executable,str(SCRIPT),'prepare',str(root),'--state',str(root/'state.json'),
                     '--course-code','COURSE 100','--out',str(root/'transfer')]
            good=copy.deepcopy(self.review)
            for mutation in ('legacy','missing','stale','unavailable','null','invalid'):
                with self.subTest(mutation=mutation):
                    changed=copy.deepcopy(good)
                    if mutation=='legacy':changed['schema_version']=1
                    elif mutation=='missing':changed.pop('writing_review')
                    elif mutation=='stale':changed['criteria'][0]['action_plan']='New wording.'
                    elif mutation=='unavailable':changed['writing_review']={'status':'unavailable','limitations':['Reviewer unavailable.']}
                    elif mutation=='null':changed['writing_review']=None
                    else:changed['writing_review']='invalid'
                    (root/'review.json').write_text(json.dumps(changed))
                    result=subprocess.run(command,capture_output=True,text=True)
                    self.assertNotEqual(0,result.returncode)
                    self.assertNotIn('Traceback',result.stderr)
                    self.assertFalse((root/'transfer').exists())


if __name__ == '__main__':
    unittest.main()
