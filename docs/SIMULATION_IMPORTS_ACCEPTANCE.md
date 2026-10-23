# Specialist simulation imports acceptance

Authorized October 23, 2026. One milestone within the agreed five-build scope.

An engineer imports a UTF-8 CSV of specialist time-history results, explicitly
declares units, frame, time origin, configuration and source, previews it, saves
it against a revision, replays its samples and compares supported observables
with an exact saved project calculation. Importing never changes that calculation
or its requirement findings.

- Retain original CSV, explicit mappings and configuration, exact revision and
  source-byte digest. No conversion, interpolation, model fitting or execution of
  file contents. Generic numeric channels remain usable without a bound model.
- Reject malformed/nonfinite/oversized data, missing declarations, duplicate or
  decreasing times. Bound bytes, rows, columns and channels.
- Compare only exact timestamp matches, matching units/frame/time origin and
  an explicit conditions declaration. Missing numerical support or unmatched
  samples remain visible; partial overlap cannot become a full agreement pass.
- Freeze the exact baseline run and review; reads verify retained evidence without
  invoking a solver. New revision/run/source changes flag historical context.
- Save explicitly, append only, and reject stale context. Draft/history views
  cannot save against an unseen newer baseline. Reports and JSON preserve scope.
- Browser playback uses recorded samples, exposes values and provenance, and
  keeps unsupported comparisons distinct from vehicle defects.
- Verify parser, alignment, history/tampering, API, actual browser workflow and
  canonical data preservation. Use isolated projects; no paid calls or founder
  fixture insertion. Finish by restarting and checking the delivered app.
