# Review levels

Select the level once per run, separately from pre-launch/published/export scope. Honor an explicit level or a clear request for its included work. An explicit blind-confirmation request selects level 3. Otherwise offer a concise question with these choices, placing the recommended default first:

- **2 — API + necessary browser verification + narrative (Recommended)**
- **1 — API content + narrative**
- **3 — API + necessary browser verification + blind assessment + narrative**

Explain that level 1 is faster and leaves interface/resource behavior unverified; level 2 adds targeted browser evidence; level 3 adds an independent policy/evidence assessment. Do not promise fixed token, credit, or time savings without measured usage. Allow a reasonable reply window (about 60 seconds for an async question), doing only independent setup/API collection in the meantime. If no answer arrives, announce use of level 2 and record selection as default. Explicit answers are user_selected. Do not treat UI preselection as a submitted choice or ask again when the choice is already known.

## Shared work

All levels substantively review API/export evidence and locally inspect in-scope instructional documents, evaluate all 42 CUOCDR design criteria, perform the mechanical grammar pass, and write the narrative after findings are finalized. Keep the narrative near the top of the faculty report and within 600 words, with every Moderate/Major concern, concrete next steps, accessibility/compliance priorities, three optional next-term teaching tips, and institutional support. Deliver the same main report, narrative, separate evidence register, and structured provenance artifacts. Perform a primary evidence/policy/narrative consistency check and run validation at every level. None evaluates course delivery or authorizes Canvas writes or sending feedback.

## 1 — API content (`api_content`)

Use supported read-only canvasapi methods, raw HTML/settings, and downloaded instructional documents, including local rendering when useful. Do not initiate browser verification. Mark conclusions requiring unsupported quiz content, rendered Canvas behavior, external-tool behavior, playback/caption quality, or other unavailable evidence as not_verified with a null rating and concrete next step. A scope exclusion is not an observed defect or verified behavior.

Disposition browser-only execution candidates as excluded with a selected-level reason, preserving the unanswered question and linked criterion. Keep them visible in the evidence register unless they concern an independently excluded file; do not hide unresolved criterion limits by clearing the queue. The faculty report states that browser verification and independent confirmation were outside the selected scope. Completed means this scoped review is done, not that all accessibility/resource behavior is certified.

## 2 — API + browser (`api_browser`; default)

Perform level 1's substantive review, then resolve evidence gaps through API/local checks first and targeted authenticated browser verification only when needed. Work through in-scope candidates as verified, excluded with a reason, or blocked after an attempted path with a limit and next step. Do not navigate every source or repeat checks answered by the API. No independent confirmation agent is required. State that independent assessment was outside scope; do not call this a blind-confirmed review.

## 3 — API + browser + blind assessment (`api_browser_blind`)

Perform level 2, then the [blind confirmation workflow](blind-confirmation.md): a fresh agent with fork_turns="none" assesses narrowly scoped raw evidence without primary judgments. Freeze both assessments, reconcile against evidence/policy, and audit the final report/narrative. Reuse saved browser evidence; no second browser pass by default. If confirmation is unavailable, contaminated, or unfinished, keep the run partial and disclose why. Do not silently downgrade it.

## Scope changes and fallbacks

Honor a later user upgrade/downgrade, record the change and actual work already performed in scope/limitations, and reuse current evidence without repeating collection. Never erase provenance or claim an independent assessment did not occur when one did. Preserve prior delivered reports; use a fresh output run for a revised delivery. If an upgrade needs fresh evidence, fetch only the gap and preserve timestamps.

Browser-only or export-only access is an evidence-source exception, not an automatic change of level. Honor explicit browser-only requests and supplied exports, record actual evidence scope and limitations, and use independent confirmation only at level 3. Do not claim API coverage where none exists. If API access fails in level 1, offer a browser/export fallback without silently initiating browser work. No browser access at levels 2–3 is a disclosed coverage limit, not proof that course features are missing.
