# 6D Space — agreed product brief

Updated October 14, 2026. Internal hackathon checkpoint: October 21, 2026, Asia/Calcutta.

Current execution state: Arya explicitly restarted the build on October 14 after feature organization and competitor discussion. docs/BUILD_PLAN.md defines the active build sequence and founder tasks; docs/FOUNDATION_BUILD.md defines the first backend interface. The previous October 13 interruption saved no application code. UI implementation follows a reviewable screen/wording specification. Initial live inference remains subject to usable account/configuration checks and the existing $5 allowance; no additional card spending is authorized.

Call the single startup product **6D**. docs/PRODUCT_FEATURES.md is the intended feature catalogue, distinguishing functional capabilities, engineering disciplines and demonstrated coverage. The full startup product is the development objective; the hackathon is a snapshot of working, validated capabilities, not the definition of the product. Differentiation must be measured in useful verification work, false accusations, review effort and reproducible evidence rather than presumed from the feature list.

## Product and scope

6D is a space-sector engineering assurance application. It helps spacecraft and space-system teams connect design assumptions, versioned numerical models, software and physical test evidence to reviewable engineering findings. When a design or model changes, it helps determine which evidence still applies, which checks need repeating and what remains unknown.

Agreed during the October 13 voice conversation: 6D is lifecycle space-engineering assurance, with design-stage review as its first working workflow. Before construction, review requirements, mission plans, specifications, subsystem interfaces, assumptions and available models to identify supported design inconsistencies, unmet requirements, potential failure mechanisms and missing verification. As physical testing becomes available, connect measurements to the relevant design version, requirements and test conditions, compare predictions with observations, and investigate discrepancies. After revisions or during operation, identify affected evidence and required follow-up review. These stages use the same platform and records; design-stage assistance is the starting point, not the permanent boundary. A sketch alone cannot support a comprehensive numerical conclusion. Report what is supported, what fails and what remains unresolved under declared conditions; never classify an entire rocket as perfect or guarantee mission success. Breadth-versus-depth demonstration choices do not change this general product objective.

The company is strictly space-only. The full future vision may include spacecraft propulsion, structures, thermal behavior, electronics, software, assembly, environmental qualification and interactions across space-system development and operation. There is no planned expansion into unrelated industries.

October 13 product clarification: 6D must be a general space-engineering assistant, able to adapt to different rocket architectures and other space systems rather than being a separate product for reusable rockets, Earth launch/landing, satellites or the Floating Coliseum. Vehicle and mission descriptions determine applicable requirements, models and evidence internally. Users should not need to choose a narrow product category before receiving assistance. Broad assistance is the objective; a quantitative finding still requires a supported, validated model and adequate inputs, with unsupported coverage explicitly unresolved. Floating Coliseum remains Arya's long-term project, not the exclusive definition of 6D or an automatically selected first implementation case.

Arya's October 13 voice decision makes the complete future platform the primary development objective starting now. Build one expandable startup product with shared requirements, model versions, dependencies, evidence and review workflows. The hackathon is a checkpoint: submit whichever capabilities are working and validated when the package is due, then continue the same product. Competition scores and winning do not define the startup's scope. The complete platform still requires multiple stages; do not claim complete launch-to-landing coverage can be finished by October 21.

October 14 clarification: all engineering areas in docs/PRODUCT_FEATURES.md remain in the full product development plan, with tools and specialist integrations implemented and validated progressively. Arya added simulation and visual playback: show how a supplied design is predicted to behave under declared conditions through supported model runs, plots and appropriate 2D/3D playback. This feature is now explicit in docs/SIMULATION_PLAYBACK.md; it is planned, not implemented. It can contribute evidence before a positive design review and be inspected afterward. Link every quantitative display to its actual run and project revision; an illustrative animation must not be presented as an engineering prediction.

## Founder and working relationship

Arya is the CEO, a student with beginner-to-intermediate Python knowledge. The assistant owns initiative on research, architecture, software implementation, validation and delivery. Explain decisions clearly. Complete reversible authorized local work without repetitive confirmation. Customer understanding and company decisions remain with Arya. No customer traction, revenue, investment, validated pricing or domain credentials are established.

