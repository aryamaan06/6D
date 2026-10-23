# References in the Assistant and optional research

The source-connected workflow is available at http://127.0.0.1:8768/, build `9000326228b7`. Local reference editing and numerical checks work without an AI or search connection.

## Explain a saved finding with references

1. In **Source library**, save a reference and explicitly link it to a requirement, a saved finding or one of the bound model's assumptions.
2. Select that requirement in Canvas/Table and open **Investigate**.
3. Choose **Ask about linked references** to fill a source-focused question. This button makes no inference request.
4. Review the question and connection status, then explicitly start the investigation when live inference is intended. The existing Nebius allowance and per-job limit still apply.
5. Open **References captured for this investigation** in the saved result. Check the pinned versions, excerpts, link rationale, review flags and omissions alongside the separate calculated evidence and AI commentary.
6. For a current unmet or unassessed finding, **Track follow-up for this finding** opens the existing action form. Review and save the task explicitly. Creating or closing a task does not change the engineering finding.

Each new investigation captures its relevant reference links and saved review in one database snapshot. Later reference edits do not replace that captured material. Older investigations are preserved without current references being added to them.

Capture includes the selected requirement/finding and its bound model's explicitly linked assumptions. Unrelated and upstream-model reference links are not implied to have been reviewed. At most eight whole links and 32 KiB are included, with omission counts. A stale reference remains stale supplemental context; it cannot satisfy an unsupported criterion.

## Find another reference

1. Open **Source library** and scroll to **Find additional references**.
2. Expand **Optional Tavily connection**. Enter the key privately and choose an absolute cumulative app search allowance. Connecting makes no search call. The key remains in server memory until disconnect or restart; prior reservations remain saved.
3. Select an engineering context and type the public query you intend to send. Only that entered query and fixed search options go to Tavily; project data is not attached automatically.
4. Choose **Search references · 1 credit expected**. One Basic request returns at most five results. There are no automatic retries, generated answers, extraction or crawling.
5. Choose **Review reference before using**. Inspect the title, URL and unverified excerpt. **Use in source form** fills the unsaved reference editor; it does not save or link anything. A busy form retains the preview.
6. Review/edit the source form, choose **Save reference**, then select the saved reference and target and choose **Add explicit link**. Search provenance is retained in the source details.

Draft and historical views cannot initiate searches or use previews to create references. Saved research history remains inspectable. A failed or interrupted attempt retains its prospective reservation and never retries automatically. Refresh saved searches before deliberately submitting another request after an interrupted response.

The initial app ceiling is twenty cumulative Basic-search reservations; reconnecting or restarting does not reset the count. Provider-reported usage above the expected request reservation is preserved and pauses further research across reconnects/restarts, pending provider/account review. The app's accounting is not your Tavily balance, billed usage or a provider-account billing control. The fixed request follows the [official Tavily search API](https://docs.tavily.com/documentation/api-reference/endpoint/search) and [credit documentation](https://docs.tavily.com/documentation/api-credits).

## Evidence limits

References are untrusted supplemental text. Search ranking, linking, source review and a completed AI explanation do not establish source authenticity, numerical correctness, model applicability or mission readiness. Instructions and numbers in excerpts cannot authorize tools or replace calculated evidence. The existing application-owned numerical evidence and prose guards remain in effect; they are bounded checks, not complete semantic verification.

The delivered workflow has been verified with isolated synthetic transports. Actual Tavily and the new source-aware Nemotron behavior still require a connected, bounded live evaluation. LangSmith tracing is a following milestone. No real key or credit is required to inspect the interface or stored engineering results.
