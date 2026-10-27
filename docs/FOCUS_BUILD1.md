# Focus refinement Build 1

October 27, 2026. Refresh **http://127.0.0.1:8768/** and confirm build **acd4b22a579d**.

## Stable rocket

The rocket stays at its resting viewport position while you scroll. It no longer chases newly visible page controls or snaps again when scrolling stops. Drag/release, keyboard movement, Dock safely, Reset, Minimize, Show full rocket and changed layout/viewport remain deliberate positioning mechanisms. Dialogs hide it temporarily; the same local renderer and reduced-motion/fallback behaviour remain.

Scrolling content can move beneath a fixed companion. Use **Rocket options → Dock safely**, drag it elsewhere, or minimize it if it covers something you want to read. There is no reserved right rail or continuously moving scroll animation. This supersedes the earlier Part 3 scroll-triggered parking behaviour.

## Actual Geist fonts

Geist Sans now supplies UI text, page copy, legacy modules, forms and headings; Geist Mono supplies technical numbers, code, IDs and plot data labels. Regular and italic variable faces are bundled locally. Readable sizes are retained, and heading weights are consistently applied despite older module styles. Numeric values, canonical SI strings, saved quotations and exported data are unchanged.

Fonts load from 6D itself, including the hosted invitation page; no external font CDN or installed desktop font is required. Only the exact published font assets are allowed. [Release, license and provenance](GEIST_FONTS.md).

## Hide or restore the sidebar

Use **Hide sidebar / Show sidebar** at the upper left. Hiding navigation gives its space to the central content. It changes layout without navigating, calculating, saving or remounting an open editor.

The keyboard shortcut is **Ctrl + \** on Windows/Linux or **Cmd + \** on macOS. It also works from an open authoring form without discarding its entries. Focus returns to the header control if a breakpoint hides the currently focused sidebar item.

Desktop and mobile choices are remembered separately in this browser. Desktop starts expanded; mobile starts collapsed. Use the same visible header control to open the mobile navigation. Saved project/revision routes and browser Back/Forward remain independent of the layout preference.

This build covers only rocket stability, typography and sidebar focus mode. Result-first/progressive-disclosure page restructuring, clearer thrust editing and conversational/image-capable AI remain separate proposed work. [Acceptance](FOCUS_BUILD1_ACCEPTANCE.md) · [Results](FOCUS_BUILD1_RESULTS.md).
