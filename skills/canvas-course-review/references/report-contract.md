# Report contract v1

All files use UTF-8. The helper uses Python's standard library. Write manifest.json and review.json as JSON objects and narrative.md as the complete faculty-facing draft (not fenced Markdown). Treat paths as relative to the run directory, without `..` or absolute paths. Do not store secrets or student records.

## manifest.json

Required fields:

- schema_version: `1`
- course: object with nonempty string `id` and `name` (export-only bundles may use a clearly identified local bundle ID).
- mode: `pre_launch`, `published_view`, or `supplied_export`.
- scope: nonempty description of reviewed scope, view, draft treatment, and any sampling.
- snapshot_at: timezone-aware ISO 8601 timestamp.
- rubric_version: `CUOCDR v0.9`.
- sources: array of objects, each with a unique string `id`, nonempty `location` (URL/object location), and `description`. Optional `artifact` identifies a saved local file; optional `sha256` verifies that artifact. Preserve original source files when supplied.
- inventory: array of objects with unique `id`, nonempty `location`, `view`, `publication_state`, and `status` (`inspected`, `blocked`, `excluded`). For inspected entries, `source_ids` must reference at least one source. Blocked/excluded entries require `reason`. Include out-of-scope entries and unlinked resources when they affect coverage; unavailable publication metadata can be recorded as `unknown`.
- limitations: array of nonempty strings, possibly empty.

Optional `manifest.course_type` is `master_blueprint` or `course_offering`. It records confirmed template purpose, not merely unpublished status. Historical manifests without it remain readable.

## review.json

Required fields:

- schema_version: `1`.
- status: `completed`, `partial`, or `failed`.
- stages: object with `design`, `grammar`, and `narrative` outcomes, each `completed`, `partial`, `failed`, or `not_started`.
- limitations: array of nonempty strings, possibly empty. Required to be nonempty for partial/failed status.
- criteria: array of all 42 records for completed/partial reports, with no duplicate or invented IDs. A failed run may retain a subset, but cannot render a successful report.
- grammar: array of objects with nonempty `source_id`, `issue`, and `suggested_fix`. An empty list means no confirmed mechanical issues only when that stage completed; partial stages must describe limits.

Each criterion record has `id` (integer), `rating` (allowed label or null), `evidence_status` (policy enum), `source_ids` (source IDs), `evidence` (concise text), `action_plan`, `verification_step`, `uncertainty`, and `deferred` (boolean). Empty strings are permitted for action/verification/uncertainty only where irrelevant. N/A uses not_applicable; null uses not_verified. Present uses verified. Revision findings use verified or scoped not_evidenced. All records need sources describing observation or search scope, including blocked checks. Null records need a verification step and uncertainty; revision records need an action plan. Explain N/A in evidence. A legacy deferred record is null and explains the placeholder and completion step. For new master/blueprint reviews, intentional instructor placeholders instead use Present, verified, deferred=false, and optional `template_placeholder: {"scope": "Instructor welcome page awaiting personalization", "reminder": "Instructor: add your biography and contact details and publish this page before the course opens."}`. Both strings are nonempty and require manifest.course_type=master_blueprint and registered evidence. Present verifies the scaffold, not completion of instructor content. If the same criterion has an unrelated observed deficiency or evidence gap, preserve that revision/null rating and keep the reminder separate; the exception does not override the rest of the criterion. See [template guidance](template-placeholders.md).

For completed/partial reports, `narrative` is an object with:

- file: `narrative.md`.
- coverage: array of objects with `criterion_id`, `passage`, and `next_step`, exactly one for each Moderate/Major criterion. Both text excerpts occur verbatim in the draft; the next step occurs inside the mapped passage. A paragraph may cover multiple criteria, each mapped separately.
- teaching_tips: array of at least three distinct verbatim excerpts from the draft, each describing a practical next-term teaching suggestion.
- strengths_excerpt: verbatim excerpt from the opening paragraph.
- closing_excerpt: verbatim excerpt from the closing paragraph.

The first nonblank line of narrative.md starts `Subject:` and includes the exact course name. Count all whitespace-separated words in the file, including subject/greeting/sign-off. Maximum 600. For partial reports the draft explicitly says `partial review`. The helper validates excerpts but cannot establish their meaning, theme grouping, priority, faculty tone, supportive closing, or substantive coverage. Check these manually against the ten narrative requirements.

