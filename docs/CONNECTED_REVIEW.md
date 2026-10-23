# Connected review and interface polish

Local delivery October 24, 2026 · build `33affdca8bf9`.

Refresh http://127.0.0.1:8768/. **Review overview** is now the opening view. It
captures the selected saved project's findings, scope declarations, follow-up
context and bounded evidence history in one read snapshot. Opening it runs no
calculation or model request.

## Follow the review

1. Confirm the project and saved revision in the sidebar. The overview identifies
   the captured calculation, latest/historical revision and any earlier retained
   calculation. An uncalculated revision never borrows earlier numerical passes.
2. Read the separate counts for met criteria, unmet criteria and unassessed
   requirements. With no current calculation, these show no result; requirements
   are labelled **Not calculated**. An empty setup points to authoring.
3. Filter or search requirement findings. Select a row for its exact reason,
   assumptions and exclusions. **Open requirement inspector** hands the same
   requirement to the existing evidence panel.
4. Follow the review map to design, coverage, calculation links, available saved
   simulation, imported histories, studies, follow-up actions, sources or the full
   report. Every handoff preserves the saved project/revision context.
5. Return through **Review overview** in the sidebar. Refresh its snapshot
   explicitly after changes made elsewhere. A mismatched project/revision/run
   response is rejected and offers retry or saved-context reload.

The sidebar now groups the system hierarchy, engineering tools, review/evidence
tools and project setup. The top **Analysis tools** menu contains orbital
simulation, scenarios, envelope studies, simulation imports and scalar test data.
Native keyboard navigation opens the menu; Escape closes it. Canvas/Table/Reader,
draft editing, changes, original module views and the full report remain available.
**Guided review** opens the existing change walkthrough from the system view.

## Display and context

SI powers are shown as superscripts, including m/s², kg/m³, m⁴ and negative
integer powers. Saved input units use formatted labels. Editing uses the exact
original unit token; raw form values, CSV, JSON, exports, source quotations and
technical provenance remain unchanged. This is display notation, not conversion.

Draft warnings explicitly state that overview evidence belongs to the saved
revision. The overview does not start draft calculations or change findings.
Historical revision controls do not create a new calculation from this review
page. Metadata and counts are captured together; supplemental coverage/action/
source records are not represented as having been part of the original numerical
run. Coverage declarations and action closure never become numerical passes.

Desktop/mobile layouts use the same recorded content. Wide findings tables scroll
inside their container. Counts are record counts, not percentages of whole-vehicle
verification. Unknowns remain visible; there is no readiness score.

## Bounded histories and scope

The overview verifies at most twenty history records and eight MiB of receipt
input in each import/study category, projecting metadata without returning raw
trajectories or CSV. Omitted-record counts are explicit; dedicated histories and
individual exports retain their own bounds. It does not fetch source URLs.
Large overview responses have a four MiB display bound.

This milestone improves navigation, evidence connection and display. No new
physics, AI qualification, authentication or hosted deployment is implied.
See [delivery evidence](CONNECTED_REVIEW_RESULTS.md) and
[acceptance criteria](CONNECTED_REVIEW_ACCEPTANCE.md).
