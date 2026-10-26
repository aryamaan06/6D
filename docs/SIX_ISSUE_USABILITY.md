# Six-issue usability refinement

Delivered October 26, 2026. Open **http://127.0.0.1:8768/** and refresh for build **0e93a5ca07d3**. This refines the existing application; it adds no physics model or paid provider activity.

## Calculate and guided review

On a saved revision, **Calculate** and **Recalculate** explicitly run the supported checks even when a result already exists. A visible message shows calculation progress, completion or failure. The controls prevent a second start while a calculation is running. Unchanged inputs can produce unchanged values; a completed explicit rerun still has a new saved run identity. Draft inputs must be saved through the existing revision workflow first.

**Guided review** opens and closes in the current work area, including Projects and the area landing pages. It no longer silently moves to Systems or disappears behind page-specific styling. The guide starts closed unless the local preference says otherwise. On Projects it first asks you to choose a project.

## Move the rocket

The Ask 6D companion now draws local three-dimensional rocket geometry with a metallic surface, fins, engine bells and animated exhaust. It requires no remote asset, font or graphics library.

- Drag the rocket to move it; releasing a drag does not open the conversation.
- Click it, or focus it and press Enter, to open Ask 6D.
- With keyboard focus, use **Alt + arrow keys** to move it; hold Shift for a larger step. **Alt + Home** restores its starting position.
- The position is clamped to the window, restored after refresh and adjusted when the window resizes. Only the normalized position is stored locally.

Reduced-motion preference pauses the animation. When WebGL is unavailable or its graphics context is lost, a local metallic illustration keeps the launcher usable. The rocket is decorative; its exhaust does not simulate engine performance. It is an original procedural rendering, not a claim of photorealism, SpaceX affiliation or equivalence to the Codex companion. Founder visual review remains the authority for later polish.

## Ask Nemotron

Click the rocket and choose **Ask Nemotron**. The main flow is now:

1. Choose **Whole project** or **One engineering check**. For one check, select its short readable name.
2. Choose **Nano**, **Super** or **Ultra** for this investigation.
3. Type your question, or use a suggested question to fill the text box.
4. Click **Ask Nemotron** to send it explicitly.

Changing a model, scope or suggestion sends nothing. The selected saved evidence remains the basis of the investigation; AI cannot change calculated findings. Full context, exact names, references, data sent and settings are in **Context, sources and settings**. Earlier records remain in **Saved answers and evidence**. Captured test context and the existing clear-context controls remain available in the context section. Owner settings and the existing provider/budget protections are retained. Super remains the default.

## Find and keep references

In **Find references**, choose a short engineering topic, type the search and click **Search references**. The default picker groups requirement topics without repeating each saved finding. **Advanced** retains every exact requirement, finding and model-assumption target; choosing one preserves its backend identity.

Preview a result before copying it into Source library. The handoff fills an **unsaved** reference form. Source library now follows a spaced **Add → Saved references → Link** flow, with optional details folded away and clear explanations when Save or Link is unavailable. A title, web address and relevant excerpt are required to save. Saving a reference and linking it to an engineering target remain two separate deliberate actions.

Sources support a stated rationale. A saved source or link does not establish source accuracy, validate a calculation or close an unassessed requirement. The app does not fetch a manually entered URL.

## Typography and retained behavior

The shared native editorial font stack covers project names, breadcrumbs, native controls, legacy modules, dialogs and human-readable text. Actual quantities, code and technical identities keep the coordinated mono stack. Existing readable sizes, SI notation and narrow-screen layouts remain.

Browser Back/Forward, saved-view URLs, draft protection, centered Inspector/Evidence and outside-click/Escape behavior remain. Numerical formulas, receipts, remembered connections, cumulative accounting, per-job caps, hosted limits and explicit provider starts were preserved. [Acceptance](SIX_ISSUE_USABILITY_ACCEPTANCE.md) · [Measured results](SIX_ISSUE_USABILITY_RESULTS.md)
