# VibeChem — UI Guide (Design System)

> Status: v0.4 · Last updated: 2026-11-23
> Changelog: v0.4 — §4 glyph system marked **draft** with an owner-preferences slot (§4.0) and construction rules; §6 block widget gains semantic zoom, output sparkline, fit marker and container blocks (proposals until the Phase 4 glyph/widget step); design-tool precedence (§10). v0.3 — library choices fixed in TECH_STACK.md (this file only defines look and behaviour). v0.2 — symbols, multi-port blocks, student tooltips, jobs display, block classes.
> Philosophy: **modern, minimalist, data-first.** The interface is monochrome; colour is reserved for *meaning* (block class, run state, data). If a colour does not encode information, it should not be there.

## 1. Design principles
1. **Data is the hero.** Chrome stays quiet so spectra and results stand out.
2. **Colour = meaning.** Neutral greys for UI; hues only for block classes, run states and plotted data.
3. **Always show where the data is.** Pipeline state (F-02) visible at a glance.
4. **One symbol, one idea.** Every function has a distinct, recognisable symbol; the class is shown by colour, the method by the glyph.
5. **Progressive disclosure.** Defaults visible; advanced parameters behind "Advanced".
6. **Teach quietly.** Student tooltips everywhere (F-08), never blocking the expert; expert mode hides them.
7. **Calm density.** Generous whitespace on the canvas; compact, tabular density in inspectors and result tables.

## 2. Colour palette

### 2.1 Neutrals (UI chrome) — Tailwind *zinc*
| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#FAFAFA` | `#09090B` | App background, canvas |
| `--surface` | `#FFFFFF` | `#18181B` | Panels, blocks, cards |
| `--surface-2` | `#F4F4F5` | `#27272A` | Hover, inputs, table stripes |
| `--border` | `#E4E4E7` | `#3F3F46` | Hairlines (1px) |
| `--text` | `#18181B` | `#FAFAFA` | Primary text |
| `--text-muted` | `#71717A` | `#A1A1AA` | Labels, secondary text |
| `--primary` | `#18181B` | `#FAFAFA` | Primary buttons (monochrome, inverted in dark) |
| `--focus` | `#6366F1` | `#818CF8` | Focus ring, selection outline only |

### 2.2 Block classes (icon tint + 3px stripe — never a block fill)
| Class | Hex | |
|---|---|---|
| Data | `#0EA5E9` | sky |
| Explore & Plot | `#8B5CF6` | violet |
| Preprocess | `#14B8A6` | teal |
| Split & Validate | `#F59E0B` | amber |
| Select | `#EC4899` | pink |
| Model | `#6366F1` | indigo |
| Transfer (calibration/domain) | `#F97316` | orange |
| Statistics | `#84CC16` | lime |
| Imaging (hyperspectral) | `#06B6D4` | cyan |
| Deploy & Report | `#64748B` | slate |

> 10 hues is the upper limit; check them together with a colour-vision-deficiency simulator before freezing. Class is always also shown by the library group and tooltip, never by colour alone. Final class names follow the card-sort study (S2).

### 2.3 Run states (F-02)
| State | Visual |
|---|---|
| `idle` | Grey dot |
| `queued` | Hollow grey dot |
| `running` | Pulsing indigo dot + animated edge flow + progress ring (% of parallel tasks done) |
| `done` | Green dot `#16A34A` |
| `stale` | Amber dot `#D97706` + dashed border |
| `error` | Red dot `#DC2626` + red border; message in inspector |

**Data position marker:** pill "● Data here · 120 × 1,557" under the furthest `done` block on each branch.

### 2.4 Data visualisation
- Continuous Y: sequential perceptually-uniform map (viridis-family). Classes: ≤ 8 colourblind-safe categorical colours.
- Calibration / CV / test sets: fixed semantic colours plus distinct marker shapes across all plots.
- Plots inherit `--surface` background and `--border` gridlines; no chart junk.
- Many spectra: above 500 lines the viewer switches to density mode (DATA_MODEL.md §2.8) and shows mean ± SD plus selected spectra.
- Publication export presets (single/double column width, vector, 300/600 DPI).

