# Writing style review agent

Use a separate agent to review the narrative and action plans for every new review at levels 1–3 and every later rewrite of those materials. The audience is a general educator without instructional design training. This is an editorial review of drafted feedback, separate from the level-3 blind assessment of course evidence. It does not change the selected review level or require new API/browser work.

## Prepare the input

Preserve historical reports and prepare a fresh working copy with review.schema_version=2 (manifest.schema_version stays 1). Version 1 is read-only compatibility, not an alternative way to publish revised feedback without this check. After finalizing findings and any level-3 reconciliation, draft the narrative and complete table actions using [the narrative guide](narrative-feedback-guidelines.md) and [the report contract](report-contract.md). Prepare a fresh local snapshot:

```bash
python3 <skill-path>/scripts/prepare_writing_review.py <run-directory> \
  --out writing-review/pass-01
```

The helper writes input.json with a content_sha256 and the text to check. It does not approve writing. Use a new pass directory after edits; do not overwrite an earlier input or assessment. The snapshot includes evidence, ratings and limits as read-only context so the reviewer can detect a change in meaning.

Spawn a separate agent with fork_turns="none" and a self-contained task. Give it only this guide, the narrative guide, the action-language section of the report contract, and the exact input.json path. This agent must be distinct from the primary reviewer and any level-3 blind reviewer. It may see the drafted findings: do not describe this check as blind. Keep it within the assigned local files; no network, browser, Canvas, Kuali, student-record access or edits to original reports.

A suitable task is:

> Check the supplied narrative and recommendations for a general educator without instructional design training. Follow the writing review guide. First check whether the overview explains the course's strengths, main findings, significance for students and a manageable starting point, with full repair instructions in the tables. Then check wording and coverage. Use the evidence only to preserve meaning; technical evidence may remain technical. Return the required assessment at the assigned path. Do not change ratings, findings, URLs or original files, and do not perform a new course review.

## What the agent checks

Check the narrative's purpose before polishing sentences. A draft that mainly repeats or shortens table repairs needs revision even if its grammar, coverage and word count pass. Identify the missing explanation or connection in a specific passage; do not demand a new heading, fixed paragraph count or formulaic wording.

- Supported strengths explain what is worth keeping. Related findings form a coherent picture, with their implications for students and an understandable next step. An impact statement must follow from observed design; do not invent student experiences or learning outcomes.
- The overview makes a manageable starting point clear, respecting accessibility/compliance and learning impact before easy refinements. Full location-specific repairs remain in the tables. Related Moderate/Major findings can share the same mapped passage and next step; criterion-by-criterion narration is not required.
- The narrative reads as an explanation to an instructor, with specific strengths and coherent concerns. It avoids stock praise, filler, abstract labels and paragraphs that merely string together repair commands. Test the actual wording, not just sentence length or the presence of familiar verbs: could an educator say what the sentence means without translating it? Explain or replace phrases such as “imagery-license guidance,” “intended course design” or “planned instructor contact” when a direct statement is clearer. Do not change the request or turn these examples into a blanket word ban.
- Each action_plan, verification_step, action/link label, instructor reminder and displayed uncertainty tells an educator what needs to change, where, and how to check the result. Keep necessary terms such as Heading 2 when they help carry out the task, with a short explanation where needed.
- Recommendations identify the issue and work without assigning it to CTL, faculty, the library, a course owner or another party. The only offer of assistance is in the closing: CTL can assist with revisions. Keep needed references to course-role information and source facts, and preserve decisions and approval conditions. Do not drop a required check or unresolved choice while removing the assignment of responsibility.
- The overview covers every Moderate/Major concern and gives next steps; full task/location instructions remain in the tables. Do not lose a substantive task while reducing repetition.
- Conditions, uncertainty, course-owner decisions, mandatory versus optional work, dates and amounts remain intact. Do not turn a proposed choice into an instruction or an unverified check into a confirmed defect. Flag meaning questions for the primary reviewer rather than resolving them by guessing.
- The narrative retains at least three practical next-term teaching tips and stays within 600 words. Links remain attached to the correct work. Follow-up history stays brief and preserves what was actually verified.
- Evidence, source quotations, measurements, raw identifiers and the official rubric are read-only context. Do not rewrite technical evidence merely to make it conversational. Assess its explanation only when that wording appears in a recommendation.

Return concrete, useful edits rather than a vague style score or a list of prohibited words. For each problem identify the exact field or passage, original text, suggested wording, reason and any risk of changing meaning. Retain clear passages without rewriting them simply to demonstrate activity.

## Assessment and reconciliation

Save assessment.json in the pass directory. It has status (passed or needs_revision), reviewer (agent identity), content_sha256 copied from the inspected input, and issues (an array). Each issue includes location, original, suggested, reason and meaning_check. passed requires no remaining issues. An agent that proposes edits reports needs_revision for that input; it cannot approve a different version it has not read.

The primary reviewer checks proposed edits against the evidence and applies agreed wording to canonical structured fields and narrative.md. Preserve ratings, factual evidence and URLs. Refresh the narrative coverage excerpts and any duplicate action wording. Prepare a new snapshot and have the same style agent check the revised wording when available; if another reviewer must take over, provide the frozen input and earlier assessment plus the new snapshot, and keep that reviewer distinct from the editor; return only changed or disputed passages as the focus, with the full snapshot available for context. Stop when the reviewed version passes. Approval requires a deliberate check of the narrative's purpose, natural wording, preserved meaning, complete action plans, teaching tips and coverage; a structurally valid draft alone is insufficient. If a meaning question remains unresolved, keep the report provisional and describe the specific limitation rather than repeatedly polishing around it.

Record review.writing_review with status, reviewer, report (the run-relative assessment.json path), content_sha256 and limitations (an array). Status may also be pending or unavailable. A new report cannot be completed with an unfinished style review. If no agent is available, record unavailable and the limitation, retain partial status, and do not claim the primary self-check was a separate review. Existing historical reports without this metadata remain readable; do not add an approval claim retroactively.

The report validator checks a passed assessment and its content hash against the current narrative, actions and factual context. Changed text needs a fresh check. It cannot judge readability or prove that an agent actually reviewed the files. Keep assessment details in the evidence register and local artifacts, outside the faculty narrative. Render the final reports, rerun validation and export any requested PDF only after the style pass. Verify Kuali payload text still matches the approved narrative/actions if transfer is requested.

## Testing changes to these instructions

When the user asks for a pilot of revised writing guidance, use preserved copies of several existing reports. Have a different reviewer compare the original and revised feedback without being told which is the new version. Assess natural wording, organization, specific next steps and preservation of meaning, with concrete examples; do not assume the rewrite is better or use word count as a quality score. The reviewer must not approve a draft they wrote. Keep the original evidence and ratings intact, retain both versions and the comparison, and record any cases where the original wording was already clearer. This pilot comparison is separate from blind assessment of the course.
