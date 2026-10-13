# Canvas course review

A browser-first Codex skill for Cedarville's CUOCDR v0.9 course-design review. It preserves all 42 rubric criteria, uses OSCQR as explanatory guidance, and appends faculty-facing narrative feedback within 600 words.

The skill reviews course design without modifying Canvas or reading student grades/submissions. It supports authenticated browser inspection and supplied exports. No nested AI API, API key, or server is required. Live review requires access to the intended Canvas course through a supported authenticated browser.

## Use

The repository-local skill is at [.agents/skills/canvas-course-review](.agents/skills/canvas-course-review/SKILL.md). Invoke `$canvas-course-review` with a course URL/ID or an export and the desired scope. Pre-launch review is the default. For use in other projects, symlink that folder into `~/.codex/skills/canvas-course-review`; keep this checkout as the maintained source.

Example request:

> Use $canvas-course-review to review this Canvas course before launch. Include draft modules, document evidence limitations, and produce the CUOCDR report and faculty narrative.

Deliverables are manifest.json, review.json, narrative.md, review.md, and validation.json in a unique local run directory. See [the report contract](.agents/skills/canvas-course-review/references/report-contract.md). The validator checks criterion completeness, source references/local hashes, rating/evidence consistency, stage outcomes, narrative coverage excerpts, and the word limit. It cannot establish semantic correctness, accessibility compliance, or remote link health; the reviewer must inspect evidence and check the narrative substantively.

```bash
python3 .agents/skills/canvas-course-review/scripts/validate_review.py /absolute/path/to/run --render
python3 -m unittest discover -s tests -v
```

## Source and status

The unchanged source rubric and legacy instructions are retained in references/. The skill carries its own references so it works when installed independently. The migration plan and research notes remain in docs/; implementation covers the browser/export workflow and report validation, without an API collector or service cutover.

The narrative covers every Moderate/Major finding with concrete next steps, prioritizes accessibility/compliance concerns, provides at least three next-term teaching tips, and closes with institutional support. It is a draft; creating it does not authorize sending it to faculty.

Synthetic validator tests and skill-package validation are available. A live Canvas pilot and substantive behavior evaluation remain to be performed. No course has been reviewed or changed by repository creation.
