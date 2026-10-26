# Ask 6D from the rocket

Refresh [the local workspace](http://127.0.0.1:8768/). The small animated rocket stays near the lower left as you move through 6D. Click **Ask 6D** to open its conversation in the center of the application. It is the normal entry point for Nemotron questions and Tavily reference searches; there is no separate Assistant tab or right-hand AI rail.

## Ask about saved engineering evidence

1. Open a project from **Projects**. The rocket needs a saved project context before an investigation can start.
2. Click the rocket and choose **Ask Nemotron**.
3. Choose the whole-project scope or a particular requirement. Check the project, saved revision and requirement shown in the conversation.
4. Choose **Nano**, **Super** or **Ultra**, then write your question. Choosing a model or opening the rocket sends nothing.
5. Read the scope/consent guidance and explicitly choose **Start live investigation**. The existing connection, spending limits and active-job checks still apply.

Nemotron explains captured engineering evidence and suggests next checks. The saved calculation, declared limits and recorded finding remain authoritative. It does not run every aerospace discipline or establish launch readiness.

Scope/data explanations and earlier answers can be expanded when needed, keeping the current question and latest answer easier to find. Relevant unsent questions are retained when you close the rocket or navigate during the current browser session. They are not saved as project records and are not guaranteed to survive a page refresh.

## Find a reference with Tavily

Choose **Find references** inside the rocket. Select the engineering context and type the public query you want to send. Only an explicit **Search references** action makes a search request; opening the tab and reading saved searches do not repeat one.

Review a returned passage with **Review reference before using**. Search results are unverified supporting material and do not change calculation results. To retain one:

1. Inspect its title, URL and passage in the preview.
2. Choose **Use in source form**. 6D opens **Source library** and copies the reviewed reference into an **unsaved** form.
3. Review the populated fields, save the reference explicitly, then add its engineering link.

Copying a preview does not automatically save, link or validate a reference. If copying fails, the preview remains available. Search requests use the configured Tavily allowance, with existing limits and no automatic retries.

## Inspect an item in the center

In **Engineering → Systems workspace**, select a requirement, model or input. **Inspector** and **Evidence** now appear in the main central workspace near the system view rather than in a separate right-hand column.

For a requirement, the calculated result and declared criterion are presented together. Expand **Declared limit and source** or **Assumptions and supporting evidence** for the detail you need. Exact engineering quantities, units and evidence remain available. Editing a draft keeps the normal input, preview, save and recalculation workflow; an unapplied draft is not a new calculated finding.

## Connections and controls

Use **Owner settings** for the separate Nebius, Tavily and LangSmith connections and owner metrics. Nebius supplies Nemotron inference; Tavily supplies reference search. LangSmith receives explicitly approved qualification metrics and is not another question-answering model. Ordinary questions and searches stay in the rocket.

Click outside the conversation, press **Escape**, or use its close button to dismiss it. Browser **Back/Forward** may also close it while changing the saved view. Closing does not cancel or repeat an already submitted provider request; reopen the rocket to read its saved outcome. The rocket respects the device's reduced-motion preference.

This milestone changes the interface and access to existing workflows. It does not change numerical solvers, silently start paid investigations/searches, or deliver public hosting.
