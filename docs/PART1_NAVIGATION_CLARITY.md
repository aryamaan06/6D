# Part 1 — navigation and clarity

October 26, 2026. Refresh **http://127.0.0.1:8768/** to see the current local delivery. The verified build identity and checks are in [delivery results](PART1_NAVIGATION_CLARITY_RESULTS.md).

## Pages begin at the top

Opening another work page, project or saved revision begins at its heading. In particular, **Overview → Review map → Open review report** now opens the beginning of the report rather than carrying over the Overview's scroll position.

Accepted browser Back/Forward changes also begin at the destination heading. Selecting an item, typing or refreshing within the same work page does not trigger a page-level scroll reset. Existing explicit actions that reveal a selected record can still bring it into view. Cancelled draft/profile navigation retains the current context, edits and position. The route controller temporarily owns scroll restoration while mounted so browser restoration does not compete with these rules.

## Component names stay in choices

Simplified labels now rewrite metric phrases while keeping the surrounding component, stage and load-case words. **Battery maximum temperature** and **Engine maximum temperature** remain distinct, as do different structural-stress or fuel-margin checks. Only the display label changes; exact requirement/finding/assumption IDs and Advanced labels stay intact.

This is not automatic interpretation of a vague project definition. Two identically named supplied requirements still need clear source titles. Search topics retain their exact engineering target, including saved finding and model-assumption identities.

## Calculation results and model fit are different questions

Overview's numerical cards still show the exact recorded requirement findings. A separate **Coverage and model applicability** panel explains the declaration/analysis gaps and links to **Review declarations & model fit**.

For the current constructed rocket, nine numerical criteria are met and one is unassessed. Its ten scope checks still need attention: nine lack a model-fit declaration and one lacks supported analysis. These are separate dimensions, not contradictory pass totals. Coverage may also include additional checks beyond the project requirements.

To review a gap, follow the coverage action and inspect the linked requirement, mission phase, assumptions and supporting evidence. Supply a fit/exclusion rationale only when justified; leave fit unknown when evidence is insufficient. A supplied fit declaration is unverified engineering context. It does not change the numerical finding, establish model validity or imply permission to launch.

## Tool status follows the selected saved revision

Engineering/analysis cards and their contextual navigation now distinguish:

- **Recorded calculation:** the selected saved revision has a matching completed model result. Open the tool to inspect its criteria, assumptions and numerical accuracy.
- **Configured · not calculated:** a model is declared but no matching completed calculation is recorded here.
- **Configured · calculation blocked:** recorded inputs/analysis prevented the calculation from completing or assessing the case.
- **Recorded calculation · partial:** some configured models have completed results; others still need attention.
- **Not configured for this project:** the tool is available, but this selected project does not define its model yet.

Historical revision badges retain their own revision identity. Older/stale receipts do not become current recorded evidence. Draft edits are explicitly separate from the saved status. An unsupported launch-GNC placeholder does not count as a supported single-axis pointing model.

Tools remain accessible to configure or inspect examples; navigation does not add models, create projects or calculate automatically. A completed calculation is not itself a passing requirement or a complete mission assessment.

This part preserves numerical models, saved receipts, the three-model AI choice, manual reference save/link steps, remembered connections and spending controls. Part 2 organization/precision/unit polish and Part 3 companion/context refinements remain separate, unstarted corrections. [Acceptance](PART1_NAVIGATION_CLARITY_ACCEPTANCE.md)