Template reminders appear beside the criterion’s action/verification text and in a separate instructor preparation checklist, including available registered Canvas action links. They are not revision findings and do not enter Moderate/Major narrative coverage solely because instructor completion is pending. Preserve them in end-user PDF exports alongside substantive actions and limitations. Historical reports render unchanged when the optional fields are absent.

## Related Canvas action links

Each criterion may include `action_links`: an array of `{ "action": "Restore the safe sandbox-testing procedure.", "label": "1.3 Sandbox", "url": "https://canvas.example.edu/courses/123/pages/sandbox", "source_id": "page-sandbox" }`. The source ID must occur in that criterion’s `source_ids`, and its registered source location must match the HTTPS URL (encoded page names and optional fragments are supported). Use the exact reviewed course, not a different course, guessed resource, or external how-to article. Register any newly inspected destination before linking it.

For new live-course reports, supply at least one relevant destination for each revision/actionable verification step when available; use more than one only when needed to locate separate work. For new reports, give each link an `action` containing the specific task at that destination. Split multi-location recommendations into action/link pairs; avoid a shared paragraph followed by a detached group of links. The renderer displays the pairs as a list in the action/verification table cell and a nested list under each revision criterion. Each pair must stand on its own and, together, retain every material step from the action plan. If any link has `action`, all links on that criterion must have a nonempty action. Legacy entries without `action` retain their previous rendering. Use concise labels naming the page, activity, settings section, or question bank. A link locates the work; it does not prove learner access or authorize editing. Exports and unavailable destinations may omit links with a location/limitation in the action text. Historical reports without this optional field remain valid and render unchanged.

## Review level

For new runs, record `review.review_level` as `api_content` (level 1), `api_browser` (level 2; recommended), or `api_browser_blind` (level 3), and `review.level_selection` as `user_selected` after an explicit user choice. Level is separate from manifest.mode, which describes pre-launch/published/export scope. Historical reports without level metadata remain readable and are not relabeled automatically. The validator retains the legacy `default` selection value for compatibility with earlier artifacts (level 2 only); do not use it for new runs. New runs must wait for an explicit selection without a timeout fallback.

Display the selected level near course identity and state whether independent blind assessment is included. Level 1 reports explicitly say browser verification was outside scope; preserve unverified browser-dependent conclusions and next steps. All levels retain all 42 criteria, the grammar pass, narrative requirements and artifacts. A completed level-1/2 report does not need independent assessment. Level 3 requires confirmation metadata for usable reports, and reconciled confirmation for completed status. Do not silently downgrade a level-3 run to make it completed. At levels 2–3, unfinished in-scope browser work makes the review partial; genuine access/technical blockers can remain in a completed scoped report if attempted and disclosed. The validator checks level/selection/confirmation metadata; manual evidence reconciliation must verify actual browser coverage and level-1 boundaries.

## Delivery

Run `validate_review.py RUN_DIRECTORY --render` to validate data and produce review.md, evidence-register.md, and validation.json. Without `--render`, the helper also verifies both Markdown files match their deterministic renderings. validation.json records errors, narrative word count, and criterion-to-passage coverage. Nonzero exit means validation failed. Both modes replace only the current run's validation.json; rendering replaces only the current run’s generated review.md and evidence-register.md, never sources or prior runs.

review.md begins with course identity, snapshot date, mode, selected review level when recorded, rubric version, and review status. A brief note identifies pending/deferred checks and directs readers to full scope/limitations when applicable. The complete narrative follows before all seven category tables in source order, a revision checklist for Minor/Moderate/Major findings, and grammar findings. Accessibility/compliance actions precede lower-impact refinements. Full scope/limitations and stage outcomes follow; a short link directs reviewers to evidence-register.md. Long source-ID lists are replaced by short criterion evidence links in the main tables. The report's title and status expose partial/failed outcomes. A failed run produces a diagnostic report without a narrative.

## End-user PDF delivery

Generate a PDF when requested; export the finalized review rather than starting a new course review. Save the final file **inside the existing review run directory**, alongside review.md, review.json and narrative.md, with a descriptive name such as `course-<id>-design-review.pdf`. This course-review destination takes precedence over a generic PDF workflow's `output/pdf/` convention. Do not deliver only a copy in a separate export folder, and configure any retained export helper to write to the run directory.

