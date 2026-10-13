"""Classify file content checks while retaining the complete API inventory."""
import re
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit
from html.parser import HTMLParser

DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.docm', '.odt', '.rtf', '.ppt', '.pptx', '.pptm', '.odp',
                       '.xls', '.xlsx', '.xlsm', '.ods', '.csv', '.tsv', '.txt', '.md', '.html', '.htm'}
MEDIA_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp4', '.mov', '.webm', '.mp3', '.wav', '.m4a'}
DOCUMENT_MIMES = ('application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument',
                  'application/vnd.ms-', 'application/vnd.oasis.opendocument', 'application/rtf', 'text/')


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src') and value:
                self.targets.append(value)


def normalized(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


def classify_files(objects, checks, base_url, course_id):
    """Return file roles/check states and update duplicate queue checks in place.

    Inclusion uses actual module/HTML references, not filename guesses or draft
    publication state. Unlinked documents require scope confirmation before opening.
    """
    files = {str(v['id']): (k, v) for k, v in objects.items() if k.startswith('file-')}
    instructor_modules = {v['id'] for k, v in objects.items() if k.startswith('module-')
                          and ('instructors-only' in normalized(v.get('name', '')) or 'do-not-publish' in normalized(v.get('name', '')))}
    instructor_pages = set()
    for key, obj in objects.items():
        if key.startswith('item-') and obj.get('collection_context', {}).get('module_id') in instructor_modules:
            if obj.get('page_url'):
                instructor_pages.add(normalized(obj['page_url']))
    refs = {fid: [] for fid in files}
    def instructor_source(key, obj):
        return (key.startswith('item-') and obj.get('collection_context', {}).get('module_id') in instructor_modules
                or key.startswith('page-') and (normalized(obj.get('url', '')) in instructor_pages
                                                or 'do-not-publish' in normalized(obj.get('title', ''))))
    def link_file(target):
        url = urlsplit(urljoin(base_url + '/', str(target)))
        if url.netloc != urlsplit(base_url).netloc:
            return None
        match = re.search(r'(?:/courses/(\d+))?/files/(\d+)(?:/|$)', url.path)
        if match and (not match[1] or match[1] == str(course_id)) and match[2] in files:
            return match[2]
        return None
    for key, obj in objects.items():
        faculty = bool(instructor_source(key, obj))
        if key.startswith('item-') and obj.get('type') == 'File' and str(obj.get('content_id')) in refs:
            refs[str(obj['content_id'])].append({'source_id': key, 'instructor_only': faculty})
        for field in ('syllabus_body', 'body', 'description', 'message', 'instructions', 'question_text'):
            if isinstance(obj.get(field), str):
                links = Links()
                links.feed(obj[field])
                for target in links.targets:
                    fid = link_file(target)
                    if fid:
                        ref = {'source_id': key, 'instructor_only': faculty}
                        if ref not in refs[fid]:
                            refs[fid].append(ref)
    roles = []
    for fid, (key, obj) in files.items():
        name = obj.get('display_name') or obj.get('filename') or fid
        ext = PurePosixPath(obj.get('filename') or name).suffix.lower()
        mime = str(obj.get('content-type', '')).lower()
        is_document = ext in DOCUMENT_EXTENSIONS or mime.startswith(DOCUMENT_MIMES)
        is_media = ext in MEDIA_EXTENSIONS or mime.startswith(('image/', 'video/', 'audio/'))
        faculty_only = bool(refs[fid]) and all(r['instructor_only'] for r in refs[fid])
        if refs[fid] and faculty_only:
            role, required, check_type = 'instructor_reference', False, 'scope_confirmation'
            reason = 'Referenced only in instructor-only material; inspect if it governs this course’s teaching/assessment plan, otherwise exclude from learner document checks.'
        elif refs[fid] and is_document:
            role, required, check_type = 'instructional_document', True, 'document_content'
            reason = 'Referenced by course learning/information content; inspect instructions, readability/accessibility, and applicable rubric evidence.'
        elif refs[fid] and is_media:
            role, required, check_type = 'contextual_image_or_media', False, 'contextual_accessibility'
            reason = 'Review meaning/alternatives or captions in the containing course page/activity; no duplicate standalone document-content check.'
        elif refs[fid]:
            role, required, check_type = 'linked_instructional_resource', True, 'resource_content'
            reason = 'Referenced in course learning content; establish instructional purpose and inspect using an appropriate safe viewer.'
        elif is_document:
            role, required, check_type = 'unlinked_document_candidate', False, 'scope_confirmation'
            reason = 'No module/HTML reference found in collected evidence; confirm instructional use before opening. Draft or unlinked status alone does not establish that a document is unused.'
        else:
            role, required, check_type = 'unreferenced_asset', False, 'inventory_only'
            reason = 'No instructional reference found in collected evidence; retained in inventory, excluded from standalone content checks. Reclassify if a later browser/bank read establishes use.'
        file_check = next((c for c in checks if c['id'] == key), None)
        if file_check and file_check.get('status') not in ('verified', 'blocked'):
            file_check['status'] = 'pending' if required or check_type == 'scope_confirmation' else 'excluded'
        status = file_check.get('status', 'pending' if required else 'excluded') if file_check else ('pending' if required or check_type=='scope_confirmation' else 'excluded')
        entry = {'source_id': key, 'file_id': fid, 'name': name, 'format': ext or mime or 'unknown',
                 'role': role, 'content_check_required': required, 'check_type': check_type,
                 'check_status': status, 'reason': reason, 'references': refs[fid]}
        roles.append(entry)
        for c in checks:
            target_fid = link_file(c.get('location', ''))
            module_item = objects.get(c['id'].removesuffix('-resource'), {})
            belongs = c['id'] == key or target_fid == fid or (module_item.get('type') == 'File' and str(module_item.get('content_id')) == fid)
            if belongs:
                c.update(file_id=fid, file_role=role, check_type=check_type, content_check_required=required,
                         scope_reason=reason, file_source_id=key)
                if c.get('status') not in ('verified', 'blocked'):
                    if c['id'] == key or not required and check_type != 'scope_confirmation':
                        # Linked images/media still receive contextual accessibility checks.
                        contextual = c.get('tag') in ('img', 'iframe', 'video', 'audio', 'source', 'track') and bool(refs[fid])
                        c['status'] = 'pending' if contextual or required or check_type == 'scope_confirmation' else 'excluded'
                    elif required:
                        c['status'] = 'excluded'
                        c['scope_reason'] = f'Consolidated document-content check under {key}; retain this reference for navigation/access context.'
        if file_check:
            entry['check_status'] = file_check['status']
    return roles