## 3. Typography
| Role | Font | Size / weight |
|---|---|---|
| UI text | **Inter** | 13–14px / 400–500 |
| Headings | Inter | 16 / 600, 20 / 600 |
| Numbers, tables, parameters | **JetBrains Mono** (tabular figures) | 12–13px / 400 |
| Block titles | Inter | 13 / 600 |
| Japanese / Vietnamese | **Noto Sans JP** fallback for Japanese; Inter covers Vietnamese diacritics | same scale |

Spacing unit 4px. Radius 8px (blocks, cards), 6px (inputs, buttons). One soft shadow level for floating elements.

## 4. Symbol (glyph) system — *draft*
> **Draft** until Quan fills §4.0 and approves the glyph set in the Phase 4 glyph-set step (TASKS.md T4.04g, 👤). Until then Claude Code uses these rules for placeholders only and does not freeze glyphs.

### 4.0 Owner preferences (Quan)
<!-- Quan adds his taste here: style references, likes/dislikes, stroke weight, level of detail, metaphors to use or avoid. Example sketch shown in planning chat 2026-11-23: SNV, Savitzky–Golay, PLS, Kennard–Stone, PDS as 24 px outline glyphs. -->
- (not yet given)

### 4.1 Construction rules (default until §4.0 says otherwise)
- **Grid:** 24 × 24 px, 2 px padding, 1.5 px stroke, round caps and joins, outline only (fills only for small data dots). Matches **Lucide**, which is used for generic actions, so base and custom glyphs read as one set.
- **Shape kit:** spectrum curve · axis pair · matrix grid · scatter dots · bracket/window · arrow · σ · two latent axes · instrument box · cube. A glyph = base shape + modifier, so families are visible (all baselines share curve + floor line; all splits share dot cluster + divider; derivatives add 1–2 ticks).
- **Show the transformation, not the name:** SNV = offset spectra collapsing into one band; Savitzky–Golay = curve with a window bracket; PLS = two linked latent axes; Kennard–Stone = spread points with extremes circled; PDS = two instruments with an arrow through a window.
- **No words as the main mark** (they fail in JA/VI); small numerals for variants are allowed.
- **Glyph = method; tint = class.** Two methods in the same class must be distinguishable in greyscale at 16 px.
- Each glyph has an accessible text label; never icon-only without a tooltip.
- One glyph per FUNCTION_CATALOG.md row; recognition tested in study S3 (20 glyphs, no labels).
- **Files:** one SVG per glyph in `app/renderer/src/ui/glyphs/`, plus a generated contact-sheet page (all glyphs at 16/24/48 px, light and dark) used for review via Playwright CLI screenshots.

## 5. Layout

```
┌───────────────────────────────────────────────────────────────┐
│ Top bar: project · pipeline · Run ▶ · Save · Cores: 7/8 · View│
├──────────┬───────────────────────────────────┬────────────────┤
│ Block    │                                   │ Inspector      │
│ library  │        Pipeline canvas (DAG)      │ (selected      │
│ (search, │   [Import]→[SNV]→[SG]─┬→[Nested CV]│  block):       │
│ grouped  │                       └→[PCA]     │ params, help,  │
│ by class)│   [Slave]──────────→[PDS]→[PLS]   │ output preview │
│          │   ● Data here · 120 × 1,557       │                │
├──────────┴───────────────────────────────────┴────────────────┤
│ Bottom drawer: data view / plots / results / jobs / log       │
└───────────────────────────────────────────────────────────────┘
```
- **Canvas mode** (default) and **Guided mode** (same pipeline as a vertical stepper).
- Collapsible panels; zoom, pan, minimap, snap-to-grid, auto-layout.
- Empty state: "Start from a template" cards + "Import data".
- **Jobs tab:** running/queued parallel jobs with progress, ETA, cores used, cancel.

