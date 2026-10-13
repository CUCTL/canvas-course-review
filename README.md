# Canvas course review

A Codex skill using API-first verification with browser checks only when necessary for Cedarville's CUOCDR v0.9 course-design review. It preserves all 42 rubric criteria, uses OSCQR as explanatory guidance, and places faculty-facing narrative feedback near the top of the report, within 600 words.

The skill reviews course design without modifying Canvas or reading student grades/submissions. For live courses, a read-only canvasapi collector gathers structured evidence, used directly for verification; browser checks address only questions that API/local document evidence cannot resolve. Browser-only reviews and supplied exports remain supported. No nested AI API, OpenAI key, or server is required. Live API review requires an authorized Canvas API token; browser-dependent checks require authenticated browser access; credentials and snapshots stay local.

## Use

The visible, shareable skill folder is at [skills/canvas-course-review](skills/canvas-course-review/SKILL.md). Invoke `$canvas-course-review` with a course URL/ID or an export and the desired scope. Pre-launch review is the default. For use in other projects, symlink that folder into `~/.codex/skills/canvas-course-review`; keep this checkout as the maintained source. A repository-local symlink under `.agents/skills/` preserves automatic discovery without duplicating the files.

The shareable skill files are all committed under `skills/canvas-course-review/`, including dependencies, collector, validator, and references. Share the repository or copy that complete folder; the installed local symlink is not the distributable. See [portable setup and collection coverage](skills/canvas-course-review/references/api-collection.md).

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/canvas-course-review/requirements.txt
.venv/bin/python skills/canvas-course-review/scripts/collect_course.py \
  --course-id 12345 --env-file /absolute/path/to/.env
```

Example request:

> Use $canvas-course-review to review this Canvas course before launch. Extract API evidence first, verify the necessary findings and visual/access checks in the browser, include draft modules, document evidence limitations, and produce the CUOCDR report and faculty narrative.

Deliverables are manifest.json, review.json, narrative.md, review.md, and validation.json in a unique local run directory. See [the report contract](skills/canvas-course-review/references/report-contract.md). The validator checks criterion completeness, source references/local hashes, rating/evidence consistency, stage outcomes, narrative coverage excerpts, and the word limit. It cannot establish semantic correctness, accessibility compliance, or remote link health; the reviewer must inspect evidence and check the narrative substantively.

```bash
python3 skills/canvas-course-review/scripts/validate_review.py /absolute/path/to/run --render
.venv/bin/python -m unittest discover -s tests -v
```

## Source and status

The unchanged source rubric and legacy instructions are retained in references/. The skill carries its own references so it works when installed independently. The migration plan and research notes remain in docs/; implementation covers hybrid API/browser and export workflows, a read-only collector, and report validation. No service cutover is implemented.

The narrative covers every Moderate/Major finding with concrete next steps, prioritizes accessibility/compliance concerns, provides at least three next-term teaching tips, and closes with institutional support. It is a draft; creating it does not authorize sending it to faculty.

Synthetic tests exercise the collector through actual SDK models and pagination, alongside validator tests and skill-package validation. A live Canvas pilot and substantive behavior evaluation remain to be performed. No course has been reviewed or changed by repository creation.

The internal manifest retains the complete file inventory; the report omits excluded files and scopes content review to instructional documents such as DOCX, PDF, PPTX, and spreadsheets. Images/media receive contextual accessibility checks; unused assets and their exclusion reasons remain in internal artifacts. Unlinked documents and instructor references receive a scope check before content inspection.

Faculty reports include the narrative, full rubric, and a revision checklist. Detailed sources and verification coverage are saved separately in `evidence-register.md`; excluded files remain in internal JSON only. Both Markdown artifacts are generated and checked by the validator.

Each new review includes an independent blind agent assessment using saved raw evidence, followed by reconciliation and a report-policy audit. Browser checks are not repeated by default. Confirmation records stay with the ignored course-review artifacts; the reusable workflow is included in the shared skill.
