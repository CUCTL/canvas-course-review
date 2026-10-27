# Kuali CUOCDR draft transfer

Use this workflow only when the user asks to start, populate or update a Kuali review draft. A course review alone does not authorize writing to Kuali. An authorized draft request includes saving an unsubmitted draft and verifying it; do not ask again for those steps. Stop before Submit or any workflow-routing operation. Packaging this skill does not authorize a live test write.

## Destination and authentication

The Cedarville CU OCDR Flow app is `65204f1a32976c013abf9212`:

- Respondent: `https://cedarville.kualibuild.com/app/65204f1a32976c013abf9212/run`
- GraphQL Playground: `https://cedarville.kualibuild.com/app/api/v0/graphiql`
- Endpoint: `https://cedarville.kualibuild.com/app/api/v0/graphql`

Use the user's authenticated browser through its supported automation tools. Follow their documented entry point. Never extract cookies/tokens or copy authorization headers into local scripts, logs or source control. If authentication is missing, have the user complete sign-in, then resume. The local helper below neither authenticates nor sends network requests. Use a supported authenticated connector if one is available and exposes the required operations; otherwise run GraphQL through the Playground UI.

Assume the form schema and tested operation signatures are stable. Reuse the bundled `assets/kuali-cuocdr-form.json`; do not introspect or retrieve the form schema on every run. Confirm draft identity/course/status through a normal data read. Refresh the schema only after a schema-related failure (unknown field/type/option, unmappable form key, explicit version mismatch, or a recognized target field failing to persist). A schema check alone does not prove draft saving.

For other GraphQL errors, switch to the Kuali form UI to complete the authorized draft edit and Save. This includes mutation-permission or non-schema server errors; do not repeatedly probe alternate mutations. For authentication errors, restore normal sign-in first, then use the form UI. Before retrying an ambiguous failed write, inspect current saved data/UI to avoid overwriting edits or creating duplicates. Browser fallback has the same draft-only boundary and requires a reload check; if browser save also fails, report the concrete blocker.

## Resolve the exact draft

Opening `/run` created a draft in the tested workflow. Inspect existing drafts first to avoid duplicates. Use the form UI to choose the exact course and save it. Confirm the selected course code and title against the review. The Kuali catalogue title can differ from the Canvas master-course name.

The draft URL/action ID is **not** the underlying document ID. A known read operation is:

```graphql
query InspectDraftAPI {
  myDrafts(args: {limit: 10, skip: 0}) {
    edges { node { id documentId title } }
  }
}
```

Match the selected UI draft to its `documentId`; do not choose the newest item blindly. Read that document using the stable query below; the helper uses the cached schema by default:

```graphql
query InspectDraftAPI {
  document(id: "EXACT_DOCUMENT_ID") {
    id status data
  }
}
```

Save the response as `state.json` inside the ignored review run. Require `status: "saved"` and a browser DRAFT badge. If identity, status or course is ambiguous, resolve it before writing. Do not embed real draft IDs in the reusable skill.

## Prepare a reviewable transfer

Validate the review and complete the [writing style agent check](writing-style-review.md) first. Recheck rewritten action or narrative text before transfer. Use its finalized `review.json` and faculty-facing `narrative.md`, including the unscored next-term teaching tips required by [the narrative guide](narrative-feedback-guidelines.md). Transfer that narrative without appending internal policy exceptions, audit history or judgments about past teaching.

```bash
python3 <skill-path>/scripts/kuali_draft.py prepare <run-directory> \
  --state <run-directory>/state.json \
  --course-code 'EXACT KUALI COURSE CODE' \
  --out <run-directory>/kuali-transfer-01
```

The helper uses the bundled schema (or `--schema PATH` for a refreshed form object) when `state.json` omits `form`. It maps all 42 criterion IDs from ordered top-level `data.*` schema fields and their template options. It ignores derived `.id`/`.label` fields. DOM gadget IDs are not form keys. It stops on missing, duplicate or ambiguous mappings, unknown rating options, the wrong selected course or a non-draft status. Label/schema changes need inspection and an intentional mapper update, not guessed keys.

Review `plan.json`, `mutation.graphql` and `variables.json` before execution:

