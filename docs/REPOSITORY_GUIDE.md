# Reading the repository

Start with the [README](../README.md) for the product and local setup, then [CURRENT_STATE.md](CURRENT_STATE.md) for the implemented scope and outstanding gaps. The repository retains development evidence; it is not necessary to read every milestone to try the application.

| If you want to… | Open |
| --- | --- |
| Run or refresh the application | [Opening instructions](OPEN_6D.md) |
| Understand what works today | [Current application state](CURRENT_STATE.md) |
| Inspect the latest conversation/scrolling correction | [Interface and investigation results](CHAT_READABILITY_RESULTS.md) |
| Assess evidence and its limits | [Validation index](VALIDATION_INDEX.md) |
| Find a particular source/test/guide | [Documentation index](DOCUMENTATION_INDEX.md) |
| Inspect the engineering adapters | [`src/sixd/engineering.py`](../src/sixd/engineering.py) and the individual adapter modules |
| Inspect revision/recalculation behavior | [`src/sixd/workspace.py`](../src/sixd/workspace.py) and [`src/sixd/lifecycle.py`](../src/sixd/lifecycle.py) |
| Inspect the AI contract | [`src/sixd/project_investigation.py`](../src/sixd/project_investigation.py), [`src/sixd/whole_project_investigation.py`](../src/sixd/whole_project_investigation.py) and [`src/sixd/workspace_ai.py`](../src/sixd/workspace_ai.py) |
| Review hosting preparation | [Deployment guide](HOSTED_DEPLOYMENT.md) and [recorded checks](BUILD_F_RESULTS.md) |
| Audit the project's development | [Chronology](PROJECT_RECORD.md), [changelog](CHANGELOG.md) and [older planning records](development/README.md) |
| Check reuse rights | [MIT license](../LICENSE) and bundled third-party notices |

## Current versus historical records

Build reports, test counts, screenshots and live-model outcomes describe their stated date, case set, source identity and configuration. A statement such as “current-source” inside an older report means current **at that checkpoint**. Use the current-state page and validation index before applying it to a newer build.

Earlier failures are retained deliberately. Removing them would conceal useful information about protocol compatibility, guards and spending. Historical files are linked behind the current overview rather than deleted or presented as today's setup instructions.

The published-file inventory has an immutable baseline commit. Its counts are not the current repository's totals. Git history remains the source for later changes.

## Private local state

Owner databases, credentials, raw private provider records and working captures are excluded from Git. Public result summaries retain only reviewed provenance, diagnostics and scoped outcomes. A committed synthetic screenshot or recorded response is labelled as such; it is never proof of a new live request.

Contributor instructions remain in the conventional root [AGENTS.md](../AGENTS.md). Runtime source is under `src/sixd`, tests under `tests`, and local setup/check tools under `tools`.
