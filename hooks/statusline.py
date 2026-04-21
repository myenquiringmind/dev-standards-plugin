"""Publish framework context-percentage cache + terminal status line.

Invoked as Claude Code's ``statusLine`` command (configured by the
**user** in ``~/.claude/settings.json`` — plugins cannot ship a
top-level ``statusLine`` key; only ``agent`` and
``subagentStatusLine`` are supported at plugin-settings level).

Reads CC's rich JSON payload on stdin, converts CC's raw
``used_percentage`` (% of model window) into the framework's
percentage-of-hard-cut metric, atomically writes
``.claude/.context_pct`` for ``context_budget.py`` to consume,
and prints a terse status string to stdout.

The framework budget is ``75%`` of CC's ~``83.5%`` compaction
threshold, so ``framework_pct = raw_pct / (0.835 * 0.75)``
≈ ``raw_pct / 0.62625``. ``framework_pct >= 95`` means the user
is within the advisory band for ``context_budget.py``;
``>= 100`` means they are at or past the hard cut.

Exit 0 always. Non-zero blanks the CC status line — we never
want to hide the line on our own errors; we print what we can.

Event: CC statusLine (not a standard hook)
Matcher: N/A — wired into settings.json, not hooks.json
"""

from __future__ import annotations

import sys
from pathlib import Path

from hooks._hook_shared import (
    CC_COMPACTION_FRACTION,
    HARD_CUT_FRACTION,
    compute_hard_cut,
    get_current_branch,
    get_project_dir,
    read_hook_input,
)
from hooks._os_safe import atomic_write

_FRAMEWORK_BUDGET_FRACTION: float = CC_COMPACTION_FRACTION * HARD_CUT_FRACTION


def _extract_used_pct(data: dict[str, object]) -> float | None:
    """Pull ``context_window.used_percentage`` as a float if present."""
    cw = data.get("context_window")
    if not isinstance(cw, dict):
        return None

    raw = cw.get("used_percentage")
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _extract_window_size(data: dict[str, object]) -> int | None:
    """Pull ``context_window.context_window_size`` as an int if present."""
    cw = data.get("context_window")
    if not isinstance(cw, dict):
        return None

    raw = cw.get("context_window_size")
    if isinstance(raw, int) and raw > 0:
        return raw
    return None


def _extract_model_name(data: dict[str, object]) -> str:
    """Pull ``model.display_name`` (preferred) or ``model.id``."""
    model = data.get("model")
    if not isinstance(model, dict):
        return ""

    for key in ("display_name", "id"):
        raw = model.get(key)
        if isinstance(raw, str) and raw:
            return raw
    return ""


def _framework_pct(raw_pct: float) -> int:
    """Convert CC's raw % to the framework's % of hard cut."""
    return max(0, int(raw_pct / _FRAMEWORK_BUDGET_FRACTION))


def _format_tokens(n: int) -> str:
    """Render a token count in compact form: ``1234`` → ``1.2K``."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _write_cache(project_dir: Path, pct: int) -> None:
    """Atomically write the framework pct cache; log on failure."""
    try:
        atomic_write(project_dir / ".claude" / ".context_pct", str(pct))
    except OSError as exc:
        print(f"[statusline] could not write .context_pct: {exc}", file=sys.stderr)


def _build_line(
    model_name: str,
    framework_pct: int | None,
    raw_pct: float | None,
    window_size: int | None,
    branch: str,
) -> str:
    parts: list[str] = []
    if model_name:
        parts.append(model_name)
    if framework_pct is not None:
        if raw_pct is not None and window_size is not None:
            hard_cut = compute_hard_cut(window_size)
            used_tokens = int(window_size * raw_pct / 100)
            parts.append(
                f"ctx {framework_pct}% ({_format_tokens(used_tokens)}/{_format_tokens(hard_cut)})"
            )
        else:
            parts.append(f"ctx {framework_pct}%")
    if branch:
        parts.append(branch)
    return " · ".join(parts)


def main() -> int:
    data = read_hook_input()

    project_dir = get_project_dir()
    branch = get_current_branch(project_dir)

    model_name = _extract_model_name(data)
    raw_pct = _extract_used_pct(data)
    window_size = _extract_window_size(data)

    framework_pct: int | None = None
    if raw_pct is not None:
        framework_pct = _framework_pct(raw_pct)
        _write_cache(project_dir, framework_pct)

    line = _build_line(model_name, framework_pct, raw_pct, window_size, branch)
    if line:
        print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
