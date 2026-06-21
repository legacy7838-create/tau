"""Event renderers for Tau coding frontends and print modes."""

from tau_coding.rendering.base import EventRenderer, PrintOutputMode
from tau_coding.rendering.json import JsonEventRenderer
from tau_coding.rendering.plain import FinalTextRenderer
from tau_coding.rendering.tool_output import (
    ToolOutputVisibility,
    format_terminal_command_result_block,
    format_tool_result_block,
    format_tool_result_summary,
    normalize_tool_output_visibility,
    preview_text,
)
from tau_coding.rendering.transcript import TranscriptRenderer


def create_event_renderer(
    mode: PrintOutputMode,
    *,
    tool_output_visibility: ToolOutputVisibility = ToolOutputVisibility.short,
) -> EventRenderer:
    """Create a renderer for a print output mode."""
    if mode is PrintOutputMode.text:
        return FinalTextRenderer()
    if mode is PrintOutputMode.json:
        return JsonEventRenderer()
    return TranscriptRenderer(tool_output_visibility=tool_output_visibility)


__all__ = [
    "EventRenderer",
    "FinalTextRenderer",
    "JsonEventRenderer",
    "PrintOutputMode",
    "TranscriptRenderer",
    "ToolOutputVisibility",
    "create_event_renderer",
    "format_terminal_command_result_block",
    "format_tool_result_block",
    "format_tool_result_summary",
    "normalize_tool_output_visibility",
    "preview_text",
]
