# Changelog

## 0.2.0 — 2026-10-08

- Add weekly usage on the left and daily usage on the right, immediately above Network.
- Combine download and upload totals on the selected interface while Mint Meter runs.
- Reset daily at local midnight and weekly on Sunday; preserve totals across restarts.
- Store at most seven daily buckets, checkpoint once per minute, and flush on normal quit.
- Exclude ambiguous reconnect, counter-reset, and resume-gap traffic; explain partial tracking in the tooltip.
- Extend the compact card to 320 × 330 logical pixels.
- Correct network-rate timing when route inspection is slow.

## 0.1.0 — 2026-09-28

- Initial compact GTK desktop card with live CPU, RAM, filesystem and network metrics.
- Bounded histories, capacity bars, dark/light themes, scaling and unit preferences.
- Position persistence, lock, reset, desktop/top stacking and workspace controls.
- Single-instance CLI, native settings and opt-in login startup.
- Core tests, virtual-display GUI checks, rootless Debian packaging and CI workflows.
- Original local evaluation build; now published under the MIT license.
