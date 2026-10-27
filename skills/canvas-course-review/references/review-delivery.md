# End-of-review delivery

At the end of each course review, provide the actual local report links and offer these options, individually or together:

1. Download the report as a PDF.
2. Submit the completed CUOCDR form in Kuali.
3. Upload the report PDF to **CTL → Online Course Review** in Teams and post a message linking to it.

Use an offer such as: “Your review is ready. Would you like a PDF download, Kuali submission, or the PDF uploaded to CTL → Online Course Review with a channel message? You can choose any combination.” State material limits if the review is partial. Honor options already requested or declined; do not ask again for an action already authorized, and do not re-offer a declined option for this report.

Offering delivery does not authorize it. A review request, a saved Kuali draft, a configured Teams destination or a preferred posting name is not permission to submit or post. Prepare the exact report, draft and message so the user can review them before requesting missing approval. Once an action is explicitly authorized for this report and content, carry it out without another generic confirmation. Ask only about a material change, missing required information or ambiguous destination.

## PDF download

When the user selects a PDF, generate it from the finalized, validated report using [end-user PDF delivery](report-contract.md#end-user-pdf-delivery). Include the narrative, all 42 criteria, N/A explanations and task/location pairs. Keep the report basename and save it in the existing review run. Render and inspect the PDF before delivery, then give its actual clickable local file link. Do not call a Markdown link a PDF download or promise a file that has not been created.

Selecting Teams upload also authorizes preparing the report PDF needed for that upload. Use another report format if the user explicitly selects it. Reuse the verified PDF when it already matches the final report; regenerate and verify it after relevant report changes.

## Kuali submission

Use [Kuali draft preparation](kuali-draft.md) to populate and independently verify the exact course's draft, preserving human edits. A draft-only request ends with a verified, unsubmitted draft. For an explicitly selected submission, follow [Submit when requested](kuali-draft.md#submit-when-requested); verify the final submission separately from saving. Keep partial-review limits and unresolved required information visible. Do not invent values, change ratings to satisfy the form, or report a saved draft as submitted.

## Teams upload and message

The default destination is the **CTL** team and its **Online Course Review** channel. Use another destination only when the user specifies it. Use the authenticated Teams and SharePoint connectors when they support the required operations; otherwise use an authorized Microsoft Graph workflow or supported authenticated browser interaction. Discover the tools available in the current session rather than assuming upload and posting are available. Never extract browser cookies or store access tokens.

1. Resolve the exact team and channel by display name, then confirm their returned IDs. Resolve the channel's actual Files folder; do not guess its SharePoint path or assume that another folder with the same name belongs to the channel. If matches are ambiguous, resolve that before writing. Do not create a team/channel or change membership or sharing permissions as part of report delivery.
2. Prepare the specific PDF, its filename, and the exact message body. Use only the faculty-facing report; keep source snapshots, student data, credentials, evidence registers, reviewer assessments and internal JSON out of the upload. Include a material scope limit when it affects interpretation.
3. After authorization, upload the verified PDF to that channel's Files folder with its report filename. Preserve existing files; on a name conflict, inspect the existing item before deciding whether to reuse it or request a replacement. Read back the uploaded item, confirm its name, folder, size and returned link, and verify its contents match the local PDF where download or checksum verification is supported. Use the returned file URL and existing permissions; do not create a public sharing link.
4. Post one channel message with the verified report link and the attribution below. Prefer a supported channel-message connector. Do not send DMs, email, cross-post elsewhere or tag people unless requested. On an ambiguous send/upload result, inspect the current channel or folder before retrying so the same report is not posted twice.
5. Independently fetch the posted message, or reload the channel, and check the text, file link and attribution. Return the actual uploaded-file and channel-message links. Report upload, posting and Kuali submission separately; a successful upload does not establish that the message was posted.

### Message attribution and content

Default to **Codex**. Use a posting name supplied by the user without asking again; if none was supplied, use the default. Add this line to every report message:

> Posted by Codex using the Canvas Course Review skill.

Replace “Codex” with the user-supplied posting name when requested. This is attribution in the message body; do not claim to change Teams' authenticated sender or edit an account's display name. Escape the supplied name as text rather than interpreting it as markup or a mention.

Example message, with placeholders filled only from verified results:

> Course review: {course code} — {course name} (Canvas {course ID})
>
> The review report is available here: {uploaded PDF link}.
>
> Kuali: {actual verified state and link, if relevant}.
>
> {Material remaining checks or scope limit, if any.}
>
> Posted by {posting name} using the Canvas Course Review skill.

Keep the message brief, professional and in plain language. Describe the actual review status; do not call a course approved or compliant merely because its report is complete. State Kuali submission only after it has been verified. If submission was not selected, omit that line or identify the actual draft/not-submitted state.

## Delivery record

Keep a local `delivery.json` in the ignored review run recording selected options, authorization basis, PDF path/hash, resolved destination IDs, posting name, exact message, uploaded item/link, message ID/link, Kuali document/receipt and each verification outcome as applicable. Do not store credentials. Preserve receipts and check them before retrying after interruption. Distinguish pending, prepared, uploaded, posted, draft-saved, submitted and verified results; do not collapse them into a single success claim.

If a connector, permission or sign-in is unavailable, keep the PDF and prepared message available, explain the specific blocker, and continue other selected actions that are independent of it. Never substitute another channel or claim delivery without verification. Once selected actions are fulfilled, return their links and verified outcomes without asking to repeat them.
