# Locally served Geist typography

October 27, 2026. 6D bundles genuine Geist Sans and Geist Mono instead of relying on an uninstalled font name or an operating-system fallback.

## Source and license

The four variable WOFF2 files are copied unchanged from the official [Vercel Geist v1.8.2 release](https://github.com/vercel/geist-font/releases/tag/v1.8.2). The upstream project describes the Sans/Mono families and its SIL Open Font License at [vercel/geist-font](https://github.com/vercel/geist-font). The original copyright and complete OFL 1.1 text are retained in [OFL-Geist.txt](../src/sixd/web/fonts/OFL-Geist.txt). The fonts have their own license; 6D's MIT license does not replace it.

[provenance.json](../src/sixd/web/fonts/provenance.json) records the release/archive URL and SHA-256, original ZIP member names, exact file sizes and per-file SHA-256. Only filenames/routes were shortened; font bytes were not subsetted or edited.

## Presentation

- Geist Sans is the shared UI family for page copy, legacy modules, native form controls and headings.
- Geist Mono is used for code, technical quantities, identity strings and chart data labels.
- Both families include normal and italic variable faces, with CSS weights from 100 to 900. Main headings use 700, section headings 650, and smaller headings 600; body size remains at least 14.5 px in the shared shell.
- Existing readable form sizes, exact source text, inputs, SI strings, findings and exports remain intact. Rounded display values do not determine calculations.
- Fonts are served from 6D's own `/fonts/` routes. No third-party CDN call or user-installed font is needed. Native fallback stacks remain available if an asset cannot load; `font-display: swap` preserves readable content while loading.

## Checks

```console
node --test tests/geist_typography.test.mjs
```

The isolated Chromium checks load and decode all four faces, verify loaded FontFace identities and actual metrics (rather than checking only a CSS family string), block third-party requests, compare the checked-in bytes with their recorded SHA-256 and verify exact UI/data text. Final owner/hosted server asset checks and integrated screenshots are recorded with the Build 1 delivery, rather than implied by this standalone fixture.