- Ratings use the template's actual `{id, label}` options. N/A maps to the form's `NA`; null remains unrated, never NA.
- For revision and pending criteria, action fields contain concrete actions and task-specific destination links from `action_links`. For N/A, transfer the course-specific explanation from `na_reason`; historical records without it use their evidence rationale. Do not clear the N/A comment or turn it into a repair task. Legacy links without `action` use `action_plan` once followed by their destinations. Preserve actionable `verification_step` tasks, including for unrated criteria, without duplicating a task already included in an action. For revision and pending criteria, do not include findings, evidence, uncertainty, internal verification labels, instructor preparation reminders or rating rationale. The N/A explanation is the deliberate exception. Rewrite a verification step as a plain task if it contains reviewer metadata; the helper rejects those prefixes. Review the text semantically as well as checking prefixes.
- Present action fields are empty; N/A action fields contain their explanations. Kuali may omit hidden Present action fields entirely; the verifier treats absent, null and empty strings as equivalent only for known action fields expected to be empty. Do not count omitted fields as lost findings or force evidence into hidden action fields.
- The narrative is escaped HTML generated from the saved Markdown; CU anchor references become plain criterion references. No process or policy paragraphs are appended.
- The course selection is never written by the helper.

Existing nonempty values that differ from the report become conflicts, and `prepare` exits 2. No mutation is authorized while `ready` is false. Existing human edits are not a stale cache to overwrite. Reconcile with the user's current instructions and current draft; prepare a fresh baseline immediately before writing. After reviewing an exact replacement that is within the user's authorized scope, pass `--replace-field EXACT_KEY` for each intended replacement and a new output directory. There is no blanket overwrite switch. An unresolved criterion with an existing rating requires explicit manual reconciliation; the helper does not clear it automatically.

For a narrow change (for example, narrative only), create a reviewed JSON payload containing only those exact fields from the prepared desired values. Preserve a fresh full read-back as the baseline and compare all other fields after saving. Do not execute the full-course transfer just to update one field. Never reuse an earlier full payload after the user edits the draft.

## Save and verify

Execute the prepared mutation through the authenticated Playground. Replace the query and variables editor contents completely; do not append JSON. Native paste is suitable for long payloads; typing thousands of characters timed out in testing. Inspect editor state before Execute. Use a consistent operation name or confirm the active operation selector when switching between query and mutation. If a call times out, read saved state before retrying; do not create another draft.

The tested operation is `updateDocument(args: {id: ..., data: $data})`, with `$data: JSON!`. It merges recognized schema fields in the tested app. Do not assume that unknown keys persist: an earlier write to a DOM gadget ID was ignored. No submission mutation is included in this workflow.

After the save response, execute a **separate document query** for id/status/data, and save it as `readback.json`. A successful mutation response is insufficient by itself.

```bash
python3 <skill-path>/scripts/kuali_draft.py verify \
  --plan <run-directory>/kuali-transfer-01/plan.json \
  --readback <run-directory>/readback.json
```

The verifier checks draft/document identity, expected values, intentionally blank ratings, and unexpected changes outside the payload. It checks form version only when the read-back supplies one; it does not request schema metadata routinely. On failure, inspect the mismatch; do not overwrite concurrent user edits or claim completion. For a reviewed narrow payload, compare its target fields and all non-target fields against the fresh baseline separately.

Reload the form and check the selected course, changed ratings/action fields and narrative, plus the DRAFT badge. Confirm that nulls remain blank, N/A explanations are retained in their Action Plan fields, and fields hidden for Present are absent/empty as expected. If the form hides an N/A comment, record that visibility limitation and retain the explanation in the report rather than claiming it is displayed. Do not click Submit. Save a screenshot showing the requested result, keep the draft tab as a deliverable when supported, and give the draft link. Distinguish API verification from browser verification and submission.

On schema failure, fetch the target document’s `form { id template schema { formKey label } }` once, save the returned form object as a replacement schema cache, remap and inspect the new plan. Use that document’s form version rather than an unrelated designer version. Update the bundled cache only after verification; keep it limited to form IDs, labels, keys and rating options, without documents, selections, user data or credentials. If schema refresh does not resolve the problem, use the form UI.

If the user asks specifically to test saving before full population, write a harmless temporary note to the correct narrative field in the authorized draft, independently read it, reload to confirm, then restore the baseline and verify restoration. Record test success separately from full transfer success. A prior successful test does not guarantee a new app/version's write behavior.

Keep baseline, mapping, payload, response, independent read-back and verification artifacts in the ignored run directory. Record hashes in the manifest when retaining them as review evidence. Never store authentication material. The helper has no submit, delete, routing, network or credential capability.
