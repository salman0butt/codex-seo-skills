---
name: seo-visual
description: Inspect rendered desktop and mobile pages for SEO-relevant visual issues, content visibility, interaction problems, and layout shifts.
license: MIT
metadata:
  author: salman0butt
  version: "0.2.0"
  category: seo
---
# Visual SEO and responsive site audit

Follow the specialist checklist at `../seo/references/agent-guides/seo-visual.md` (upstream MIT).

## Procedure
1. Identify target URL or supplied screenshots and viewport widths. Use an available browser tool only if permitted and installed; do not assume Claude's WebFetch or Playwright is present.
2. Compare above-the-fold content, typography, layout hierarchy, image alt context, touch targets, modals, sticky overlays, navigation, CLS symptoms, and access to critical content on desktop and mobile.
3. Inspect actual DOM/rendered results for JavaScript-loaded content before asserting what search crawlers see. Where browser inspection is blocked, state the limitation and request HTML or screenshots.
4. Record issue, viewport, timestamp, screenshot/evidence, severity, and reproduction steps. Distinguish aesthetic preference from measurable accessibility or SEO failure.
5. Suggest safe changes and retest at 320, 375/390, 768, and desktop widths when appropriate. Never assert a Lighthouse score or accessibility compliance without testing.

## Output
A viewport-specific issue matrix and exact verification steps, with paths/patches only for code available in the user's workspace. Never modify a live property without authorization.