## Near-term implementation baseline

The bounded capabilities below remain the existing starting plan and known implementation gaps, rather than a permanent ceiling or a promise that all will be finished by the checkpoint. Further disciplines can enter development once their inputs, models and validation are defined. Design the shared foundation for the full future scope, while keeping every advertised capability tied to actual supported evidence. The founder is continuing to explain the full vision; this strategic decision does not itself authorize speculative UI changes, paid requests or public release.

Proposed early-user hypothesis: a technical lead or mission-analysis engineer at a small spacecraft team or specialist space-engineering consultancy. This is a customer-validation starting point, not a restriction on vehicle types in the product architecture.

Arya expanded the initial implementation target on October 11 to include bounded orbit, propulsion, structures and thermal screening. As of October 14, four deterministic design adapters (ideal propulsion, static cantilever, radiative equilibrium and drag load) and the shared requirement/evidence foundation are implemented. The constructed revision demonstration uses explicit supplied changes; it is not an actual maneuver or coupled-spacecraft simulation. See docs/FOUNDATION_BUILD.md and docs/BUILD_PLAN.md for the current interface and sequence. docs/RELEASE_BLUEPRINT.md remains the earlier specification context.

October 13 scope decision: add a bounded aerodynamic pressure/drag-load check when an explicit atmospheric scenario and applicable data are supplied. That formula adapter is now implemented, with coefficient/flow applicability explicitly unverified. Full GNC simulation is not yet implemented; an unsupported control requirement remains unresolved in the demonstrated project review. The implemented steady-state radiative check does not predict aerothermodynamic heating. Avionics and embedded flight-software evidence integration remain later product capabilities, not advertised current coverage.

Core journey: provide a supported model/configuration and assumptions; review and lock its requirements and contract; let a Nemotron agent select supported independent checks; inspect the results and their sources; identify affected evidence after a revision; rerun the relevant checks; reproduce or export a report with explicit exclusions.

Space-specific numerical verification is the first entry hypothesis. Its usefulness, differentiation and willingness to pay must still be tested against customers' current workflows and relevant tools. The first release is engineering analysis assistance, not flight certification or launch authorization.

## Architecture commitments

- Model reasoning interprets descriptions, requests necessary clarifications, chooses supported investigations and explains recorded evidence.
- Use one vehicle-adaptive interface and shared requirements/evidence engine. Select applicable domain tools from the user's vehicle, mission and supplied models; mission profiles are internal applicability mappings, not separate products. Example vehicles establish test coverage rather than defining permanent product limits. Avoid presenting assistance with any vehicle as established quantitative verification of every vehicle.
- A maintained deterministic kernel and independent reference methods produce quantitative results and supported verdicts. Model prose cannot invent evidence or override the kernel.
- Each audit preserves inputs, units, reference frames, method assumptions, source versions, reproduction steps and a mandatory not-tested list.
- Distinguish likely defects, numerical-method limitations, inconclusive evidence and no defect found within supported checks.
- Retain prior evidence when requirements or inputs change. An old report must not appear to cover a different configuration.
- Use curated or explicitly supported model adapters initially. No arbitrary public code execution is promised.
- Keep inference providers replaceable. Use actual NVIDIA inference on Nebius for the hackathon demonstration; fixtures must be visibly labeled and cannot stand in for the required live integration.
- Four core bounded domain adapters plus conditional aerodynamic-load screening are the initial implementation baseline. Full GNC simulation, aerothermodynamic heating prediction, avionics/flight-software evidence integrations, guarded patching, CAD/FEA integration, broader document ingestion and extra orbit families remain future work, not implemented coverage or permanent exclusions. Prioritize further work against the full startup vision once its specifications and validation are established. Track uncovered dependencies explicitly. Each advertised capability must pass its own acceptance gates; preserve end-to-end reliability and label unfinished work honestly.
- The agreed design direction combines Apple's presentation/polish with Notion's calm workspace organization. Define screens, language and evidence states before final UI implementation.

