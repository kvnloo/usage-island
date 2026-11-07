# Upstream parity: CodexBar 0.40.0 → 0.46.1

What [steipete/CodexBar](https://github.com/steipete/CodexBar) has added since our
`0.4.0` baseline (which tracked CodexBar **0.40.0**), and what each item means for
this Waybar port.

**Method.** Diffed upstream `CHANGELOG.md` (0.41.0 → 0.46.1), `docs/cli.md`,
`docs/configuration.md`, the canonical provider-ID list, the bundled icon set, and
`Sources/CodexBarCLI/CLIPayloads.swift` + `Sources/CodexBarCore/UsageFetcher.swift`
against `codexbar.sh`, `codexbar-popup.py`, and the live output of the `codexbar`
binary installed on this machine.

**Filter.** Upstream is a macOS SwiftUI app; most of its 0.41–0.46 work is menu-bar
layout, WidgetKit, Keychain, and confetti, none of which apply here. This document
only covers what is reachable from the Linux CLI — the sole surface this port
consumes. A macOS-only appendix is at the end so the omissions are explicit.

---

## Priority summary

| # | Item | Why | Effort |
|---|------|-----|--------|
| 0 | Upgrade the local `codexbar` binary | Everything below is gated on it | trivial |
| 1 | `save_config()` destroys credentials | Data loss, live bug | small |
| 2 | Config path moved to XDG | Settings writes a file the CLI ignores | small |
| 3 | Provider registry: +11 / −2 | Users can't enable 11 providers | small |
| 4 | 11 new provider icons, 1 stale | Cosmetic, pairs with #3 | trivial |
| 5 | `isSyntheticPlaceholder` ignored | Renders fake usage as real | small |
| 6 | `cacheAccountKey` for cache keying | Replaces our heuristic | small |
| 7 | Sub-1% and clamping display rules | Wrong numbers in bar/tooltip | small |
| 8 | 18 unrendered provider detail payloads | Tooltip poorer than upstream | large |
| 9 | `codexbar guard` | New CLI capability | medium |
| 10 | Hooks / `serve` / `cards` / `cookie refresh` | Optional surfaces | varies |

---

## 0. Prerequisite: the installed CLI is older than our own baseline

The binary at `~/.local/bin/codexbar` (dated 6 Jul) reports version `unknown` and:

- rejects `guard`, `cards`, `hooks` as unknown commands;
- lists `crossmodel` and `kimik2` in `--provider`, both **removed upstream in 0.44.0**;
- dumps exactly the 57 provider IDs that `PROVIDER_NAMES` hardcodes.

So our 57-provider list is not stale relative to *this* binary — it is stale relative
to upstream, and the binary is the thing lagging. Its `--provider` flag also spells
IDs differently from the config file (`abacusai` / `groqcloud` / `azure-openai` /
`alibaba-coding-plan` vs `abacus` / `groq` / `azureopenai` / `alibaba`); worth
re-checking after the upgrade that `codexbar.sh` still passes IDs the CLI accepts.

Everything below assumes a 0.46.x CLI. Upgrade first, then re-run
`codexbar config dump` and diff against `PROVIDER_NAMES` before touching anything.

Release assets are now published for glibc **and static musl**
(`CodexBarCLI-v<tag>-linux-musl-{x86_64,aarch64}.tar.gz`). `install.sh` only knows the
glibc naming — worth offering musl for Alpine/NixOS users.

---

## 1. `save_config()` silently destroys credentials — fix first

[`codexbar-popup.py`](codexbar-popup.py) `save_config()` rewrites the whole config as:

```python
payload = {"providers": [{"id": pid, "enabled": True} ...], "version": 1}
```

Every other field is dropped. Against upstream's current schema that discards
`apiKey`, `cookieHeader`, `cookieSource`, `source`, `enterpriseHost`, `region`,
`workspaceID`, `tokenAccounts`, the whole top-level `hooks` block, and provider
ordering (which upstream uses for display order).

This was survivable when Linux users had no credentials to lose. It isn't now:
0.44–0.46 made manual cookies the supported Linux path for Alibaba Token Plan, Qwen
Cloud, LongCat, and Command Code, added API-key providers, and added hooks. Upstream
hit the identical bug and fixed it in 0.44.0 ("Hooks: preserve configured hooks across
config saves", #2436).

**Fix:** read the existing config, mutate only `enabled` per provider, write the merged
result back. Preserve unknown keys verbatim so future schema additions survive a Save.

Note `config dump` **redacts credentials by default** as of 0.46.0 (`--show-secrets`
restores them). Never merge from `config dump` output — read the real file. Our
Settings only reads `id`/`enabled` from the dump, so reading stays fine; writing is
the hazard.

---

## 2. Config path moved to XDG

Upstream resolution order is now:

1. `$CODEXBAR_CONFIG`
2. `$XDG_CONFIG_HOME/codexbar/config.json` (new installs)
3. `~/.codexbar/config.json` (legacy, only when no XDG config exists)

We hardcode the legacy path in two places — [`codexbar-popup.py:132`](codexbar-popup.py:132)
and [`codexbar.sh:18`](codexbar.sh:18). On a fresh 0.46 CLI install the XDG file is
authoritative, so our Settings Save writes a file the CLI ignores and the user sees
toggles that do nothing.

**Fix:** mirror the three-step resolution in both files. Keep writing to whichever file
resolves, and do not create the XDG file if a legacy one already exists — that would
silently orphan the user's existing config.

Unrelated but adjacent: our own `state.json` already honours `XDG_CONFIG_HOME`, so
only the CodexBar config path needs changing.

---

## 3. Provider registry delta

Upstream registry is **66 IDs**; we carry **57**.

**Add (11).** With the version that introduced each:

| ID | Provider | Landed |
|----|----------|--------|
| `wayfinder` | Wayfinder (local gateway health/routing/savings) | 0.42.0 |
| `sub2api` | sub2api (group keys, wallet, daily/weekly/monthly) | 0.43.0 |
| `clinepass` | ClinePass (API key, 5h/weekly/monthly) | 0.44.0 |
| `neuralwatt` | Neuralwatt (subscription kWh + prepaid credits) | 0.44.0 |
| `longcat` | LongCat (quota + fuel packs, disabled by default) | 0.44.0 |
| `zenmux` | ZenMux (5h/weekly, expiry, USD PAYG balance) | 0.44.0 |
| `deepinfra` | DeepInfra (balance, spend, limits, suspension) | 0.45.0 |
| `aiand` | ai& (30-day org spend from request logs) | 0.45.0 |
| `qwencloud` | Qwen Cloud (5h + weekly rolling windows) | 0.46.0 |
| `zoommate` | ZoomMate (credits, session history, pacing) | 0.46.0 |
| `xai` | xAI console — distinct from consumer `grok` | 0.27.0 |

`xai` is a **pre-existing** gap, not a regression: it has always been a separate
registry entry from `grok` and we never listed it.

**Remove (2).** Both deleted upstream in 0.44.0 and absent from the current registry:

- `crossmodel` — hosted relay removed pending identifiable operator details
- `kimik2` — unofficial anonymous relay removed (official `kimi` / `moonshot` remain)

Leaving them listed offers users toggles a 0.46 CLI will reject.

**Files:** `PROVIDER_NAMES` in [`codexbar-popup.py`](codexbar-popup.py); the macOS-only
grouping in Settings; `README.md` provider mentions.

Also worth doing: replace the hardcoded dict with a `config dump`-derived list at
runtime, falling back to the baked-in dict. Our 0.4.0 already made `config dump` the
authority for *selectable* providers; making it the authority for *labels* too would
end this drift permanently. Human-readable names would still need a local map, but the
ID set would self-update.

---

## 4. Icons

Upstream bundles **62** provider marks; `assets/providers/` has **52**.

**Pull (11):** `aiand` `clinepass` `deepinfra` `longcat` `neuralwatt` `qwencloud`
`sub2api` `wayfinder` `xai` `zenmux` `zoommate` — exactly the set from §3.

**Drop (1):** `ProviderIcon-crossmodel.svg` — no longer upstream.

Four providers we already list have never had an icon: `alibabatokenplan`,
`azureopenai`, `moonshot`, `openai`. Upstream has no mark for them either, so the
current no-icon fallback is correct — noting it only so it isn't mistaken for drift.

Refresh `assets/providers/NOTICE` with the new count.

---

## 5. `RateWindow.isSyntheticPlaceholder` — we render fake windows as real

`RateWindow` now carries two fields we ignore:

- **`isSyntheticPlaceholder: Bool`** — upstream emits placeholder windows that must
  *not* "masquerade as a real session lane". We read `usedPercent` unconditionally in
  both [`codexbar.sh`](codexbar.sh) (`max_pct`, `fmt_window`, `pct_or_null`) and the
  popup, so a placeholder becomes a real-looking number, feeds the cross-provider max,
  and can drive the bar's `critical` class. Upstream 0.42.1 fixed the same class of bug
  for Claude ("ignore synthetic no-session placeholders … preventing false restores and
  duplicate threshold warnings").
- **`nextRegenPercent: Double?`** — the popup already reads it; the jq tooltip does not.

**Fix:** filter `isSyntheticPlaceholder` windows out of `max_pct` and the bar text, and
either hide them in the tooltip or label them explicitly.

`PacePayload` also gained **`runOutProbability: Double?`** (0.45.0's forecast work),
which neither file reads — a natural addition to the existing pace line.

---

## 6. `cacheAccountKey` — replaces our multi-account cache heuristic

`ProviderPayload` now includes `cacheAccountKey: String?`, upstream's own stable
per-account cache key. Our 0.4.0 built the equivalent by hand — `entry_key()` in the
popup concatenates `provider\0account` with an identity-email fallback, and
`codexbar.sh` keys cached snapshots on provider + account label.

Prefer `cacheAccountKey` when present, fall back to `entry_key()` otherwise. This
matters for Claude profiles and OpenRouter, where 0.45.1/0.46.0 added labelled
multi-account support with isolated usage and upstream fixed cross-profile credential
bleed (#2484) — our string-built key can collide where theirs won't.

---

## 7. Display-behaviour parity

Small, high-visibility rules upstream settled on. Each is a few lines in
[`codexbar.sh`](codexbar.sh)'s jq block and/or the popup's `int(pct)` rendering.

- **Sub-1% (0.41.0).** Show every positive value below 1% as `<1%`, rather than
  rounding >0.5% up to `1%`. Our jq uses bare `floor` and the popup uses `int(pct)`, so
  0.7% currently renders as `0%` — arguably worse than either upstream behaviour.
  **This overlaps [PR #6](https://github.com/Marouan-chak/codexbar-waybar/pull/6)** and
  should be settled together: upstream's answer is integers in compact surfaces plus a
  `<1%` special case, not two decimals.
- **Clamp to 0–100.** Upstream clamped overage in four separate providers
  (z.ai 0.46.0, ElevenLabs 0.45.1, Cursor 0.45.0, Abacus 0.45.0) and fixed Devin's 1%
  inflating to 100% (0.41.0). A single clamp at our render layer covers all of them and
  any future provider that overshoots.
- **Preserve computed sub-1% (0.45.2).** OpenCode / OpenCode Go emit real fractional
  percentages that must not be rescaled as direct fractions.
- **Reset countdown at exactly 24h (0.46.0).** Use the day form at the 24-hour
  boundary. Relevant to our `resetTimeFormat` renderer.
- **Show reset time when a quota is exhausted (0.42.0).** Replace the percentage with
  the countdown while a window is depleted, then restore it. Upstream made this an
  option; it fits our pinned-provider bar text well.
- **Hide pace for depleted weekly quotas (0.44.0)** while keeping the reset countdown.
- **Claude plan labels.** `Max 5x` / `Max 20x` instead of flat `Max` (0.41.0);
  Team Standard vs Team Premium (0.44.0).

---

## 8. Provider detail payloads we don't render

`UsageSnapshot` carries 25 provider-specific detail structs. We render **5**:
`providerCost`, `codexResetCredits`, `openRouterUsage`, `sakanaPayAsYouGo`,
`openAIAPIUsage`.

Unrendered (18): `kiroUsage` `ampUsage` `zaiUsage` `zoommateCreditsHistory`
`minimaxUsage` `deepseekUsage` (+ `deepseekDetailedUsageState`,
`deepseekPlatformProfiles`) `opencodegoUsage` `mimoUsage` `clawRouterUsage`
`sub2APIUsage` `wayfinderUsage` `groqConsoleUsage` `claudeAdminAPIUsage`
`mistralUsage` `deepgramUsage` `poeUsage` `xaiUsage` `cursorRequests`.

Plus `commandCodeHasSubscriptionPlan` (we read the other two `commandCode*` flags).

Each needs its own tooltip/popover renderer, so this is the largest item here and the
most divisible — do them per provider, driven by which ones you actually use. The
existing `summarize_usage_details()` in the popup is the right place; `provider_lines()`
in the jq block is the tooltip equivalent.

Note `MiMoUsageSnapshot` can now carry a stale-cache marker (`stale 34d`, 0.42.1) that
should surface rather than read as live usage.

---

## 9. `codexbar guard` (0.45.0) — the most useful new CLI command for us

```bash
codexbar guard --provider codex --min-remaining 20 --window weekly --json
```

Exit codes are stable and documented: `0` safe, `1` below threshold, `64` bad args,
`69` unavailable (`--fail-open` turns `69` into `0`). `--timeout` bounds the fetch.

Two fits here:

1. A documented recipe in `README.md` for gating user scripts on quota — cheap, no code.
2. Wiring it behind a Waybar click action or `notify-send` threshold, replacing any
   percentage comparison we'd otherwise hand-roll in jq.

Guard fetches are read-only and never prompt for interactive Keychain access, so
they're safe to call from a polling context.

---

## 10. Other CLI surfaces (evaluate, don't assume)

- **`codexbar cards` / `--brief` (0.41.0).** Responsive terminal card grid. Honours
  `$COLUMNS`, `--no-color`, `CODEXBAR_CARDS_ENHANCED=1`. Candidate for our right-click
  action, which currently falls back to `notify-send`.
- **Hooks (0.44.0).** `codexbar hooks list|enable|disable|test`, config under top-level
  `hooks`, default off, commands run shell-free with `CODEXBAR_*` env + JSON on stdin.
  Mostly this is a **don't-break-it** item (see §1) — but `quota_low` could drive a
  Wayland notification without us polling for it.
- **`codexbar serve` (0.44.0).** `/health` (now returns `version`), `/usage`, `/cost`,
  and token-gated `/dashboard/v1/snapshot`. One long-lived `serve` could replace our
  per-provider subprocess fan-out in `codexbar.sh` — a real architectural simplification
  worth prototyping, with the caveat that it adds a daemon to manage. Loopback binds
  leave `/usage` and `/cost` unauthenticated; **never** bind non-loopback from our
  installer.
- **`codexbar cookie refresh` (0.45.0).** Browser import is macOS-only, so on Linux this
  is only relevant for the manual-cookie providers. Low priority.
- **`codexbar cache clear --cookies|--cost|--all` .** Useful behind a Settings button.
- **`codexbar config validate`.** Cheap post-Save sanity check — pairs naturally with
  the §1 fix.

---

## 11. Linux fixes we inherit by upgrading

No work on our side; listed so the upgrade's value is legible, and because two of them
are bugs users may have already reported.

- **NixOS `SIGILL` (0.43.0)** — CLI now bootstraps the configured IANA timezone before
  Foundation starts on non-FHS systems.
- **Crash formatting rate windows (0.43.0)** — Foundation bundle discovery on Linux.
- **`EMFILE` in long-running `serve` (0.45.0)** — subprocess capture pipes now closed.
- **Antigravity port discovery (0.42.0)** — recovers CLI listening ports from procfs
  when `lsof` is absent, including network namespaces. Directly relevant to our
  Antigravity credential bridge and `cert_redirect.c` shim; worth re-testing whether
  parts of that workaround are still needed.
- **Alibaba / Qwen Token Plan on Linux via manual cookie (0.46.0)**.
- **Kiro signal-mask fix (0.43.0)** — spawned PTY probes no longer ignore termination,
  which matters for our `CODEXBAR_PROVIDER_TIMEOUT` handling.

---

## 12. Explicitly out of scope (macOS-only)

Not gaps — recording them so the list above reads as complete: menu-bar drag-and-drop
layouts and high-contrast mode (0.44/0.45), WidgetKit, Keychain policy work, confetti
palettes, Agent Sessions SSH/Tailscale discovery, Usage & Spend share cards, adaptive
refresh, Codex Workspaces indexing, browser cookie import, and app-side Settings
reorganisation.

---

## Suggested sequencing

1. **Upgrade the CLI** (§0), re-dump the provider list, confirm `--provider` ID spellings.
2. **Fix `save_config()`** (§1) and the **config path** (§2) — both are live
   correctness bugs, both are small, and #1 loses user data today.
3. **Registry + icons** (§3, §4) — mechanical, unblocks 11 providers.
4. **`isSyntheticPlaceholder` + clamping + sub-1%** (§5, §7) — settle alongside PR #6
   so the percentage-rendering rules land once, coherently.
5. **`cacheAccountKey`** (§6).
6. **`guard` recipe** (§9), then pick off detail payloads (§8) by actual need.
7. **Prototype `serve`** (§10) only if the subprocess fan-out is actually hurting.

Steps 1–3 are roughly one sitting. Step 4 is the one to think about rather than
implement quickly, since it changes what every user sees in their bar.

---

*Sources: upstream `CHANGELOG.md` 0.41.0–0.46.1, `docs/cli.md`, `docs/configuration.md`,
`Sources/CodexBarCLI/CLIPayloads.swift`, `Sources/CodexBarCore/UsageFetcher.swift`,
and the local `codexbar` binary. This port is already listed in upstream's README under
"Linux desktop integration".*
