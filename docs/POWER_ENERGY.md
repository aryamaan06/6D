# Power and energy budgets

This increment adds a maintained `power_energy_budget` adapter to the existing project, requirement, revision, scenario, test-comparison and reporting workflow. It calculates a supplied operating schedule. It does not predict a complete electrical system or establish spacecraft readiness.

## Connected workflow

1. Open **Power & energy**. The separate power reference template is also available from **Import project**; its inputs and criteria are constructed examples, not a real mission.
2. Author explicit scalar inputs with values, exact units and source labels. In the shared draft, bind the global capacities and each named mode's duration, generation and equipment rows. Equipment power is per unit; its count declares how many operate simultaneously.
3. Apply the power model to the shared draft, add or inspect its requirements, review dependency changes and save a revision. Draft previews do not calculate power or energy findings.
4. Run checks for the saved revision. Inspect the saved mode table, equipment rows, power margins, energy budget and separate requirement findings. Plots display recorded mode results; they are not interpolated electrical dynamics or battery state of charge.
5. Edit a bound operating input, save another revision and rerun affected checks. A power-only change does not recalculate an unrelated thermal or structural model. A limit-only change reuses the unchanged budget and reassesses the declared criterion.
6. Inspect Reader/Report or a linked requirement. Existing scalar test comparisons can attach explicitly declared observations to an exact saved metric and baseline. Their measured compliance and prediction agreement stay separate from canonical design findings. The scoped Assistant can read the saved evidence and recheck the selected model; it cannot replace its verdict.

## Explicit model contract

The project schema remains `sixd.project.v1`. The model has its existing `id`, `type`, `inputs` and optional `description` fields. Named modes and equipment are encoded as flat roles in `model.inputs`; each role points to an existing project input record. No new project-level mode metadata, arbitrary code or inferred defaults are introduced.

| Required binding role | Exact unit | Meaning |
| --- | --- | --- |
| `usable_battery_energy` | `J` | Upfront bus-deliverable usable energy, already adjusted by the author for reserves and losses |
| `max_battery_power` | `W` | Available bus-delivered battery output power throughout the schedule |
| `bus_power_limit` | `W` | Maximum total equipment demand the bus can carry in each mode |
| `mode.<index>.<mode_id>.duration` | `s` | Positive duration of the named mode |
| `mode.<index>.<mode_id>.generation` | `W` | Constant available generation at the same bus boundary |
| `mode.<index>.<mode_id>.load.<load_id>.power` | `W` | Constant equipment power per unit |
| `mode.<index>.<mode_id>.load.<load_id>.count` | `1` | Number of simultaneously operating units |

Indices are contiguous and begin at `1`; the index defines sequence, not JSON object order. Mode IDs are unique. Mode and load IDs begin with an ASCII letter, contain only ASCII letters, digits, `_` or `-`, and have at most 32 characters; reserved object-property names are rejected. Each mode requires duration, generation and at least one equipment row with both power and count. The contract supports at most 16 modes and 128 equipment rows in total. Counts are integer-valued from 0 to 1,000,000. All other values are finite and nonnegative, with duration strictly positive.

For example, these are binding roles, not literal quantities:

```json
{
  "id": "electrical_budget",
  "type": "power_energy_budget",
  "inputs": {
    "usable_battery_energy": "usable_energy",
    "max_battery_power": "battery_power_limit",
    "bus_power_limit": "bus_capacity",
    "mode.1.cruise.duration": "cruise_duration",
    "mode.1.cruise.generation": "cruise_generation",
    "mode.1.cruise.load.avionics.power": "avionics_power",
    "mode.1.cruise.load.avionics.count": "avionics_count"
  }
}
```

Every referenced input must separately supply its numeric `value`, exact `unit` and nonempty `source`. `Wh`, `kWh` or a different unit label is not silently converted to `J`. A source label does not authenticate the input or verify its measurement convention. Authoring preflight checks layout, bindings and units without running physics; adapter execution checks the numerical domain.

## Budget arithmetic and verdicts

Modes are sequential and non-overlapping. Every listed equipment unit runs continuously throughout its mode; the model has no within-mode duty cycle or scheduling. For a mode with duration `t`, simultaneous demand `L`, generation `G`, battery power capacity `B` and bus capacity `C`:

```text
L = sum(equipment power per unit * simultaneous count)
battery power required = max(L - G, 0)
bus power margin = C - L
battery power margin = B - max(L - G, 0)
combined power margin = min(C - L, G + B - L)
load energy = L * t
generated energy = G * t
battery energy required = max(L - G, 0) * t
uncredited surplus energy = max(G - L, 0) * t
```

The cumulative required battery energy sums all mode deficits. Remaining energy budget is upfront usable battery energy minus that cumulative requirement. It may become negative to expose a shortfall; it is not a simulated battery state or state of charge. Demand continues to be budgeted even where declared power or energy capacity is insufficient. Generation surplus is reported separately and receives no charging credit, whether it occurs before or after a deficit.

Power capacity in `W` and total energy sufficiency in `J` are distinct. A design can have sufficient stored energy yet lack battery output power, or adequate power capacity yet lack sufficient energy for the duration. A negative generation-only margin may be covered by the battery and is not by itself a failed power-capacity check.

