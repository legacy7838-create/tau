"""Display state for Tau's Textual TUI."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from tau_agent.messages import AgentMessage
from tau_agent.tools import AgentToolResult, ToolCall
from tau_agent.types import JSONValue
from tau_coding.rendering.tool_output import (
    ToolOutputVisibility,
    format_tool_result_block,
    format_tool_result_summary,
)
from tau_coding.skills import parse_skill_invocation

ChatItemRole = Literal["user", "assistant", "tool", "error", "status", "thinking", "skill"]


@dataclass(slots=True)
class ChatItem:
    """One rendered item in the TUI transcript."""

    role: ChatItemRole
    text: str
    tool_call_id: str | None = None
    tool_call: ToolCall | None = None
    tool_result_text: str | None = None
    tool_result: AgentToolResult | None = None
    always_show_tool_result: bool = False


@dataclass(slots=True)
class TuiState:
    """Mutable display state for the interactive TUI."""

    items: list[ChatItem] = field(default_factory=list)
    assistant_buffer: str = ""
    running: bool = False
    error: str | None = None
    tool_output_visibility: ToolOutputVisibility = ToolOutputVisibility.short
    show_thinking: bool = False
    queued_steering: tuple[str, ...] = ()
    queued_follow_up: tuple[str, ...] = ()

    def add_item(
        self,
        role: ChatItemRole,
        text: str,
        *,
        tool_call_id: str | None = None,
        tool_call: ToolCall | None = None,
        tool_result_text: str | None = None,
        tool_result: AgentToolResult | None = None,
        always_show_tool_result: bool = False,
    ) -> None:
        """Append a transcript item."""
        self.items.append(
            ChatItem(
                role=role,
                text=text,
                tool_call_id=tool_call_id,
                tool_call=tool_call,
                tool_result_text=tool_result_text,
                tool_result=tool_result,
                always_show_tool_result=always_show_tool_result,
            )
        )

    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Append a collapsed tool-call item."""
        self.add_item(
            "tool",
            format_tool_call_block(tool_call),
            tool_call_id=tool_call.id,
            tool_call=tool_call,
        )

    def add_user_message(self, content: str) -> None:
        """Append a user-authored message, compacting skill invocations for display."""
        skill_invocation = parse_skill_invocation(content)
        if skill_invocation is None:
            self.add_item("user", content)
            return
        self.add_item("skill", f"Using skill: {skill_invocation.name}")
        if skill_invocation.additional_instructions:
            self.add_item("user", skill_invocation.additional_instructions)

    def add_thinking_delta(self, delta: str) -> None:
        """Append a thinking/reasoning fragment to the current thinking block."""
        if self.items and self.items[-1].role == "thinking":
            self.items[-1].text += delta
            return
        self.add_item("thinking", delta)

    def record_tool_result(self, result: AgentToolResult) -> None:
        """Attach a tool result to its matching call, or append an orphan result."""
        for item in reversed(self.items):
            if item.role == "tool" and item.tool_call_id == result.tool_call_id:
                result = _result_with_tool_call_context(result, item.tool_call)
                result_text = format_tool_result_block(
                    name=result.name,
                    ok=result.ok,
                    content=result.content,
                    data=result.data,
                    visibility=self.tool_output_visibility,
                )
                item.tool_result_text = result_text
                item.tool_result = result
                return
        result_text = format_tool_result_block(
            name=result.name,
            ok=result.ok,
            content=result.content,
            data=result.data,
            visibility=self.tool_output_visibility,
        )
        self.add_item(
            "tool",
            format_tool_result_summary(name=result.name, ok=result.ok),
            tool_call_id=result.tool_call_id,
            tool_result_text=result_text,
            tool_result=result,
        )

    @property
    def show_tool_results(self) -> bool:
        """Return whether any tool result detail is visible."""
        return self.tool_output_visibility is not ToolOutputVisibility.none

    @show_tool_results.setter
    def show_tool_results(self, value: bool) -> None:
        """Compatibility setter for the old collapsed/expanded boolean state."""
        self.set_tool_output_visibility(
            ToolOutputVisibility.short if value else ToolOutputVisibility.none
        )

    def set_tool_output_visibility(self, visibility: ToolOutputVisibility) -> None:
        """Set tool-output visibility and refresh cached result text."""
        self.tool_output_visibility = visibility
        self._refresh_tool_result_text()

    def cycle_tool_output_visibility(self) -> ToolOutputVisibility:
        """Cycle visible tool output through short, full, and none."""
        order = (
            ToolOutputVisibility.short,
            ToolOutputVisibility.full,
            ToolOutputVisibility.none,
        )
        next_index = (order.index(self.tool_output_visibility) + 1) % len(order)
        self.set_tool_output_visibility(order[next_index])
        return self.tool_output_visibility

    def toggle_tool_results(self) -> bool:
        """Toggle expanded display for tool results and return the new state."""
        self.set_tool_output_visibility(
            ToolOutputVisibility.none if self.show_tool_results else ToolOutputVisibility.short
        )
        return self.show_tool_results

    def toggle_thinking(self) -> bool:
        """Toggle thinking-token display and return the new state."""
        self.show_thinking = not self.show_thinking
        return self.show_thinking

    def update_queue(self, *, steering: tuple[str, ...], follow_up: tuple[str, ...]) -> None:
        """Replace visible queued-message state."""
        self.queued_steering = steering
        self.queued_follow_up = follow_up

    @property
    def queued_message_count(self) -> int:
        """Return the total number of pending queued messages."""
        return len(self.queued_steering) + len(self.queued_follow_up)

    def clear(self) -> None:
        """Clear visible transcript state without modifying durable session history."""
        self.items.clear()
        self.assistant_buffer = ""
        self.error = None

    def _refresh_tool_result_text(self) -> None:
        for item in self.items:
            if item.tool_result is None:
                continue
            item.tool_result_text = format_tool_result_block(
                name=item.tool_result.name,
                ok=item.tool_result.ok,
                content=item.tool_result.content,
                data=item.tool_result.data,
                visibility=self.tool_output_visibility,
            )

    def load_messages(self, messages: Iterable[AgentMessage]) -> None:
        """Populate the transcript from restored session messages."""
        for message in messages:
            if message.role == "user":
                self.add_user_message(message.content)
            elif message.role == "assistant":
                if message.content:
                    self.add_item("assistant", message.content)
                for tool_call in message.tool_calls:
                    self.add_tool_call(tool_call)
            elif message.role == "tool":
                self.record_tool_result(
                    AgentToolResult(
                        tool_call_id=message.tool_call_id,
                        name=message.name,
                        ok=message.ok,
                        content=message.content,
                        data=message.data,
                        details=message.details,
                        error=message.error,
                    )
                )


