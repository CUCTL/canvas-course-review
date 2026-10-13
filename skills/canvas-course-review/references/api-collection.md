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

All remote operations use read-only canvasapi model methods. The collector reads course identity/syllabus, course settings, front page when home uses a wiki page, navigation tabs, modules/items, all accessible pages, assignments, discussion prompts, Classic Quizzes/questions, course rubric details and associations, file metadata, and New Quiz instructions/settings. Iteration follows pagination and preserves previously read records if a later page fails. Page bodies are fetched individually; raw HTML fields retain styling, iframe sources, image alternatives, and table markup. Draft and unlinked content remain inventoried even in published_view mode: use API availability/prerequisite/publication evidence first; inspect configured resource/navigation behavior only where design evidence is insufficient; do not require actual enrolled-learner access or evaluate delivered teaching.

Only selected course-design fields are stored. SDK internals, enrollment details, submissions, discussion replies/participants, rubric assessments, grades, and quiz access-code values are excluded. Exceptions retain operation/location/type, not server response bodies. File download URLs are omitted, and credential/signature query parameters are removed from indexed locations while resource identifiers are retained; original authorized course HTML is preserved as evidence and must remain local.

File contents are not automatically downloaded. All file metadata stays inventoried; `manifest.file_reviews` distinguishes instructional documents, linked resources, contextual images/media, instructor references, unlinked document candidates, and unreferenced assets. Module/HTML references determine initial scope; filenames and publication status alone do not. Inspect instructional DOCX, PDF, PPTX, spreadsheets, and other instructional documents (including external documents) by downloading Canvas files with canvasapi and inspecting them locally first; use the browser only for evidence unavailable through API/local inspection. Check images/media in context instead of opening every decorative asset. Confirm unlinked documents and instructor references before deciding whether content review is needed. Instructor guides governing teaching/assessment remain relevant. Unknown question-bank references can change initial scope; update classification as evidence becomes available. Duplicate document-content queue entries are consolidated under the file record; exclusion is a scope decision, never proof of accessibility or learner access. External tools/URLs, media, and captions need browser checks when API/local evidence cannot establish the relevant behavior or quality. The supported canvasapi 3.6.0 model exposes New Quiz metadata/settings but no New Quiz item-list method: inspect question content in the browser at levels 2–3. At level 1, disclose the unsupported content coverage and leave affected conclusions unverified. Individual due-date overrides/accommodations, student records, and proof of teaching delivery are outside collection scope. Missing permissions/SDK support are reported, not silently treated as empty collections. Missing expected content fields also produce an explicit gap.

## Outputs and continuation

- manifest.json: report-compatible source register, hashes, API inventory, scope, and limitations.
- collection.json: separate collection status (`running`, `completed`, `partial`, `failed`), counts per paginated collection, sanitized failures, timestamps, and SDK version on CLI completion.
- source/: selected source JSON and original HTML fields; do not execute saved HTML.
- course.json: combined design evidence; course.md: plain-text index, not rendered fidelity.
- browser-checks.json: verification candidates with source IDs or locations and preferred_method=api_first. The legacy filename is retained; this is not a mandatory browser-visit queue or proof that links/accessibility were verified.

A nonzero CLI exit with partial status still leaves usable artifacts. A failed course-identity read cannot become successful collection. Incremental checkpoints preserve inventories at collection/module boundaries; a hard process termination can leave status running and unindexed files. Do not call that snapshot complete. An interrupted run can be inspected for usable evidence, but retry extraction into a new directory; automated resume/retry is not implemented. The SDK controls HTTP behavior; this helper has no separate retry/timeout service.

After collection, inspect errors and triage browser-checks.json against the available API/local evidence. Verify from that evidence first, retrieve missing details through supported canvasapi methods, and, at levels 2–3, use the browser only for a named unresolved question. At level 1, exclude browser-only work from the execution queue with a selected-level scope reason; preserve the unanswered question and affected criterion as unverified rather than calling it verified or absent. See [review levels](review-levels.md). Record verification_method, verification_scope, and source IDs on verified checks; record a browser_trigger when browser evidence is necessary. Add distinct local-document/browser sources with provenance and artifact hashes. Preserve pending/blocked questions; exclude redundant browser visits with a reason rather than calling them browser-verified. Preserve API provenance rather than rewriting sources to imply browser inspection. Use pending verification for criteria that still need technical or institutional confirmation. Use [the report contract](report-contract.md) for review.json/narrative.md and run the report validator. Collection counts prove only the scope returned to the authorized API account, not access for every learner or semantic review completion.