| Supported metric | Unit | Meaning |
| --- | --- | --- |
| `peak_load_power` | `W` | Maximum simultaneous equipment demand across modes |
| `minimum_power_margin` | `W` | Minimum combined power margin across modes |
| `total_load_energy` | `J` | Sum of equipment energy across the schedule |
| `total_generated_energy` | `J` | Sum of supplied generation energy across the schedule |
| `battery_energy_required` | `J` | Sum of deficits, with no recharge credit |
| `battery_energy_margin` | `J` | Upfront usable battery energy minus required battery energy |
| `minimum_generation_margin` | `W` | Minimum generation minus equipment demand |
| `max_battery_power_required` | `W` | Maximum battery deficit power |
| `minimum_bus_power_margin` | `W` | Minimum bus capacity minus equipment demand |
| `minimum_battery_power_margin` | `W` | Minimum battery capacity minus required battery output |
| `total_duration` | `s` | Sum of sequential mode durations |
| `surplus_generation_energy` | `J` | Reported generation surplus without storage credit |

Requirements retain their separately declared same-unit limit and exact `<=`, `>=` or `==` operator. Prefer capacity criteria such as `minimum_power_margin >= 0 W` and `battery_energy_margin >= 0 J`. A completed calculation with a violated criterion is `not_met`, not a software failure. Missing/invalid model inputs, unsupported metrics or comparison-unit gaps cannot establish satisfaction and remain `not_assessed`.

Budget accumulation uses exact rational arithmetic for the supplied finite numeric operands before exporting finite floating-point values. Exports still have finite precision: a rounded nonzero metric compared with an extreme nonzero threshold can lose distinctions. The retained zero-centered margins preserve small capacity shortfalls without subtracting already rounded totals. This numerical treatment establishes neither physical accuracy nor input uncertainty. Overflow, underflow of a nonzero result, or indistinguishable timeline endpoints produces an invalid-input/calculation gap without a partial completed artifact.

## Constructed independent reference

The reference template in `examples/power-energy-reference.project.json` contains two modes and an independent thermal model. Its power figures are arithmetic witnesses, not mission requirements:

| Mode | Duration | Equipment demand | Generation | Battery demand | Battery energy required |
| --- | --- | --- | --- | --- | --- |
| Cruise | 100 s | Avionics 10 W plus two payloads at 30 W each = **70 W** | 20 W | 50 W | **5000 J** |
| Downlink | 50 s | Avionics 10 W plus radio 40 W = 50 W | 100 W | 0 W | 0 J |

With 6000 J usable battery energy, 60 W battery output capacity and a 100 W bus capacity, the required battery energy is 5000 J and the energy margin is **1000 J**. Minimum combined power margin is 10 W. Total equipment energy is 9500 J; total declared generation is 7000 J. Downlink's 2500 J surplus is disclosed but cannot reduce the required 5000 J battery budget. Replacing the cruise duration with 200 s increases required battery energy to 10000 J and gives a -4000 J energy margin while the power-capacity margin remains 10 W.

## Saved evidence and integrations

A completed result retains `power_budget` with schema `sixd.power-energy-budget.v1`: ordered mode rows, declared limits, equipment rows, per-mode arithmetic, cumulative required energy, remaining energy budget, assumptions and exclusions. It is retained in the immutable run and review evidence alongside project inputs, adapter version, source fingerprints, dependency fingerprints and original execution identity. Review validation rederives the artifact from its recorded inputs and rejects inconsistent metrics or rows. Digests check consistency; they do not authenticate hardware results or signed approval.

Saved scenarios can vary explicit bound inputs and retain their own hypothetical results without changing the canonical project. Interface contracts can compare an explicit current power metric with a declared allowance, but do not feed that value into another model. The separate thermal reference still receives its own declared heat input; electrical demand is not automatically converted into thermal loading. Likewise, no orbital illumination or eclipse condition is inferred.

Older reviews remain readable without a power artifact. A verifier-source update may make prior evidence historical until the user explicitly reruns the saved revision. Navigation, artifact rendering and exports make no paid inference calls. The existing provider selection and cumulative allowance are unchanged; newly added Assistant context is validated offline, not a new live provider-quality result.

## Scope and references

Excluded effects include solar illumination and panel orientation, generation prediction, eclipse geometry, charging and recharge, battery chemistry, voltage/current behavior, state of charge, temperature dependence, degradation, discharge-efficiency prediction, inrush and transients, wiring/converter losses, protection/fault behavior, load shedding, automatic scheduling and duty cycles. The author must supply an appropriate bus-level measurement boundary and already adjusted usable energy; 6D does not infer reserves or losses. No coupled vehicle simulation, environmental qualification, certification, launch authorization or mission-success guarantee is added.

NASA describes spacecraft electrical power as encompassing generation, storage and distribution; this adapter handles an explicit arithmetic budget within that larger discipline. [NASA, State-of-the-Art of Small Spacecraft Technology: Power](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/). The distinction between power and energy follows the watt's relation to joules per second. [NIST, Watt (W)](https://www.nist.gov/glossary-term/34606). These references provide domain and unit context; they do not endorse or validate the supplied spacecraft data or 6D's implementation. Sources reviewed October 18, 2026, Asia/Calcutta.