def format_tool_call_block(tool_call: ToolCall) -> str:
    """Format a collapsed tool call for live and restored transcript blocks."""
    invocation = format_tool_call_invocation(tool_call)
    if tool_call.name == "bash":
        return invocation
    return f"→ {invocation}"


def format_tool_call_invocation(tool_call: ToolCall) -> str:
    """Format a tool call as a terse human-readable invocation."""
    arguments = tool_call.arguments
    if tool_call.name == "read":
        path = _string_argument(arguments, "path")
        if path is None:
            return _fallback_tool_call_invocation(tool_call)
        return f"read {path}{_read_line_suffix(arguments)}"
    if tool_call.name == "edit":
        path = _string_argument(arguments, "path")
        if path is None:
            return _fallback_tool_call_invocation(tool_call)
        return f"edit {path}"
    if tool_call.name == "write":
        path = _string_argument(arguments, "path")
        if path is None:
            return _fallback_tool_call_invocation(tool_call)
        return f"write {path}"
    if tool_call.name == "bash":
        command = _string_argument(arguments, "command")
        if command is None:
            return _fallback_tool_call_invocation(tool_call)
        timeout = _number_argument(arguments, "timeout")
        suffix = f" (timeout {timeout:g}s)" if timeout is not None else ""
        return f"$ {command}{suffix}"
    return _fallback_tool_call_invocation(tool_call)


def _read_line_suffix(arguments: dict[str, JSONValue]) -> str:
    offset = _int_argument(arguments, "offset")
    limit = _int_argument(arguments, "limit")
    if offset is None and limit is None:
        return ""
    start = 1 if offset is None else max(1, offset)
    if limit is None:
        return f":{start}-"
    return f":{start}-{start + max(1, limit) - 1}"


def _fallback_tool_call_invocation(tool_call: ToolCall) -> str:
    if tool_call.arguments:
        return f"{tool_call.name} {tool_call.arguments}"
    return tool_call.name


def _string_argument(arguments: dict[str, JSONValue], key: str) -> str | None:
    value = arguments.get(key)
    return value if isinstance(value, str) else None


def _int_argument(arguments: dict[str, JSONValue], key: str) -> int | None:
    value = arguments.get(key)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _number_argument(arguments: dict[str, JSONValue], key: str) -> int | float | None:
    value = arguments.get(key)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int | float) else None


def _result_with_tool_call_context(
    result: AgentToolResult,
    tool_call: ToolCall | None,
) -> AgentToolResult:
    if result.name != "edit" or tool_call is None:
        return result
    path = _string_argument(tool_call.arguments, "path")
    if path is None:
        return result
    data = dict(result.data or {})
    if isinstance(data.get("path"), str):
        return result
    data["path"] = path
    return result.model_copy(update={"data": data})
