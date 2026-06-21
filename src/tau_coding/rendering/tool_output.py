"""Shared formatting for visible tool-output previews."""

from enum import StrEnum

from tau_agent.types import JSONValue

TOOL_RESULT_PREVIEW_LINES = 8
TOOL_PATCH_PREVIEW_LINES = 32
TOOL_RESULT_PREVIEW_CHARS = 2_000
TERMINAL_COMMAND_OUTPUT_PREVIEW_LINES = 120


class ToolOutputVisibility(StrEnum):
    """Visible detail levels for rendered tool results."""

    none = "none"
    short = "short"
    full = "full"


def normalize_tool_output_visibility(value: object) -> ToolOutputVisibility:
    """Parse a user/config value into a tool-output visibility level."""
    if isinstance(value, ToolOutputVisibility):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        try:
            return ToolOutputVisibility(normalized)
        except ValueError as exc:
            raise ValueError(f"Unknown tool output visibility: {value}") from exc
    raise ValueError("Tool output visibility must be one of: none, short, full")


def format_tool_result_summary(*, name: str, ok: bool) -> str:
    """Format a terse tool result line for orphaned results."""
    status = "✓" if ok else "✗"
    return f"{status} {name}"


def format_tool_result_block(
    *,
    name: str,
    ok: bool,
    content: str,
    data: dict[str, JSONValue] | None = None,
    visibility: ToolOutputVisibility = ToolOutputVisibility.short,
) -> str:
    """Format a tool result according to the requested visible detail level."""
    status_line = format_tool_result_summary(name=name, ok=ok)
    if visibility is ToolOutputVisibility.none:
        return status_line

    lines = [status_line]
    if content:
        if visibility is ToolOutputVisibility.full:
            lines.append(content)
        else:
            lines.append(preview_text(content, max_lines=TOOL_RESULT_PREVIEW_LINES))

    patch = _result_patch(name=name, ok=ok, data=data)
    if patch:
        lines.append("")
        path = _result_path(data)
        if path:
            lines.append(f"File: {path}")
        lines.append("Diff:")
        if visibility is ToolOutputVisibility.full:
            lines.append(patch)
        else:
            lines.append(preview_text(patch, max_lines=TOOL_PATCH_PREVIEW_LINES))
    return "\n".join(lines)


def format_terminal_command_result_block(
    *,
    ok: bool,
    added_to_context: bool,
    output: str,
) -> str:
    """Format an input-bar terminal command result for visible TUI display."""
    status = "✓" if ok else "✗"
    suffix = " · added to context" if added_to_context else " · not added to context"
    lines = [f"{status} bash{suffix}"]
    if output:
        lines.append(preview_text(output, max_lines=TERMINAL_COMMAND_OUTPUT_PREVIEW_LINES))
    return "\n".join(lines)


def preview_text(
    text: str,
    *,
    max_lines: int,
    max_chars: int = TOOL_RESULT_PREVIEW_CHARS,
) -> str:
    """Return a bounded text preview with a clear truncation marker."""
    lines = text.splitlines()
    if not lines:
        return _clip_text(text, max_chars=max_chars)

    preview_lines = lines[:max_lines]
    preview = "\n".join(preview_lines)
    hidden_lines = max(0, len(lines) - len(preview_lines))

    truncated_by_chars = len(preview) > max_chars
    if truncated_by_chars:
        preview = preview[:max_chars].rstrip()

    if hidden_lines or truncated_by_chars:
        details: list[str] = []
        if hidden_lines:
            details.append(f"{hidden_lines} more line{'s' if hidden_lines != 1 else ''}")
        if truncated_by_chars:
            details.append("additional text")
        preview = f"{preview}\n\n[Preview only: {', '.join(details)} hidden.]"
    return preview


def _clip_text(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}\n\n[Preview only: additional text hidden.]"


def _result_patch(
    *,
    name: str,
    ok: bool,
    data: dict[str, JSONValue] | None,
) -> str | None:
    if name != "edit" or not ok or data is None:
        return None
    patch = data.get("patch")
    return patch if isinstance(patch, str) and patch.strip() else None


def _result_path(data: dict[str, JSONValue] | None) -> str | None:
    if data is None:
        return None
    path = data.get("path")
    return path if isinstance(path, str) and path.strip() else None
