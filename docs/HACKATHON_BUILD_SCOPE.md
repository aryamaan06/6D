# Agreed hackathon functional scope

Updated October 24, 2026 from Arya's explicit A–F agreement. This is the complete proposed functional backlog for this submission, not a guarantee of a score or of completing every item by a particular date. UI refinement and the founder walkthrough are separately acknowledged work. Testing defects are fixed within their affected build; new feature letters need explicit scope approval.

| ID | Accepted build | Current position |
| --- | --- | --- |
| A | Integrated rocket reference: coherent existing propulsion, structural, thermal, atmospheric and vertical-flight checks; baseline, flawed revision, correction. | Implemented: visible rocket reference, five supported calculations and an explicit launch-GNC gap; staged baseline/change/correction workflow. See BUILD_A_RESULTS.md. Existing references remain available. |
| B | Bounded guided ascent with horizontal motion and an explicit steering programme. | Implemented: separate bounded planar-ascent adapter, supplied pitch programme, horizontal/vertical histories and connected review. Closed-loop launch GNC remains unassessed. See BUILD_B_RESULTS.md. |
| C | Variable thrust and staging with mass/event handling. | Implemented: serial stages, linear thrust segments, analytical fuel exhaustion, dry-mass separation, ignition delays, profile forms and saved event playback. See BUILD_C_RESULTS.md. |
| D | Whole-project AI investigations across related requirements/evidence gaps. | Implemented: frozen whole-project findings/dependencies/change review, application-owned review queue and guarded qualitative next checks. Requirement scope remains available. Current-source live evidence is one specific changed-rocket case; broader semantic/human validation is pending. See BUILD_D_RESULTS.md. No new Quick/Deep model was enabled. |
| E | Encrypted remembered Tavily/LangSmith connections. | Implemented October 25: separate explicit Windows opt-in, protected key/settings restore, forget/disconnect controls, unchanged accounting and upload consent. Existing optional keys are not silently saved. See BUILD_E_RESULTS.md. |
| F | Hosted access, project/credential isolation and protected judge access. | Preparation implemented/tested October 25: separate invitation gateway, persistent isolated visitor projects, protected controls, server-only optional inference and persistent cumulative/day/session limits; CPU/Caddy deployment package. Actual host/cost approval, public URL/TLS and deployed live checks remain pending. See BUILD_F_RESULTS.md. |

Part1 review actions are documentation/release preparation supporting this scope: correct README, archive stale notes, apply owner-approved license, verify public access, index evidence and assemble Claude's Part2 packet. They do not add G/H features or start a physics build.

Build A supplies the populated hero path. It must not imply that separate orbital/flight or scalar-linked component models form a complete coupled rocket simulation. Broader NASA/ISRO/SpaceX case studies must distinguish documented history, public measurements and constructed reconstructions.

Build D may present a captured failure and a guarded replay, with their actual dates, policies and live/offline distinction. It must not silently promote old Ultra compatibility to current quality qualification. A fallback can only show clearly labelled recorded evidence, never impersonate a fresh response.

Build F must not expose the current local key, shutdown, backup or writable workspace endpoints by changing the bind address alone. No automatic cloud spending or public deployment follows from this plan. Deployment and ongoing operation require a concrete reviewed configuration and an approved budget.

October 25 correction pass is delivered within A–D: faster history verification/copying, consistent status/direction checks and LF checkout consistency. It adds no G/H feature scope. See [correction results](CORRECTIVE_BUILD_RESULTS.md). E is delivered; F preparation is implemented locally and public deployment remains pending. Current-source live qualification must be distinguished from historical AI receipts after these changes.

## October 25 feature freeze

Arya requested that today be the last feature-building day and that the remaining days focus on verification, corrections, interface refinement and walkthrough. [The final audit](FINAL_BUILD_AUDIT.md) recommends completing the existing F deployment without adding G/H or another physics/integration milestone for this submission. A discovered defect is corrected within its existing feature, with evidence retained; the broader future 6D vision remains separate. No public hosting/spend follows from the audit.
