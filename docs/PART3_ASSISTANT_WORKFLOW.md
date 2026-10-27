# Part 3 — rocket and evidence context

Open **http://127.0.0.1:8768/** and refresh. The rocket remains the ordinary entry to Nemotron and Tavily; no right-hand AI panel is added.

## Move or minimize the rocket

Drag the rocket freely and release it. Its resting position moves clear of visible controls when space permits. **Rocket options** offers **Dock safely**, **Reset position** and **Minimize / Show full rocket**, plus keyboard help. Alt + arrow keys move it; Alt + Home resets it.

Your preferred position is remembered. A changed layout can require a different safe resting position. On crowded screens, access becomes compact; if no floating space is available, it appears in normal page flow below the header. It restores full size when room returns unless you explicitly minimized it. Other native dialogs hide the companion until they close. Reduced motion and the local graphics fallback remain supported.

## Check what you are asking about

Open a saved project and click **Ask 6D**. Above the question, the context card identifies the saved project/revision, page, calculation, whole-project or selected-check scope, finding status and relevant linked-reference availability. Draft and historical context is explicit.

Opening from a selected requirement in Systems chooses that check. Opening from Overview, reports or a selected model/input uses whole-project context. Explicitly changing the assistant scope is retained when reopening the same context. **Use this page’s context** resets to the current page’s selection. Typed questions survive scope/page changes within the same saved project/revision/calculation, with a reminder to review them. They are not automatically carried to a different project or revision.

A selected test row is included only with its matching saved project, revision, calculation and requirement. Switching checks parks it and shows that it is excluded; returning to its matching check restores it. **Clear selected test row** removes it. Selection itself sends nothing.

Reference counts describe current links available in scope, with review-required and unavailable targets shown separately. They do not promise that every reference fits into the provider request: the existing bounded capture policy still applies. Search results and unlinked library sources are excluded.

## From Tavily to a Nemotron question

1. In the rocket, choose **Find references**, select the topic, enter a query and explicitly search.
2. Preview a result. **Copy draft to Source library** prepares an unsaved source form in the matching latest saved context.
3. Review the passage and save it explicitly. A saved library source is still unlinked.
4. Select the source, project check and rationale, then explicitly **Link reference**.
5. On a current linked reference, **Ask about this reference** opens the rocket with its scope and a prepared or retained question. Review it, then explicitly choose **Ask Nemotron**.

Copying refuses to replace an unfinished source or link draft. The preview remains available and the reason is shown inside the rocket. Save, link, search and Ask are separate operations; none starts automatically. Editing a source can require link review before it is current again.

This refinement changes interface context and handoffs. It does not change solvers, findings, model defaults, credentials, budgets or hosting permissions. [Verification and limits](PART3_ASSISTANT_WORKFLOW_RESULTS.md) · [Acceptance](PART3_ASSISTANT_WORKFLOW_ACCEPTANCE.md).
