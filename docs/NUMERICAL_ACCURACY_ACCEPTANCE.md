# Numerical accuracy milestone

Authorized October 23, 2026. Acceptance precedes implementation.

An engineer runs a declared orbit, inspects numerical evidence, changes resolution
or tolerance, and sees unresolved findings until the supplied numerical criteria
are supported. Saved history remains inspectable with its original method.

- Measure signed state errors against a separately implemented analytic Kepler
  reference over circular, eccentric, inclined and multi-period cases.
- Improve measured position/velocity errors with a versioned solver; record the
  former method's results without relabeling old evidence.
- Three-grid comparisons, numerical allowances and unresolved states propagate
  through requirements, scalar chains, playback and reports. No convergence
  criterion is a rigorous error bound or proof of physical applicability.
- Exact powered-flight burnout has identical before/after timestamps and state,
  including fractional event times and zero-coast cases.
- No automatic production-data recalculation, paid calls or source-data changes.
  Validate on isolated projects, then verify existing records read-only.
- Bound computation and retain usable historical artifacts without invoking the
  new solver. Publish measured results and known limitations.
