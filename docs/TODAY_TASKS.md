# 6D — Arya's next steps

October 14, 2026. Codex owns engineering implementation, tests and integration. These are founder/setup/review tasks, not a request for Arya to write the core product. Use the original 6D chat and the existing workspace.

## Where to work

- **This original 6D chat:** product decisions, feedback and error/result messages. Codex already edits this project's files from here; no new conversation is needed for today's tasks.
- **VS Code:** open the existing project files and run the commands below in its PowerShell terminal. The installed Codex sidebar can be used for a separately assigned, bounded task later. Official OpenAI documentation describes the IDE extension as a coding interface working with editor context: https://learn.chatgpt.com/docs/codex/ide. This does not require moving our lead build conversation.
- **GitHub:** the private repository is already connected and pushed. No new repository, clone or upload is needed. Codex handles reviewed commits/pushes.

Perform the steps below in order. Paste each command into the terminal, press Enter and wait for it to finish before the next command. If a command errors, stop that terminal sequence and send its error text here; the written interface review can proceed independently.

## 1. Open the existing folder

In VS Code, choose **File → Open Folder**, select:

`C:\Users\Arya\Documents\Codex\2026-10-04\i-a\6d-startup`

Choose **Terminal → New Terminal**. If Git Bash opens, use the dropdown beside the terminal's **+** button and select **PowerShell**. These commands are PowerShell commands. No installation or packages are required. VS Code terminal instructions: https://code.visualstudio.com/docs/terminal/basics.

```powershell
Set-Location -LiteralPath 'C:\Users\Arya\Documents\Codex\2026-10-04\i-a\6d-startup'
$sixdPython = 'C:\Users\Arya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $sixdPython --version
```

Expected: a Python 3.x version, with no error. Keep this same terminal open for the following steps. `$sixdPython` is a shortcut available only in this terminal; if you open a new terminal, run this setup block again.

## 2. Run the offline foundation demonstration

Copy this one line into that terminal:

```powershell
& $sixdPython -X utf8 run.py project-demo
```

Expected constructed examples, in order:

1. `baseline`: `supported_requirements_met` — all six declared requirements are met within their bounded models.
2. `revised`: `requirements_not_met` — the explicitly increased heat input exceeds the supplied thermal limit.
3. `missing_evidence`: `incomplete` — the thermal failure remains visible and the unsupported control requirement is unresolved.

The command saves JSON receipts in `artifacts\projects`. It makes no model requests and costs nothing. This is currently a backend demonstration; the new product screens are proposed in SCREEN_SPEC.md. When all three expected cases appear and the `PS ...>` prompt returns, continue. Report `Offline demo: completed` or the error text; there is no need to paste the entire JSON output.

## 3. Check the private-key configuration — no inference

