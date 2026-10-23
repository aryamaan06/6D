# Engineering coverage and applicability

Open the connected workspace and select **Engineering coverage** in the sidebar.

The map groups engineering checks by a supplied mission phase and discipline. Every existing requirement appears automatically until a declaration maps it. A calculated requirement result and the physical applicability of its model are displayed separately.

## Using the map

1. Select an existing requirement card, or fill the new-check form.
2. Name the engineering question, mission phase and discipline. Phase suggestions are organizational labels, not solver capabilities.
3. Link a saved requirement when a calculation exists. Leave it unlinked when analysis is still needed.
4. Record whether the check is required, excluded or undecided. An exclusion needs a rationale.
5. Record whether model fit is unknown, declared by you, or outside the assumptions. A declared judgment needs a written rationale and a linked requirement.
6. State the next engineering step and explicitly save. This appends a declaration version; it does not calculate or change the requirement finding.
7. After a design change, revisit declarations marked **Context needs review**. Review the new configuration before saving another version.

Select a card to inspect its rationale, model assumptions, exclusions and version history. **Open linked requirement** returns to the existing engineering workspace. Discipline and coverage-state filters narrow the phase map. **Export coverage JSON** preserves the loaded coverage snapshot. The full engineering report includes coverage and its combined JSON export captures coverage, references, actions and test evidence in one database snapshot.

## Meaning of results

- **Analysis not linked:** a required check lacks a current supported calculation mapping.
- **Model fit not established:** a calculation may exist, but no fit judgment has been declared.
- **Outside model assumptions:** the supplied engineering judgment identifies a physical applicability problem.
- **Context needs review:** recorded dependencies changed or the mapped requirement disappeared.
- **Calculation unresolved:** required current numerical evidence is unavailable or unassessed.
- **Criterion unmet / Criterion met · declared fit:** the numerical result is shown alongside a supplied applicability judgment. Neither status establishes whole-mission validity.
- **Declared out of scope / Applicability undecided:** scope decisions remain visible. Any linked criterion result is preserved separately.

Counts refer to declared checks and unmapped requirements. Multiple checks can link to one requirement, so these are not a physics-completeness percentage. An empty map is not evidence of a complete mission review.

## Revision and evidence behavior

Coverage is a supplemental append-only record. Old declaration versions remain inspectable; records created against a later revision do not appear in an earlier revision. Annotations added later to the same revision are not part of that revision's original calculation receipt.

Mapped checks track explicit requirement/model/input/criterion/implementation dependencies, including upstream calculation chains. Unmapped checks conservatively track the entire declared project because no narrower dependency exists. Source-library link changes are not a verified assessment of physical applicability. Changes outside recorded project data need a new supplied review.

Historical revisions and project drafts are read-only for coverage. A conflicting save retains the form and requires the current context to be reviewed. Up to 100 declared checks and 30 versions per check are supported. Every requirement remains represented even if no declaration exists.

All seven existing bounded calculators retain their scope. This milestone adds no powered flight, coupled vehicle physics or launch authorization. It uses local records and requires no API key or paid inference.
