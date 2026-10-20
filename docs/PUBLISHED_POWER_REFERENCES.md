# Power reference mapping

Verified source access October 19, 2026:

- [OpenStax, University Physics Volume 2 §9.5, Example 9.10](https://openstax.org/books/university-physics-volume-2/pages/9-5-electrical-energy-and-power): published constant-load energy totals for 100W and 20W operated three hours/day for 365 days are 109.5 and 21.90 kWh. The same section defines constant-load energy and the kWh-to-joule conversion. These stated totals, converted to 394200000J and 78840000J, supply numerical expectations independent of 6D's calculation.
- [NIST SI Guide, Chapter 4](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes): energy in joules and power in watts (J/s).
- [NASA Small Spacecraft Technology, Power](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/): spacecraft power-subsystem context and hardware considerations. This source is not claimed to validate the constructed schedule, capacity values or conservative no-recharge policy.

The textbook on-time is aggregated to a constant supplied interval. This reproduces energy accounting only; a household worked example does not validate solar geometry, battery chemistry, reserves, losses or space qualification. Model capacities are explicitly constructed benchmark wrappers.

A separate constructed two-mode schedule checks simultaneous counts, generation, independently summed energy, surplus and separate power/energy shortfalls. Its expected table uses literal independently computed integer arithmetic, not production helpers. This is an application of published energy accounting and the declared no-recharge policy, not a published worked spacecraft case. All power checks use absolute tolerance 1e-6 SI units and relative tolerance 1e-12; comparisons take the larger allowance.