Preserve the faculty narrative followed by all 42 criteria in the seven rubric categories. Use tables with **CU/ID, Criterion, Rating, Findings/scope, and Action/verification** columns; do not substitute stacked cards or prose sections unless the user asks for that layout. Landscape pages may be used for wide tables, with portrait narrative/checklist pages. Repeat column headers on continued table pages, keep category headings with their first row, and keep each criterion row together when it fits on a page. If a row must span pages, repeat its identity and clearly identify the continuation. Keep readable type rather than shrinking the table to fit.

The end-user edition omits internal Evidence/Evidence register/confirmation-file links, source-ID maps, raw object IDs used only for verification, and reviewer-process details. Retain course identity and CU criterion numbers. Preserve the ratings, substantive findings, uncertainty, pending/deferred items, scope limitations, revision checklist and grammar corrections; removing provenance must not strengthen conclusions or imply launch approval. Keep the canonical JSON/Markdown and separate evidence register intact for internal verification. A short, accurate confirmation statement may remain without links to its private artifacts.

Keep each specific action next to its clickable Canvas destination as a sub-list in the **Action/verification table cell** and under its **revision checklist item**. Retain actionable verification/setup links and relevant human-readable public citations; these are distinct from internal evidence links. Do not replace action/link pairs with a detached list of destinations.

Use the PDF workflow to render and visually inspect every page. Check table boundaries, wrapping, repeated headers, category/row continuity, page numbering, and absence of clipped text, overlapping content or orphan spill pages. Verify all 42 criteria are included, all intended action destinations remain clickable, internal evidence links are absent, and the final file is in the review run directory. Deliver a direct link to that PDF. Record export checks alongside the review when useful; do not claim the Markdown validator alone validates PDF content/layout.

## File review scope

Optional `manifest.file_reviews` retains one entry per inventoried file: `source_id`, `file_id`, `name`, `format`, `role`, `content_check_required` (boolean), `check_type`, `check_status`, `reason`, and `references` (source IDs with instructor-only flags). Status is pending, verified, blocked, or excluded. Verified means the recorded check scope has evidence; excluded means outside that check scope, not accessible/compliant. Unlinked document candidates require scope confirmation. Linked images/media receive contextual accessibility checks rather than standalone document checks. File metadata retrieval marked inspected in the coverage inventory does not mean document contents were reviewed. The separate evidence register renders only non-excluded files in its checklist, source register, and coverage inventory. No file inventory or source register appears in the main report. The internal manifest retains every file and its exclusion reason.

Verification queue entries record `preferred_method: api_first`. On substantive verification, record `verification_method` (api, local_document, browser, or mixed), `verification_scope`, and evidence `source_ids`. When browser use is necessary, record `browser_trigger` naming the unanswered question. API retrieval marked inspected does not automatically verify substantive content or visual/access behavior. A verified API check must never be described as browser-verified.

## evidence-register.md

Generated by the same validator/renderer as review.md. Contains every criterion’s evidence status and source-ID mapping, the grammar evidence map, source register, non-excluded file review checklist, and coverage inventory. When browser-checks.json is present, include its recorded verification dispositions with methods, scope/reasons, and evidence IDs. This is optional reviewer detail; the main faculty report stands on its own. The complete manifest and queue JSON retain excluded file metadata internally. Without --render, a missing or modified evidence register fails rendering-consistency validation just like a modified review.md.

## Confirmation metadata

Optional `review.confirmation` preserves backward compatibility for historical artifacts. New level-3 reviews perform the blind workflow before delivery. Levels 1–2 omit confirmation metadata and state that independent assessment is outside scope; a user requesting it upgrades the review to level 3. Fields are `status` (reconciled, pending, unavailable), `blind` (boolean), `limitations` (array), and local paths `input_index`, `independent_assessment`, `reconciliation`, `policy_audit`. Reconciled requires blind=true and all four artifacts present; reconciliation uses `confirmation/reconciliation.md` for the main report link. Incomplete confirmation needs limitations and cannot accompany a completed report. The validator verifies artifact presence and metadata consistency, not actual agent independence or the semantic quality of reconciliation. Record these artifacts as hashed manifest sources for provenance. Historical reports without metadata receive no confirmation statement.