## Implementation references

SDK methods and pagination were checked against [canvasapi Course documentation](https://canvasapi.readthedocs.io/en/stable/course-ref.html) and the installed 3.6.0 source. New Quiz fields were checked against [Instructure New Quizzes documentation](https://developerdocs.instructure.com/services/canvas/resources/new_quizzes). Tests exercise actual canvasapi models/pagination through a strict GET-only fixture transport; no live course is needed.

## Verification routing

| Question | Preferred evidence | Browser trigger |
| --- | --- | --- |
| Course policies, objectives, activities, assessment alignment, grammar | API text/HTML, module relationships, rubric/quiz details | Missing content or ambiguity requiring the displayed view |
| Dates, points, time limits, publication, prerequisites | API settings/metadata | Configured visibility/resource behavior or preview UI needs clarification; no real learner session required |
| Instructional DOCX/PDF/PPTX/spreadsheets | canvasapi file download; local content/structure inspection and targeted rendering | External document or interaction unavailable locally |
| Headings, alt attributes, table markup, declared styles | Raw API HTML/document structure | Visual meaning, computed contrast, keyboard behavior, or layout needs confirmation |
| Video/captions and external tools | Available metadata/transcripts for content and declared caption availability | Playback, caption accuracy/synchronization, authentication, or tool interaction |
| New Quiz question content unavailable through supported SDK | Available API instructions/settings | Build view needed for questions/banks |

A check may be partly answered by the API while its visual/access question remains pending. Keep those scopes separate. Reuse existing evidence and group necessary browser checks by page/resource; avoid repeatedly opening pages merely to confirm already-inspected API text. No minimum number of browser visits is required. Evidence sufficiency against the rubric determines coverage, not the tool used.

## Continuation and scanner guidance

- Compare live content with the API snapshot before relying on old findings. Refresh changed evidence without replacing prior sources; record snapshot times. Reconcile all affected ratings, actions, uncertainty, grammar, and narrative coverage. Remove obsolete claims about placeholders, unavailable playback, or uninspected banks when new evidence resolves them.
- Treat the queue as candidates with bounded questions. Resolve duplicates and generic staff/admin/navigation resources against course scope; do not launch unrelated integrations or inspect grades/rosters just to clear a queue. Every in-scope pending candidate needs an attempted verification and an evidence-backed disposition before delivery. Report verified/excluded/blocked counts separately from criterion ratings and report status. Do not bulk mark unresolved work blocked to make the pending count zero.
- For New Quizzes, inspect Build content and all required source-bank pages when the supported SDK cannot return items. Wait for actual question rows, verify pagination/coverage, and distinguish inspected prompts from fully inspected choices/feedback. Expand details without adding/editing items; dismiss configuration panes without saving. Instructor preview may demonstrate controls/timer behavior, but is not a real learner-access or accommodation test. Submit no attempt.
- Recheck transient playback failures through the authenticated browser before treating them as persistent. Verify caption activation and visible text rather than relying on a CC icon. Caption presence, sampled accuracy, complete synchronization, visual description, and continuous flashing analysis are distinct scopes. If full media cannot be inspected through supported tools, retain that specific blocker rather than claiming complete accessibility.
- Canvas’s course accessibility scanner can supply diagnostic evidence. Run a scan or inspect its results without applying fixes, changing content, or marking issues resolved. Review flagged locations against original HTML and computed rendered styles; automated counts are not confirmed deficiencies. A scanner may misinterpret a named CSS color even when the displayed foreground/background pass measured contrast. Retain the discrepancy and measurements. Separate instructor-only template flags from learner-facing findings.
- A catalog landing page or resolver is not full-text access. Record the actual provider restriction and next step; do not bypass security challenges, accept new terms, purchase access, or replace unavailable reading evidence with assumptions.

The main report should help faculty act. Put only revision actions, concise findings, and material limitations there; preserve detailed traceability and verification dispositions in the separate evidence register and internal JSON.

All verification remains within course design. No delivery analytics, actual feedback/response histories, learner participation, grade outcomes, attendance or individual accommodation implementation are collected or rated. Unavailable live learner access is recorded as outside scope; it is not a design-review blocker.
