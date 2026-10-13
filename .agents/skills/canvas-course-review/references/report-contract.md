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

## review.json

Required fields:

- schema_version: `1`.
- status: `completed`, `partial`, or `failed`.
- stages: object with `design`, `grammar`, and `narrative` outcomes, each `completed`, `partial`, `failed`, or `not_started`.
- limitations: array of nonempty strings, possibly empty. Required to be nonempty for partial/failed status.
- criteria: array of all 42 records for completed/partial reports, with no duplicate or invented IDs. A failed run may retain a subset, but cannot render a successful report.
- grammar: array of objects with nonempty `source_id`, `issue`, and `suggested_fix`. An empty list means no confirmed mechanical issues only when that stage completed; partial stages must describe limits.

Each criterion record has `id` (integer), `rating` (allowed label or null), `evidence_status` (policy enum), `source_ids` (source IDs), `evidence` (concise text), `action_plan`, `verification_step`, `uncertainty`, and `deferred` (boolean). Empty strings are permitted for action/verification/uncertainty only where irrelevant. N/A uses not_applicable; null uses not_verified. Present uses verified. Revision findings use verified or scoped not_evidenced. All records need sources describing observation or search scope, including blocked checks. Null records need a verification step and uncertainty; revision records need an action plan. Explain N/A in evidence. A deferred record is null and explains the placeholder and completion step.

For completed/partial reports, `narrative` is an object with:

- file: `narrative.md`.
- coverage: array of objects with `criterion_id`, `passage`, and `next_step`, exactly one for each Moderate/Major criterion. Both text excerpts occur verbatim in the draft; the next step occurs inside the mapped passage. A paragraph may cover multiple criteria, each mapped separately.
- teaching_tips: array of at least three distinct verbatim excerpts from the draft, each describing a practical next-term teaching suggestion.
- strengths_excerpt: verbatim excerpt from the opening paragraph.
- closing_excerpt: verbatim excerpt from the closing paragraph.

The first nonblank line of narrative.md starts `Subject:` and includes the exact course name. Count all whitespace-separated words in the file, including subject/greeting/sign-off. Maximum 600. For partial reports the draft explicitly says `partial review`. The helper validates excerpts but cannot establish their meaning, theme grouping, priority, faculty tone, supportive closing, or substantive coverage. Check these manually against the ten narrative requirements.

## Delivery

Run `validate_review.py RUN_DIRECTORY --render` to validate data and produce review.md and validation.json. Without `--render`, the helper also verifies review.md matches the deterministic rendering. validation.json records errors, narrative word count, and criterion-to-passage coverage. Nonzero exit means validation failed. Both modes replace only the current run's validation.json; rendering replaces only its generated review.md, never sources or prior runs.

review.md includes all seven category tables in source order, source IDs and locations, inventory, scope, stage status, limitations, grammar findings, priority actions, and the complete narrative. The report's title and status expose partial/failed outcomes. A failed run produces a diagnostic report without a narrative.
