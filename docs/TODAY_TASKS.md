# 6D — Arya's next steps

October 14, 2026. Codex owns engineering implementation, tests and integration. These are founder/setup/review tasks, not a request for Arya to write the core product. Use the original 6D chat and the existing workspace.

## 1. Open the existing folder

In VS Code, choose **File → Open Folder**, select:

`C:\Users\Arya\Documents\Codex\2026-10-04\i-a\6d-startup`

Choose **Terminal → New Terminal**. Use PowerShell. The verified bundled Python needs no installation or packages.

```powershell
Set-Location -LiteralPath 'C:\Users\Arya\Documents\Codex\2026-10-04\i-a\6d-startup'
```

## 2. Run the offline foundation demonstration

Copy this one line into that terminal:

```powershell
& 'C:\Users\Arya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 run.py project-demo
```

Expected constructed examples, in order:

1. `baseline`: `supported_requirements_met` — all six declared requirements are met within their bounded models.
2. `revised`: `requirements_not_met` — the explicitly increased heat input exceeds the supplied thermal limit.
3. `missing_evidence`: `incomplete` — the thermal failure remains visible and the unsupported control requirement is unresolved.

The command saves JSON receipts in `artifacts\projects`. It makes no model requests and costs nothing. This is currently a backend demonstration; the new product screens are proposed in SCREEN_SPEC.md. Tell Codex whether it completed or paste the error text. There is no need to paste the entire JSON output.

## 3. Run the first capped live integration check privately

Completed prerequisites: Arya confirmed $29.50 usable balance, active `6d-local-development`, exact routing ID `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, and console prices $0.06 input / $0.24 output per million tokens. The selected model's official license and API tool-calling documentation were reviewed. `.local\token-factory.json` is configured for the already-approved $5 cumulative initial test allowance; it contains no key. Remote access/model behavior remain untested.

First inspect configuration through the private helper:

```powershell
& 'C:\Users\Arya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 tools/with_token_factory_key.py provider-status
```

At the hidden prompt, paste/type your API key **in that local terminal**, then press Enter. Nothing is displayed while entering it. The helper keeps it in its own process environment and writes no key file. Expect `configured: true`, the exact routing ID and a note that remote access is not yet tested. This command makes no inference request.

Review the constructed Euler contract before acknowledging it:

```powershell
& 'C:\Users\Arya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 run.py contract --case euler_method_limit
```

This example deliberately uses a first-order numerical method with known limitations. The demonstration should distinguish that limitation from a code defect. Your acknowledgment applies to this constructed example, not a real spacecraft design.

Then run **one** live investigation under the existing allowance:

```powershell
& 'C:\Users\Arya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 tools/with_token_factory_key.py investigate --case euler_method_limit --provider token-factory --accept-contract
```

Enter the key privately again. This command sends actual model requests to Nebius and reserves spending before each one. A normal sequential run needs about three completions, with at most four. The $5 allowance is cumulative across runs through this adapter, not $5 for each run. Keep `.local\budget.sqlite3`; deleting it would erase the local spending history. No additional card spending is authorized.

Share only the printed engineering headline, provider mode/live-call count, investigation state and `Evidence JSON` path. If it fails, send the safe error text and wait for a fix instead of repeatedly retrying. The saved receipt lets Codex inspect actual tool selections and usage without receiving your key. A model may fail this initial compatibility test; configuration alone does not prove live integration.

## 4. Review the proposed product experience

Open `docs\SCREEN_SPEC.md`. Give feedback on labels, navigation, reading order and anything that feels confusing or crowded. It follows the agreed Apple/Notion direction. Codex will implement and verify the new UI after this concrete review.

## Optional independent review using Antigravity

Use the Gemini Pro model already available to you. Open this same folder and paste the entire prompt below. This task is read-only, so it will not conflict with Codex's implementation. Return the short structured result, not the tool transcript.

```text
Review 6D's proposed first product journey for clarity and honesty. Do not edit files, run commands, access credentials, contact external services, or redesign the architecture. Read AGENTS.md, PROJECT_BRIEF.md, docs/BUILD_PLAN.md, docs/SCREEN_SPEC.md and docs/TODAY_TASKS.md in this folder. Check whether a non-specialist can understand what to provide, what is actually checked, what an unmet or unresolved requirement means, and which capability is implemented versus planned. Identify the three most consequential improvements, with the affected screen and a concrete wording/flow change. Do not assess unprovided customer traction or award speculative hackathon scores. Output only: Issues (maximum three), Suggested changes, and Any contradiction. Keep the response under 250 words. If there is no important issue, say so; do not invent one.
```

In Codex, keep the current model for this build. If selecting settings for a separate scoped coding/review session, GPT-6.1 Sol with High is a reasonable default; harder architecture questions can use a higher effort selectively. This is a work-setting recommendation, not a required new purchase. Official model capabilities: https://developers.openai.com/api/docs/models/gpt-6.1-sol.

## Later founder tasks

Codex prepares a reviewer shortlist and a concise feedback request; Arya chooses whom to contact. Codex also prepares the deployment/repository/license package and video script; Arya reviews concrete publication/company decisions and records the demo when ready. No outreach, new cloud spending or new account setup is needed for today's foundation check.
