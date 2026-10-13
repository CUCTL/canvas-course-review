"""File review scope follows instructional references, not extension alone."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/canvas-course-review/scripts'))
from file_scope import classify_files

BASE = 'https://canvas.example.edu'

class FileScopeTests(unittest.TestCase):
    def fixture(self):
        objects = {f'file-{i}': {'id': i, 'filename': name} for i, name in enumerate(
            ['reading.pdf', 'worksheet.docx', 'slides.pptx', 'draft.docx', 'banner.png', 'diagram.png', 'staff.docx'], 1)}
        objects.update({
            'module-1': {'id': 1, 'name': 'Week 1', 'published': False},
            'module-2': {'id': 2, 'name': 'Instructors Only'},
            'item-1': {'id': 1, 'type': 'File', 'content_id': 1, 'collection_context': {'module_id': 1}},
            'item-7': {'id': 7, 'type': 'File', 'content_id': 7, 'collection_context': {'module_id': 2}},
            'page-start': {'body': '<a href="/courses/7/files/2/download">Worksheet</a><a href="/files/3">Slides</a><img src="/courses/7/files/6/preview">'},
        })
        checks = [{'id': f'file-{i}', 'status': 'pending'} for i in range(1, 8)]
        checks += [{'id': 'item-1-resource', 'status': 'pending'},
                   {'id': 'diagram-link', 'location': BASE + '/files/6/preview', 'tag': 'img', 'status': 'pending'}]
        return objects, checks

    def test_instructional_scope_and_context(self):
        objects, checks = self.fixture()
        roles = {x['file_id']: x for x in classify_files(objects, checks, BASE, 7)}
        self.assertEqual(len(roles), 7)
        for i in ('1', '2', '3'):
            self.assertTrue(roles[i]['content_check_required'])
            self.assertEqual(roles[i]['role'], 'instructional_document')
        self.assertEqual(roles['4']['check_type'], 'scope_confirmation')
        self.assertEqual(roles['4']['check_status'], 'pending')
        self.assertEqual(roles['5']['check_status'], 'excluded')
        self.assertEqual(roles['6']['check_type'], 'contextual_accessibility')
        self.assertEqual(roles['7']['role'], 'instructor_reference')
        by_id = {x['id']: x for x in checks}
        self.assertEqual(by_id['diagram-link']['status'], 'pending')
        self.assertEqual(by_id['item-1-resource']['status'], 'excluded')

    def test_preserves_evidence_and_rejects_unrelated_links(self):
        objects, checks = self.fixture()
        checks[0]['status'] = 'verified'
        checks[1]['status'] = 'blocked'
        objects['page-start']['body'] = '<a href="https://other.example/files/3">Foreign host</a><a href="/courses/8/files/3">Foreign course</a>'
        roles = {x['file_id']: x for x in classify_files(objects, checks, BASE, 7)}
        self.assertEqual(roles['1']['check_status'], 'verified')
        self.assertEqual(roles['2']['check_status'], 'blocked')
        self.assertEqual(roles['3']['references'], [])
        self.assertEqual(roles['3']['role'], 'unlinked_document_candidate')

if __name__ == '__main__':
    unittest.main()
