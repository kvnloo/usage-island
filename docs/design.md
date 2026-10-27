# Design Reference

The popup UI should track upstream CodexBar's macOS menu popover as the visual
source of truth.

![Upstream CodexBar popover reference](../assets/design/upstream-codexbar-reference.png)

## Popup Target

- Rounded translucent lavender panel, approximately 620 px wide, with a thin
  light border and soft shadow.
- Top provider strip uses large icon-over-label tabs. The active provider is a
  saturated blue rounded rectangle with white icon/text; inactive providers use
  muted gray icon/text and a short usage meter below the label.
- Body content is flat, not carded. Sections are separated by single lavender
  hairlines.
- Typography is intentionally large: provider/section/menu labels are near
  26 px, supporting values are near 20 px.
- Usage tracks are thin rounded lavender bars with warm orange fill.
- Section order for the usage view is:
  `Provider header`, usage windows, `Extra usage`, `Cost`, account/dashboard
  rows, then `Settings...`, `About CodexBar`, and `Quit`.

The macOS menu bar visible above the popover in the screenshot is environmental
chrome. The wallpaper/background is environmental too. Visual parity work must
compare only the popup panel crop (`x=44, y=63, width=620, height=1309` in the
reference screenshot). On bottom Waybar layouts the popup can anchor
bottom-right above the bar; set `CODEXBAR_POPUP_EDGE=top` and
`CODEXBAR_POPUP_SCALE=1` when comparing directly against the raw upstream
panel dimensions.

## Icon Source

Provider icons should come from the upstream CodexBar provider descriptors, not
hand-drawn local replacements. The popup loads the bundled
`ProviderIcon-*.svg` assets mirrored from upstream and aliases provider IDs
where upstream does the same. For example, upstream's `factory` provider has
the display name `Droid` and uses `ProviderIcon-factory`, so this project maps
both `factory` and `droid` to that asset.

Action-row symbols use a fixed Nerd Font glyph set so they do not vary with the
host GTK icon theme.

## Component Spec

The panel-local component data lives in
[`popup-panel-spec.json`](popup-panel-spec.json). It enumerates the panel shell,
provider tabs, dividers, usage sections, bars, cost section, action rows, and
footer rows. Use it with:

```bash
scripts/verify_popup_visual.py --candidate /path/to/panel-or-screenshot.png
```

If the candidate is a full screenshot, pass `--candidate-crop x,y,width,height`.
Divider components are still scored individually, but the verifier searches a
small local vertical band for those one-pixel rules. GTK/Wayland can land a
hairline on an adjacent device row at compact scale, and the comparison should
catch a missing or wrong divider without failing on compositor rounding.

For the half-size Waybar target, render the fixture data with:

```bash
XDG_CACHE_HOME=/tmp/codexbar-visual-cache \
CODEXBAR_DISABLE_REFRESH=1 \
CODEXBAR_INITIAL_PROVIDER=claude \
CODEXBAR_POPUP_SCALE=0.5 \
CODEXBAR_POPUP_EDGE=bottom \
CODEXBAR_POPUP_REFERENCE_TABS=1 \
./codexbar-popup.py
```
