# API extraction and browser verification

## Portable setup

The complete shareable skill is this `canvas-course-review` folder, including SKILL.md, agents/, references/, scripts/, and requirements.txt. Copy that folder into the recipient's Codex skills directory, or install it from its repository path. No absolute developer-machine paths or separate Canvas skill are required.

Use Python 3.10+ and install dependencies in a virtual environment:

```bash
python3 -m venv /tmp/canvas-course-review-venv
/tmp/canvas-course-review-venv/bin/python -m pip install -r <skill-path>/requirements.txt
```

Supply `CANVAS_BASE_URL` as the HTTPS institution origin (no /api/v1) and `CANVAS_API_TOKEN` through environment variables or an ignored .env file. Use an account/token authorized to read the intended course. Do not put live credentials in prompts, source control, command arguments, or shared artifacts. Environment values take precedence over an explicitly loaded .env file. The collector does not search unrelated projects for credentials or require an OpenAI key.

```bash
/tmp/canvas-course-review-venv/bin/python <skill-path>/scripts/collect_course.py \
  --course-id 12345 --env-file /absolute/path/to/.env --mode pre_launch
```

The default output root is `/tmp/canvas-tools/course-review`; each invocation creates `<course-id>/<UTC-timestamp>-<unique-suffix>/` without overwriting an existing run. `--output-root` selects a durable location when requested. Keep course snapshots local and separate from the shareable skill. After review, preserve the requested reports in an appropriate durable output location if the snapshot is temporary.

## Collection scope

All remote operations use read-only canvasapi model methods. The collector reads course identity/syllabus, course settings, front page when home uses a wiki page, navigation tabs, modules/items, all accessible pages, assignments, discussion prompts, Classic Quizzes/questions, course rubric details and associations, file metadata, and New Quiz instructions/settings. Iteration follows pagination and preserves previously read records if a later page fails. Page bodies are fetched individually; raw HTML fields retain styling, iframe sources, image alternatives, and table markup. Draft and unlinked content remain inventoried even in published_view mode: resolve actual learner scope in the browser before rating.

Only selected course-design fields are stored. SDK internals, enrollment details, submissions, discussion replies/participants, rubric assessments, grades, and quiz access-code values are excluded. Exceptions retain operation/location/type, not server response bodies. File download URLs are omitted, and credential/signature query parameters are removed from indexed locations while resource identifiers are retained; original authorized course HTML is preserved as evidence and must remain local.

File contents are not automatically downloaded. All file metadata stays inventoried; `manifest.file_reviews` distinguishes instructional documents, linked resources, contextual images/media, instructor references, unlinked document candidates, and unreferenced assets. Module/HTML references determine initial scope; filenames and publication status alone do not. Inspect instructional DOCX, PDF, PPTX, spreadsheets, and other instructional documents (including external documents) through the browser or an authorized document workflow. Check images/media in context instead of opening every decorative asset. Confirm unlinked documents and instructor references before deciding whether content review is needed. Instructor guides governing teaching/assessment remain relevant. Unknown question-bank references can change initial scope; update classification as evidence becomes available. Duplicate document-content queue entries are consolidated under the file record; exclusion is a scope decision, never proof of accessibility or learner access. External tools/URLs, media, and captions require browser checks. The supported canvasapi 3.6.0 model exposes New Quiz metadata/settings but no New Quiz item-list method: inspect question content in the browser. Individual due-date overrides/accommodations, student records, and proof of teaching delivery are outside collection scope. Missing permissions/SDK support are reported, not silently treated as empty collections. Missing expected content fields also produce an explicit gap.

## Outputs and continuation

- manifest.json: report-compatible source register, hashes, API inventory, scope, and limitations.
- collection.json: separate collection status (`running`, `completed`, `partial`, `failed`), counts per paginated collection, sanitized failures, timestamps, and SDK version on CLI completion.
- source/: selected source JSON and original HTML fields; do not execute saved HTML.
- course.json: combined design evidence; course.md: plain-text index, not rendered fidelity.
- browser-checks.json: pending content/resource/failed-read checks with source IDs or locations. This is a queue, not proof that links or accessibility were verified.

A nonzero CLI exit with partial status still leaves usable artifacts. A failed course-identity read cannot become successful collection. Incremental checkpoints preserve inventories at collection/module boundaries; a hard process termination can leave status running and unindexed files. Do not call that snapshot complete. An interrupted run can be inspected for usable evidence, but retry extraction into a new directory; automated resume/retry is not implemented. The SDK controls HTTP behavior; this helper has no separate retry/timeout service.

After collection, inspect errors and browser-checks.json, perform browser verification, add distinct browser source records with evidence/artifact hashes, and record completed/blocked/excluded checks. Preserve API provenance rather than rewriting sources to imply browser inspection. Use pending verification for criteria that still need technical or institutional confirmation. Use [the report contract](report-contract.md) for review.json/narrative.md and run the report validator. Collection counts prove only the scope returned to the authorized API account, not access for every learner or semantic review completion.

## Implementation references

SDK methods and pagination were checked against [canvasapi Course documentation](https://canvasapi.readthedocs.io/en/stable/course-ref.html) and the installed 3.6.0 source. New Quiz fields were checked against [Instructure New Quizzes documentation](https://developerdocs.instructure.com/services/canvas/resources/new_quizzes). Tests exercise actual canvasapi models/pagination through a strict GET-only fixture transport; no live course is needed.