Completed prerequisites: Arya confirmed $29.50 usable balance, active `6d-local-development`, exact routing ID `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, and console prices $0.06 input / $0.24 output per million tokens. The selected model's official license and API tool-calling documentation were reviewed. `.local\token-factory.json` is configured for the already-approved $5 cumulative initial test allowance; it contains no key. Remote access/model behavior remain untested.

First inspect configuration through the private helper:

```powershell
& $sixdPython -X utf8 tools/with_token_factory_key.py provider-status
```

At `Token Factory key (hidden, local only):`, paste/type **only your API key in that local terminal**, then press Enter. No letters or asterisks appear; that is expected. The helper keeps it in its own process environment and writes no key file. Expect `"configured": true`, the exact routing ID and `"live_calls_made": 0`. The note correctly says remote access is not yet tested. This command makes no inference request. If `configured` is false, send the printed `note` and stop before the live command.

## 4. Read the constructed example contract — no inference

Review the constructed Euler contract before acknowledging it:

```powershell
& $sixdPython -X utf8 run.py contract --case euler_method_limit
```

Expected: the example's assumptions followed by `Contract SHA-256`. This example deliberately uses a first-order numerical method with known limitations. The demonstration should distinguish that limitation from a code defect. Read it as a supplied constructed example; your acknowledgment applies to that example, not a real spacecraft design. If a field is unclear, send its name so Codex can explain it.

## 5. Run one live Nano investigation

Then run **one** live investigation under the existing allowance:

```powershell
& $sixdPython -X utf8 tools/with_token_factory_key.py investigate --case euler_method_limit --provider token-factory --accept-contract
```

Enter the key privately again. This command sends actual model requests to Nebius and reserves spending before each one. A normal sequential run needs about three completions, with at most four. The $5 allowance is cumulative across runs through this adapter, not $5 for each run. Keep `.local\budget.sqlite3`; deleting it would erase the local spending history. No additional card spending is authorized.

Allow the command to finish; several model requests may take a few minutes. Expected success markers are `6D: Method limitation`, `Provider: live_token_factory`, a positive `Live model calls` count, `Investigation: completed`, and an `Evidence JSON` path. `Live request attempts` is printed separately; `Live model calls` counts accepted provider responses. These are test expectations, not a promise that a model run succeeds.

Copy only those printed lines into this chat. If it fails, send the safe error text and the evidence path if one is shown; do not repeatedly retry. The saved receipt lets Codex inspect actual tool selections and usage without receiving your key. A numerical headline alone does not mean the AI investigation completed; include its state. Configuration alone does not prove live integration.

October 14 diagnostic update: the first live run failed before a response was accepted. Codex fixed error classification and verified 130 tests offline. After that fix, run this step once again in the existing configured workspace so a new receipt can show the classified cause or completion. No re-creation of the key/configuration, ledger reset or budget increase is needed. Send `Live request attempts`, the accepted call count, investigation state, error and new evidence path.

## 6. Review the proposed product experience

In VS Code's left Explorer, expand **docs** and open **SCREEN_SPEC.md**. Read the visual direction, proposed screens and evidence states. This is a written screen proposal, not the new website yet; no terminal command or key is required.

Review the clarity and your Apple/Notion preference, not the correctness of spacecraft equations. Return concrete issues or say the direction works for you:

```text
Confusing wording:
Navigation order:
Too crowded:
Overall design direction:
```

For a clearer explanation of your added visual feature, read **docs → SIMULATION_PLAYBACK.md**. It records the planned model-linked simulation feature; it does not claim playback is already built.

## 7. Send a compact result update here

You may report each task as you finish it, or use this template. Do not put the key in the update:

```text
Offline demo: completed / error
Provider status: configured true / false
Live investigation: completed / error / not run yet
Live model calls:
Evidence JSON path:
UI feedback:
```

Codex then inspects the receipt, fixes any integration issue, and continues the supported project journey/interface work. Git setup and the 115-test fresh-checkout verification are already completed; Arya does not need to repeat those tasks.

## Optional independent review using Antigravity

Use the Gemini Pro model already available to you. Open this same folder and paste the entire prompt below. This task is read-only, so it will not conflict with Codex's implementation. Return the short structured result, not the tool transcript.

```text
Review 6D's proposed first product journey for clarity and honesty. Do not edit files, run commands, access credentials, contact external services, or redesign the architecture. Read AGENTS.md, PROJECT_BRIEF.md, docs/BUILD_PLAN.md, docs/SCREEN_SPEC.md and docs/TODAY_TASKS.md in this folder. Check whether a non-specialist can understand what to provide, what is actually checked, what an unmet or unresolved requirement means, and which capability is implemented versus planned. Identify the three most consequential improvements, with the affected screen and a concrete wording/flow change. Do not assess unprovided customer traction or award speculative hackathon scores. Output only: Issues (maximum three), Suggested changes, and Any contradiction. Keep the response under 250 words. If there is no important issue, say so; do not invent one.
```

No new Codex model selection is required for today's terminal/file-review tasks. Continue the lead build here. If a separate coding/review session is assigned later, Codex will provide its scoped prompt, model and effort setting.

## Later founder tasks

Codex prepares a reviewer shortlist and a concise feedback request; Arya chooses whom to contact. Codex also prepares the deployment/repository/license package and video script; Arya reviews concrete publication/company decisions and records the demo when ready. No outreach, new cloud spending or new account setup is needed for today's foundation check.
