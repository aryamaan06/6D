# Use the clearer review journey

Open [the local workspace](http://127.0.0.1:8768/) and refresh. From **Projects**, open a project to reach its **Overview**. Public deployment is still pending; this guide describes the local workspace.

## Follow the six steps

1. **Design** — inspect or author the project's inputs, model bindings and requirements.
2. **Calculate** — run the supported checks for the saved revision and record a baseline.
3. **Change inputs** — create a draft and edit the appropriate values, units or sources. Preview the affected checks, then save the revision.
4. **Recalculate** — run checks for that saved revision. Inspect which calculations ran and which unchanged evidence was reused.
5. **Review changes** — compare the saved revisions and the requirements affected by the change.
6. **Report** — read the recorded findings, assumptions and unresolved scope; export the saved evidence when needed.

Draft changes are not calculated findings. Save the draft before recalculating. Opening a view does not start a calculation or an AI investigation.

The prepared rocket path reduces thrust from **20,000 N to 11,000 N**, then restores it. Thrust is the engine's pushing force, measured in newtons. These are teaching values for a constructed reference, not fixed limits or recommendations for a real vehicle. Use ordinary **Change inputs** to edit a different value.

## Read the result correctly

| Result | Meaning |
| --- | --- |
| **Meets criterion** | The applicable saved calculation satisfies the declared condition within its stated model and inputs. |
| **Criterion unmet** | The applicable saved calculation misses the declared condition. Inspect its exact value, limit and assumptions. |
| **Not assessed** | Applicable evidence is insufficient to decide, including missing analysis or unresolved numerical uncertainty. This alone does not establish a failed design. |
| **Not calculated** | This saved revision still needs its checks run. |

These findings do not authorize launch or establish whole-mission readiness. Exact engineering values and evidence remain available in the normal review and Assistant views.

## Use Owner settings for services and usage

**Owner settings** keeps three services separate: **Nebius** supplies AI inference, **Tavily** supplies optional reference searches, and **LangSmith** receives explicitly approved qualification metrics. Manage each connection through its own control. Opening settings, selecting a model or connecting a key does not start inference, a search or an upload.

Development usage shows the approved cumulative application allowance, conservative reservations and remaining reservation capacity. These figures are not the provider wallet or a bill. Account figures and investigation diagnostics live here instead of ordinary Assistant conversations and history. Owner tools are unavailable in the hosted reviewer workspace.

## Close popups and preserve edits

Click outside an open dialog or floating action menu, or press **Escape**, to dismiss it. Clicking inside or dragging from inside to outside keeps a dialog open. Edited authoring forms ask before discarding unapplied entries; saved project data and changes already applied to the draft remain intact. Ordinary explanatory disclosures stay open until you close them.

## Understand the Ultra scoreboard

**Owner settings → Fresh Ultra workflow check** shows a separate six-case run. The recorded live result is **6/6 workflow passes**, with six completed and none blocked or untested. These are constructed development cases; completion and limited explanation checks do not establish broad model accuracy, aerospace validity or human semantic approval.

The historical **2/6** remains unchanged: **two completed workflow passes, one blocked explanation and three untested cases**. Untested cases did not fail. The corrected wording check and fresh result do not rewrite that history.

Nano, Super and Ultra remain selectable for individual investigations. The default remains **Super**. A fresh check has its own explicit approval, a ceiling of USD 2.10 and 36 request reservations within the existing allowance, and no automatic retry or default-model change.