## Existing implementation to preserve

Location: C:/Users/Arya/Documents/Codex/2026-10-04/i-a/6d-startup.

The preserved orbital implementation contains a standard-library Python kernel for planar circular point-mass orbits, five constructed examples, contract review, independent force/reference/refinement and applicable reversibility checks, JSON/HTML evidence records, reproduction/comparison commands and a loopback web UI. The browser compares saved audits' assumptions, source versions, verdicts, check statuses, changed measurements and exclusions. October 11 browser/mobile checks remain earlier development receipts; the browser was not changed in the October 14 foundation increment.

The October 14 backend increment adds strict structured project intake, the four bounded adapters, requirement findings, preserved evidence receipts and explicit revision dependency comparison. Verification-source changes invalidate earlier applicability even without a manual version bump. An independent review caught a propulsion cancellation edge case; the fix and regression cases are included. All 115 integrated tests passed. The orbital force probes cover axes/quadrants and the declared Verlet contract now also checks reversibility, catching the previously reproduced RK2-method mismatch. This is not proof of the exact stepping algorithm. Agent state is recorded separately from numerical findings; a passing numerical headline does not imply a completed AI investigation.

The first private-terminal live attempt on October 14 recorded one request attempt and zero accepted responses, with an empty tool trace and a failed investigation. Independent kernel findings still matched the expected Euler method limitation. The previous generic error hid the cause; it is not recoverable from that receipt. Safe error categories and separate request-attempt console output are now implemented, with all 130 offline development tests passing. The original receipt and $0.00132948 conservative reservation are preserved; that reservation is not a provider invoice. No further live request was made by Codex during the fix. Current account/model/pricing gates are configured; an actual completed live investigation remains the integration gate. See docs/LIVE_INTEGRATION_STATUS.md.

The classified follow-up on October 14 identified `finish_reason=length` with a 1,024-token cap and no accepted tool response. The targeted correction increases the local Nano completion allowance to 8,192 tokens and the request timeout to 180 seconds, retaining the same model/endpoint/prices, $5 cumulative cap and previous ledger. All 140 tests passed offline; successful live completion remains to be demonstrated. Antigravity's intake, unimplemented-control and findings-clarity feedback is incorporated in docs/SCREEN_SPEC.md. The new UI and simulation playback are still planned, not implemented by these documentation/configuration changes.

Latest integration checkpoint, October 14: the larger allowance produced one accepted live response (1,035 prompt / 3,308 completion tokens), confirming provider access for that request. The first selected check had nonempty arguments, so the old runner stopped before executing it. The correction offers only unfinished checks, constrains finish to recorded evidence, rejects invalid batches before execution and allows one controlled format correction within five turns. Parameter values and model prose are not retained as evidence. The final kernel audit, contract lock and cumulative $5 ledger remain authoritative. All 159 offline tests passed, including 19 recovery/accounting/report tests and an independent read-only implementation review. A completed live agent receipt is still pending; no paid inference was made by Codex during this fix.

Current provider checkpoint: the next receipt again truncated with an 8,192-token allowance before any accepted tool response. The prior generic sampling configuration did not follow NVIDIA's recommended Nano tool-calling sampling pair; this is a plausible contributor, not a measured cause. Native and API thinking controls are now explicit compatibility profiles rather than assumed supported behavior. The new verify-live session enters the key once, tests up to three profiles under a $0.10/15-request session ceiling within the same $5 ledger, and adopts a profile only after both constructed Euler and force-defect investigations complete with verified independent evidence. Safe failed-response usage is retained separately from accepted calls. All 197 tests passed offline; actual live success remains pending. Follow docs/LIVE_VALIDATION.md instead of repeated manual investigate retries. No paid request was made by Codex during this correction.