## 6. Components (libraries and versions: TECH_STACK.md §1.5)
- **Block anatomy:** class stripe · glyph · title · 1-line parameter summary ("SG · w=15 · d=1") · state dot · named ports.
- **Ports (F-07):** small shapes on left (inputs) and right (outputs); shape encodes port type (● spectra/table, ◆ model, ▲ split/folds, ■ results, ⬢ image cube). Hover shows port name and type. Required inputs that are unconnected show a hollow red ring.
- **Edges:** 1.5px neutral lines; label with the port name when a block has more than one output.
- **Inspector:** generated from the block's parameter schema (DATA_MODEL.md §5); defaults; "Advanced" collapsible; "Reset to default"; inline validation; "Learn more" link; optional custom panel for special blocks (ARCHITECTURE.md ADR-005).
- **Leakage-safe badge (F-42):** green-outline chip on validation blocks; amber with explanation if unsafe.

### 6.1 Block widget proposals (decided in the Phase 4 glyph/widget step, 👤)
- **Semantic zoom, three levels:** far = glyph + state dot · middle = + title · near = + parameter summary and port labels. Keeps a 200-block canvas readable.
- **Output sparkline:** at near zoom or on hover, a 2-line mini-plot of the mean output spectrum (or score/metric for non-spectral outputs).
- **Fit marker:** a small corner notch on blocks with `fitted = true` (MSC, scaling, PLS …), explained by its tooltip — teaches which steps are refitted per fold.
- **State by dot + border, never by fill;** running = progress ring around the glyph.
- **Container blocks:** nested CV / grid search drawn as a framed group around its sub-pipeline, fold count on the frame. Needs a port-type decision in DATA_MODEL.md §4 before T4.06; if not decided by then, Claude Code stops (`DOC_CONFLICT`).
- Fixed node width (proposal 176 px); height grows with port count.

## 7. Student tooltips (F-08)
- Trigger: hover or keyboard focus, 400 ms delay; never on touch-and-hold of the canvas.
- Content: ≤ 2 sentences — *what it does* + *when to use it*; optional typical value ("Window 11–21 points is common for NIR").
- "Learn more" opens a side panel: short explanation, small figure, method reference (from F-75).
- Style: `--surface` card, `--border`, 12px Inter, max width 280px, no colour except a class-tinted glyph.
- Settings → "Show tips for students" (default on); expert mode hides them.
- All tooltip text in EN/JA/VI; stored as i18n keys referenced by the block definition, not hard-coded in components. EN source text is edited with ux-copy and Humanizer.

## 8. Interaction patterns
- Drag from library → canvas; drop on an edge to insert between blocks.
- Drag from an output port to start a connection; compatible input ports highlight, incompatible ones dim.
- Invalid connections refused with a tooltip explaining why.
- Parameter edits mark downstream blocks `stale` (F-04); Run recomputes only stale blocks, running independent branches in parallel.
- Long jobs show progress on the block, in the Jobs tab and in the top-bar core indicator; cancellable.
- Engine restart (F-84): non-blocking banner "Engine restarted — your project is safe".
- Keyboard: `Space`+drag pan, `Del` remove, `Ctrl/⌘+S` save, `Ctrl/⌘+Enter` run, `?` shortcut sheet.
- Motion: short and functional only (state changes, edge flow); respect `prefers-reduced-motion`.

## 9. Accessibility
- WCAG AA contrast; state never by colour alone (dot + label/tooltip, port shapes).
- Full keyboard navigation of library, canvas and inspector.
- Respect `prefers-reduced-motion`.

## 10. Design tools and precedence
This file is the **only** design specification. Impeccable, ui-ux-pro-max and Emil Kowalski's skills (TOOLS.md) help apply and review it; when they disagree with this file, this file wins and the disagreement becomes a proposed change here. No PRODUCT.md, DESIGN.md or other design docs are created.
