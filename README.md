# Studio Helper 文房助手

A single-file web app for generating Chinese calligraphy practice sheets and
other layout templates (字格 / 信紙 / 扇面), converting photos to 線稿
line-art, sprinkling decorative flecks (金箔/銀箔), and stamping a seal
(印章) — all in the browser. It runs locally and can also send the
generated sheet straight into [Expresii Paint](https://www.expresii.com/)
as a painting underlay, overlay, or settled paint.

![Studio Helper screenshot](screenshot.png)

## Features

- **Template types**
  - 米字格 Mi — cross + diagonals
  - 田字格 Tian — cross
  - 九宮格 9-box — 3×3 sub-grid
  - 回宮格 Hui — inner box
  - 豎線 Vertical — vertical lines only
  - 橫線 Horizontal — horizontal lines only
  - 直式信紙 Chinese letter — vertical Chinese letter paper
  - 扇面 Fan — folding-fan leaf: bold black outline (the 2 大骨) + black 折線 (fold
    lines). For a real fan spec the leaf is divided into (方−1)×2+1 sectors — i.e.
    (方−1)×2 black fold lines between the two 大骨 edges (e.g. 15方 → 29 sectors),
    with **no red column grid**. Adjacent fold lines alternate 凹折 (concave/valley)
    and 凸折 (convex/ridge); with **Dashed guides ON** they get distinct dash styles
    (凹折 = `7 5`, 凸折 = `2 5`). A **扇面规格 (fan spec)** dropdown (8寸 / 9寸 /
    10寸 / 自定) applies the real sector shape from the reference template (opened
    width, rib length, radial depth); the leaf fits the current paper, so it works
    with Expresii auto paper-size sync. 自定 keeps the red concentric + column grid.
- **Paper**: presets (A4/A3/A5/Letter/Legal/Square), custom aspect, portrait /
  landscape, adjustable resolution (px/mm, ~300 DPI). The exported PNG stays
  pixel-matched to the Expresii canvas at any DPI.
- **Layout**: cols & rows, or cell-size; paper margin (auto = ½ cell).
- **Style**: border & guide colors, border/guide widths, dashed guides, cell
  borders.
- **Export**: SVG (vector, scales to any printer), PNG, or Print/PDF.
- **Expresii integration**: live connection status, editable server URL,
  auto paper-size sync from `/state` (2048×2048 → default 8×8 grid), and
  *Send to Expresii* (Underlay or Settled Paint).

## Running locally

The app is a single self-contained `index.html`. **Just open it in a browser** — no
server, no build step:

```
# Option A — simplest: double-click index.html, or open it from your file manager
file:///.../TemplateGenerator/index.html

# Option B — serve it (optional; only if you prefer an http:// origin)
git clone https://github.com/expresii-paint/TemplateGenerator.git
cd TemplateGenerator
python -m http.server 8753
# open http://127.0.0.1:8753/index.html
```

Everything runs in the browser: grid generation, the 線稿 (line-art) converter, and
connecting to Expresii. Expresii's Command Server sends `Access-Control-Allow-Origin: *`,
so the page talks to it directly (including from a `file://` page), just like Amami.html.

## Sending to Expresii

1. Make sure Expresii is running with its Command Server enabled.
2. In the **EXPRESII** panel, confirm the Server URL (default
   `http://localhost:9000`) and that it shows *connected*.
3. Pick a **Target** (Underlay / Overlay / Settled Paint layer) and click **Send to
   Expresii**.

## Files

| File | Purpose |
|------|---------|
| `index.html` | The entire app (HTML + CSS + JS), self-contained. |
| `screenshot.png` | Screenshot shown above. |
