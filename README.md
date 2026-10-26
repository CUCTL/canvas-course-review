# Canvas course review

A Codex skill using API-first verification with browser checks only when necessary for Cedarville's CUOCDR v0.9 course-design review. It preserves all 42 rubric criteria, uses OSCQR as explanatory guidance, and places faculty-facing narrative feedback near the top of the report, within 600 words.

The skill reviews course design without modifying Canvas or reading student grades/submissions. For live courses, a read-only canvasapi collector gathers structured evidence, used directly for verification; browser checks address only questions that API/local document evidence cannot resolve. Browser-only reviews and supplied exports remain supported. No nested AI API, OpenAI key, or server is required. Live API review requires an authorized Canvas API token; browser-dependent checks require authenticated browser access; credentials and snapshots stay local.

## Use

The visible, shareable skill folder is at [skills/canvas-course-review](skills/canvas-course-review/SKILL.md). Invoke `$canvas-course-review` with a course URL/ID or an export and the desired scope. Pre-launch scope is the default. When no review level is specified, the skill asks the user to choose and waits for an explicit answer. Level 2 is recommended; no level is automatically selected. For use in other projects, symlink that folder into `~/.codex/skills/canvas-course-review`; keep this checkout as the maintained source. A repository-local symlink under `.agents/skills/` preserves automatic discovery without duplicating the files.

The canonical public source is [CUCTL/canvas-course-review](https://github.com/CUCTL/canvas-course-review). Use this repository for installation and updates. Older installations need one manual update from this source to receive the public updater default.

Each new review runs `scripts/check_updates.py --upgrade` against the [GitHub source](https://github.com/CUCTL/canvas-course-review). An exact match to a published ancestor upgrades automatically, with a rollback archive and file verification. Local edits and unknown versions are preserved; update failures are disclosed and the review continues with the installed version. After an upgrade, Codex reloads the installed instructions before reviewing. Only the skill folder changes; repository HEAD, unrelated files and reports remain unchanged. Omit `--upgrade` for a read-only comparison. Existing clients need one manual update to receive the new startup behavior; continuations and report-only edits do not repeat it.

The complete shareable skill package lives under `skills/canvas-course-review/`, including dependencies, collector, validator, and references. Share the repository or copy that complete folder; the installed local symlink is not the distributable. See [portable setup and collection coverage](skills/canvas-course-review/references/api-collection.md).

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/canvas-course-review/requirements.txt
.venv/bin/python skills/canvas-course-review/scripts/collect_course.py \
  --course-id 12345 --env-file /absolute/path/to/.env
```

Choose a review level:

| Level | Included work |
| --- | --- |
| 1 — API content | API/local instructional-file review + narrative and reports |
| 2 — API + browser (recommended) | Level 1 + browser verification where API/local evidence is insufficient |
| 3 — API + browser + blind assessment | Level 2 + independent blind assessment, reconciliation, and policy audit |

All levels retain the 42-item design rubric, grammar pass, narrative coverage checks, a separate writing style agent, and report validation. The style agent checks the narrative and action plans for general educators without instructional design training; evidence may remain technical. It does not count as the level-3 blind assessment. Level 1 explicitly leaves browser-dependent conclusions unverified. Levels 1–2 do not include independent blind course assessment. The selected level appears in the report. See [review-level scope and selection](skills/canvas-course-review/references/review-levels.md).

Example request:

> Use $canvas-course-review to review this Canvas course before launch. Extract API evidence first, verify the necessary findings and visual/access checks in the browser, include draft modules, document evidence limitations, and produce the CUOCDR report and faculty narrative.

Delivered reports use `<course-id>-<course-code>_review_<unix-timestamp>.md` and the matching `.pdf` when requested, for example `28805-MASTER_BTHT_3023_ONL_review_17888888987.pdf`. Internal artifacts retain manifest.json, review.json, narrative.md, review.md, and validation.json in a unique local run directory. See [the report contract](skills/canvas-course-review/references/report-contract.md). The validator checks criterion completeness, source references/local hashes, rating/evidence consistency, stage outcomes, narrative coverage excerpts, and the word limit. It cannot establish semantic correctness, accessibility compliance, or remote link health; the reviewer must inspect evidence and check the narrative substantively.

```bash
python3 skills/canvas-course-review/scripts/validate_review.py /absolute/path/to/run --render
.venv/bin/python -m unittest discover -s tests -v
```

## Source and status

The unchanged source rubric and legacy instructions are retained in references/. The skill carries its own references so it works when installed independently. The migration plan and research notes remain in docs/; implementation covers hybrid API/browser and export workflows, a read-only collector, and report validation. No service cutover is implemented.

The narrative covers every Moderate/Major finding with concrete next steps, prioritizes accessibility/compliance concerns, provides at least three unscored next-term teaching tips, and ends with a natural closing. Follow [the narrative guide](skills/canvas-course-review/references/narrative-feedback-guidelines.md) for the writing requirements. It is a draft; creating it does not authorize sending it to faculty.

Synthetic tests exercise the collector through actual SDK models and pagination, alongside validator tests and skill-package validation. Live-service behavior must be verified separately for each course review or authorized Kuali draft transfer.

The internal manifest retains the complete file inventory; the report omits excluded files and scopes content review to instructional documents such as DOCX, PDF, PPTX, and spreadsheets. Images/media receive contextual accessibility checks; unused assets and their exclusion reasons remain in internal artifacts. Unlinked documents and instructor references receive a scope check before content inspection.

Faculty reports include a conversational overview with numbered priorities and links to detailed findings, followed by all 42 criteria in the required five-column rubric tables. Actions and their Canvas destinations appear as ordinary lists in the table action cells, without checkboxes or a separate revision checklist. Full scope and limitations remain in the report. Detailed sources and verification coverage are saved separately in `evidence-register.md`; excluded files remain in internal JSON only. Both Markdown artifacts are generated and checked by the validator.

Level 3 includes an independent blind agent assessment using saved raw evidence, followed by reconciliation and a report-policy audit. Browser checks are not repeated by default. Confirmation records stay with the ignored course-review artifacts; the reusable workflow is included in the shared skill.

Scope is course design only, even for published/running courses. Interaction and feedback are assessed as documented plans and designed opportunities. Actual teaching performance, feedback execution, student activity/outcomes, and accommodation delivery are outside scope; the required next-term teaching tips are suggestions faculty may choose to use, without affecting design ratings.

Master/blueprint reviews count intentional instructor-completion scaffolds as Present, with explicit completion/publication reminders in the report. Unpublished status alone does not establish this exception; core content and accessibility requirements still apply. See [template placeholder guidance](skills/canvas-course-review/references/template-placeholders.md).

When requested, the skill can also prepare, save and verify an unsubmitted Kuali CUOCDR draft. The local helper handles payload preparation and read-back checks; authenticated browser interaction handles saving. Existing human edits are preserved, and draft authorization does not include submission. See [the Kuali draft workflow](skills/canvas-course-review/references/kuali-draft.md).

Before delivery, the separate [writing style reviewer](skills/canvas-course-review/references/writing-style-review.md) checks plain language, organization and preservation of meaning. Its assessment is saved locally and tied to the reviewed text; later changes require a fresh check. The main narrative remains within 600 words and includes at least three practical next-term teaching tips.

New and revised feedback uses review schema version 2, which requires the writing-review record. Version-1 reports remain readable for historical checks; rendering revised reports and preparing Kuali transfers require version 2 and current agent approval. Keep originals and revise a fresh copy.