On October 14 Arya reconfirmed a $29.50 balance and active `6d-local-development`, exact routing ID `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, and current console prices $0.06 input / $0.24 output per million tokens. The selected model's official license and API tool-calling documentation were reviewed. Nonsecret `.local/token-factory.json` is configured for the already-approved $5 cumulative initial live inference from existing balance only, with no additional card spending. No credential value is recorded in project files. The selected paid-usage preference can charge the linked card after a negative balance; it does not authorize those charges. Remote authentication/model behavior and any credit expiry are not established by local configuration. Independent evaluation, public hosting, licensing/repository publication, video and submission materials remain to be delivered. Follow docs/TODAY_TASKS.md for the privately entered, capped live test.

Useful files: README.md, src/sixd, tests, docs/VERIFICATION_SCOPE.md and docs/FIRST_INCREMENT.md. Preserve the working code; replace obsolete context rather than rebuilding the same foundation.

## Hackathon and startup

Use one space-only 6D product for the startup and the Nebius/NVIDIA Best Apps and Agents demonstration. The founder's internal readiness target is October 21; the official competition deadline remains October 30. Keep the competition subordinate to product usefulness. A working hosted demo, public functional repository with an open-source license, setup instructions, public video under three minutes, description, evaluation evidence and provider feedback form the release package.

The public repository must include all necessary submitted functionality. Prepare a concrete publishable package before asking for any unresolved publication approval. Respect actual account permissions, model licenses and provider spending constraints. The only approved runtime allowance is the $5 initial inference cap described above. No outreach messages, additional charges, purchases or deployment credentials are authorized through this brief. Do not assume available promotional credits cover commercial production. Arya requested help finding a relevant engineering reviewer; none has yet agreed.

## Competition

Most broad engineering vendors also serve the space sector. Flow Engineering already has space customers and change/requirements/test workflows with agents and human review. Ansys offers dedicated mission tools and cross-domain spacecraft analysis workflows. Siemens and Jama also serve space programs. Epsilon3 explicitly offers spacecraft engineering, test and operation software. Space-only positioning does not remove these competitors.

Demonstrate an advantage in a specific supported verification task: evidence quality, problems discovered, setup effort, reproducibility, integration or economics. Do not claim generic incumbents lack space knowledge, independent checks or AI. Vendor descriptions are capability claims, not independently measured performance.

## Tools and usage plan

Use one codebase and one lead build chat. Codex handles core implementation and integration. The VS Code Codex extension is another surface for that same work, not an extra independent usage allowance. Gemini/Antigravity can handle scoped research, browser testing and independent review; avoid concurrent edits to the same files or competing architecture rewrites. Google Cloud is optional hosting after actual credits, account access and billing are checked. Runtime model calls for the competition remain NVIDIA on Nebius.

Repository setup, October 14: Arya created `https://github.com/aryamaan06/6D.git` and supplied it for connection. Authenticated metadata confirmed it is private and writable. The existing 6d-startup workspace is initialized as Git on `main`, with that URL as `origin`; no duplicate product folder is created. Repository-local commit identity uses the GitHub username and verified account-ID no-reply address. Track reviewed source, tests, examples and development documentation; exclude credentials, `.local/`, generated reports/work and caches. Local development continues in the same folder, with reviewed commits pushed to GitHub. This is private storage, not authorization to publish the startup repository or select its eventual public-submission license.

The account check on October 10 showed three available full reset credits and about seventy-nine percent of the current weekly allowance remaining. This is a snapshot, not a promise that those allowances suffice. Use resets only when actually needed; prioritize a working core, reliability and submission readiness. Preserve compact task briefs and evidence files rather than repeatedly sending full historical conversations.

## Context discipline

Arya explicitly chose the original conversation as the main build chat on October 11; its title is now **6D**. The separate build chats are archived. Continue implementation here and do not create another chat unless Arya requests it. Use this brief and RELEASE_PLAN.md to preserve current scope. Refer to 6D only. Historical investor materials remain proposals, not proof of current features or demand.

## Primary references

- https://nebiusglobalaihackathon.devpost.com/rules
- https://www.flowengineering.com/customers
- https://www.flowengineering.com/product/branching
- https://www.epsilon3.io/space-industry
- https://docs.nebius.com/serverless/overview
- https://learn.chatgpt.com/docs/projects?surface=app
