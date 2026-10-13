# Independent blind confirmation

Run this step for level 3 course-design reviews before delivering findings. Levels 1–2 do not require it; use the primary consistency check and report validation instead. Reuse saved API, document, and browser evidence; do not repeat browser verification by default. This is an independent policy/evidence assessment, not student grading or authority to change Canvas.

## Phase 1: independent assessment

Use a separate agent with `fork_turns="none"` and a self-contained task. Provide the exact course/scope, snapshot dates, CUOCDR rubric, review policy, explanatory guidance, and a narrowly scoped folder of raw API JSON/HTML, original documents, browser snapshots/screenshots, and raw measurements. Include supplemental API reads and technical measurements supporting primary claims (such as grading flags and computed contrast), with provenance; remove primary interpretation/rating labels, not the underlying observations. Refresh evidence only if an actual conflict or gap requires it. If new evidence is introduced after the blind freeze, identify it in the non-blind reconciliation rather than claiming it was assessed blindly.

Do not provide primary ratings, findings, action plans, narratives, reports, interpretation notes, reconciliation files, or report paths. Avoid copying generated review artifacts or disposition queues into the raw input bundle. A shared filesystem is not an access-control boundary: explicitly restrict the reviewer to its assigned input paths and forbid inspecting other reports, conversation history, Canvas grades, or unrelated files. Keep primary artifacts outside that bundle.

Ask the reviewer to independently assess all 42 criterion IDs with rating or null, evidence state, deferred flag, original evidence/path references, concrete next steps, and uncertainty. Enforce the design-only boundary in all modes: judge documented plans and authored/configured content, not actual teaching execution, engagement, or outcomes; teaching tips are optional suggestions. Require policy-compliance observations, source/version conflicts, and limits on what existing evidence establishes. No network/browser work, Canvas changes, or student-record inspection is needed for this confirmation task.

Save the primary assessment and the independent assessment before comparison. Record the input-file list/hashes and the reviewer’s statement of blindness. If the reviewer saw primary judgments prematurely, discard its confirmation claim and rerun Phase 1 with a fresh agent.

## Phase 2: reconciliation and report audit

After freezing the independent assessment, expose the primary findings and artifacts for comparison. This phase is explicitly no longer blind. Check disagreements against the original evidence and controlling policy; do not average ratings or automatically prefer either agent. Record criterion-level differences, decisions, supporting evidence, and any remaining instructor/institutional judgment.

Have the reviewer check the final structured findings, narrative, main report, and evidence register for consistency: exact IDs/wording, evidence sufficiency, severity, deferred versus deficient items, scope/status, contradictions, current versus superseded evidence, every Moderate/Major narrative mapping, concrete next steps, supportive tone, three teaching tips, and the 600-word limit. Confirm that excluded files stay out of delivered listings and detailed provenance stays in the separate evidence register.

If changes follow that audit, update all affected artifacts and run the validator again. Recheck only changed or disputed passages rather than repeating the full evidence/browser review. Save the policy audit and reconciliation record; name any unresolved judgments in the report. State that the initial assessment was blind and the comparison/audit followed it, rather than describing the comparison itself as blind.

If an independent agent is unavailable or blindness is contaminated and cannot be restored, disclose that confirmation is incomplete and keep delivery provisional. Do not claim blind confirmation merely because a second agent read the finished report.

## Artifacts

Keep private run artifacts under `confirmation/`: the input index, frozen `independent-assessment.json`, independent notes, `reconciliation.md`, and `policy-audit.md`. Preserve originals. In review.json, record optional `confirmation` metadata with `status` (reconciled, pending, unavailable), `blind` (whether Phase 1 remained independent), local artifact paths, and limitations. New level-3 reviews require this step; older reports without that metadata remain readable but must not acquire a confirmation claim. Main report needs only a short confirmation statement and link; detailed differences belong in the evidence appendix/confirmation files.
