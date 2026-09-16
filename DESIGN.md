---
name: Shave
mode: hybrid            # ranked view = OPERATE, method page = READ
date: 2026-09-10
---

# Shave, the design system

Extracted from the approved mockup. The mockup is the reference
implementation; this file is the vocabulary.

## Stance

An instrument panel, not a marketing site. The reader is an energy-industry domain
expert who scans and operates. Density is a feature. Every pixel of chrome has to earn
its place, and the loudest thing on screen should be the data, not the interface.

Grounded in the subject's own world: electrical single-line drawings, assessor plats,
utility tariff sheets. That is where the colour language comes from.

## Color

Tokens are defined on bare `:root` (light), then redefined under
`@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`,
then again under `:root[data-theme="dark"]`. Never style a component inside a theme
block. Always go through the token.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--ground` | `#F4F5F3` | `#0F1417` | page ground. Cool paper, not cream, not pure white |
| `--surface` | `#FFFFFF` | `#161C20` | panels |
| `--surface-2` | `#EDEFEC` | `#1D2529` | selected row, drawer |
| `--ink` | `#16191B` | `#E6EAE8` | primary text |
| `--ink-2` | `#5C666B` | `#93A0A5` | secondary text |
| `--ink-3` | `#8A9499` | `#6F7C82` | labels, eyebrows, axis text |
| `--rule` | `#D8DCD9` | `#263036` | hairlines |
| `--rule-strong` | `#BEC5C0` | `#33414A` | table head rule, control borders |
| `--signal` | `#CC3311` | `#FF5C3D` | **the accent.** Energized red |
| `--g2` | `#0B6E6E` | `#2AA7A0` | rate class G-2 (semantic) |
| `--g3` | `#8A9499` | `#6F7C82` | rate class G-3 (semantic) |
| `--ok` / `--warn` / `--bad` | `#15706B` / `#9A6700` / `#A33224` | `#3FB5A6` / `#D2A03C` / `#E2705C` | confidence chips, error text |

**Accent discipline.** `--signal` is spent on exactly three things: the shaved peak on a
sparkline, parcel fill weight on the map, and the selected-row rail. It is never a button
fill, never a heading colour, never decoration. Neutrals carry a slight green-cool bias so
they read as chosen rather than inherited.

**Semantic colour is separate from the accent.** Rate class and confidence have their own
scales. They do not borrow `--signal`.

## Type

**IBM Plex Sans** and **IBM Plex Mono**, from Google Fonts, with real fallback stacks.
Plex was drawn for engineering documentation, which is this subject exactly. Deliberately
not Inter or Space Grotesk.

| Role | Face | Size | Treatment |
|---|---|---|---|
| Brand | Plex Sans 700 | 22px | `letter-spacing: -0.03em` |
| Panel title | Plex Sans 600 | 12px | |
| Body / reason | Plex Sans 400 | 13.5px | `max-width: 56ch` |
| Table data | Plex Sans 400 | 13px | |
| Numbers | **Plex Mono** 500 | 13.5px | `font-variant-numeric: tabular-nums`, always |
| Eyebrow / label | Plex Mono 400 | 10.5px | uppercase, `letter-spacing: .1em` |
| Chip | Plex Mono 400 | 9.5px | uppercase, `letter-spacing: .07em` |

Every figure that appears in a column is tabular. Addresses, kW values, dollar amounts,
bearings and rate codes are all mono.

## Layout

Split view: map `55fr`, ranked table `45fr`, `gap: 16px`. Below 900px it becomes one
column **and the ranked list is ordered first**, with the map following. The payload leads on
the device most likely to open a cold link.

Radius is `3px` everywhere. **There are no shadows in this system.** Separation comes from
hairline rules and surface shifts. Panels are not cards; the only card grid is the states
gallery, where the card genuinely is the unit.

Side gutter is `padding-inline: 20px` on one wrapper, vertical via `padding-block`.
Horizontal scroll is contained to `.tablewrap`; the body never scrolls sideways.

## Data display

- Sparklines get an area fill at 16% opacity, a 1.1px stroke, an emphasized peak dot in
  `--signal`, and a 5%-opacity band marking the billed 08:00–21:00 window.
- Confidence renders as a bordered chip in its semantic colour, never as a bare word.
- The selected table row expands in place to carry its reason sentence. The argument is
  never behind a click.
- The map encodes: fill opacity = annual saving, outline = rate class, hatched segment =
  the clear wall run. Nothing on the map is decorative.

## Accessibility floor

`:focus-visible` outlines in `--signal` at 2px with 2px offset. Skip link to the ranked
list. Table rows and map parcels are keyboard reachable with `role` and `aria-label`.
Touch targets ≥ 44px (row padding is 12px vertical on a 20px line). `prefers-reduced-motion`
disables parcel transitions. Body text meets 4.5:1 against its surface in both themes;
`--ink-3` is reserved for labels at ≥ 3:1 and never for running prose.

## Copy

Utility language. Orientation, status, action. Never mood.

Empty states state a finding, not an absence: *"Every screened parcel fell below 50 kW
average demand, so a 250 kW cabinet has no peak worth shaving. That is a real answer, not
a failure."* Errors say what is still working: *"The ranked list is unaffected, it is
served as static data. Only free-text address search is down."*
