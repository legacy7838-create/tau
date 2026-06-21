import json

import pytest

from tau_agent import (
    AgentToolResult,
    AssistantMessage,
    ErrorEvent,
    MessageDeltaEvent,
    MessageEndEvent,
    MessageStartEvent,
    QueueUpdateEvent,
    RetryEvent,
    ThinkingDeltaEvent,
    ToolCall,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
)
from tau_coding.rendering import FinalTextRenderer, JsonEventRenderer, TranscriptRenderer
from tau_coding.rendering.tool_output import ToolOutputVisibility, format_tool_result_block


def test_tool_result_block_supports_visibility_levels() -> None:
    content = "\n".join(f"line {index}" for index in range(1, 12))

    none = format_tool_result_block(
        name="read",
        ok=True,
        content=content,
        visibility=ToolOutputVisibility.none,
    )
    short = format_tool_result_block(
        name="read",
        ok=True,
        content=content,
        visibility=ToolOutputVisibility.short,
    )
    full = format_tool_result_block(
        name="read",
        ok=True,
        content=content,
        visibility=ToolOutputVisibility.full,
    )

    assert none == "✓ read"
    assert "line 1" in short
    assert "line 8" in short
    assert "line 9" not in short
    assert "3 more lines" in short
    assert "line 11" in full
    assert "Preview only" not in full


def test_tool_result_block_formats_edit_diff_preview() -> None:
    patch = "\n".join(["--- a.py", "+++ a.py", "@@"] + [f"+line {index}" for index in range(40)])

    block = format_tool_result_block(
        name="edit",
        ok=True,
        content="Successfully replaced 1 block.",
        data={"path": "a.py", "patch": patch},
        visibility=ToolOutputVisibility.short,
    )

    assert "Successfully replaced 1 block." in block
    assert "File: a.py" in block
    assert "Diff:" in block
    assert "--- a.py" in block
    assert "+line 28" in block
    assert "+line 32" not in block
    assert "Preview only" in block


def test_transcript_renderer_streams_text_and_tool_events(
    capsys: pytest.CaptureFixture[str],
) -> None:
    renderer = TranscriptRenderer()

    renderer.render(MessageStartEvent())
    renderer.render(ThinkingDeltaEvent(delta="hidden reasoning"))
    renderer.render(MessageDeltaEvent(delta="Hel"))
    renderer.render(MessageDeltaEvent(delta="lo"))
    renderer.render(
        RetryEvent(
            attempt=2,
            max_attempts=3,
            delay_seconds=0,
            message="Retrying provider request 2/3 after HTTP 503.",
        )
    )
    renderer.render(
        ToolExecutionStartEvent(
            tool_call=ToolCall(id="call-1", name="read", arguments={"path": "a.py"})
        )
    )
    renderer.render(ToolExecutionUpdateEvent(tool_call_id="call-1", message="reading"))
    renderer.render(
        ToolExecutionEndEvent(
            result=AgentToolResult(tool_call_id="call-1", name="read", ok=True, content="done")
        )
    )

    captured = capsys.readouterr()
    assert renderer.finish() is True
    assert captured.out == "Hello\n"
    assert "hidden reasoning" not in captured.out
    assert "hidden reasoning" not in captured.err
    assert "… Retrying provider request 2/3 after HTTP 503." in captured.err
    assert "→ read a.py" in captured.err
    assert "… reading" in captured.err
    assert "✓ read" in captured.err
    assert "done" in captured.err


def test_transcript_renderer_fails_on_non_recoverable_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    renderer = TranscriptRenderer()

    renderer.render(ErrorEvent(message="provider failed", recoverable=False))

    captured = capsys.readouterr()
    assert renderer.finish() is False
    assert "Error: provider failed" in captured.err


def test_transcript_renderer_respects_tool_output_visibility(
    capsys: pytest.CaptureFixture[str],
) -> None:
    renderer = TranscriptRenderer(tool_output_visibility=ToolOutputVisibility.none)

    renderer.render(
        ToolExecutionEndEvent(
            result=AgentToolResult(
                tool_call_id="call-1",
                name="read",
                ok=True,
                content="hidden content",
            )
        )
    )

    captured = capsys.readouterr()
    assert "✓ read" in captured.err
    assert "hidden content" not in captured.err


def test_final_text_renderer_prints_only_final_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    renderer = FinalTextRenderer()

    renderer.render(ThinkingDeltaEvent(delta="hidden reasoning"))
    renderer.render(MessageDeltaEvent(delta="ignored"))
    captured_before_finish = capsys.readouterr()
    ok = renderer.finish()
    captured_after_finish = capsys.readouterr()

    assert ok is True
    assert captured_before_finish.out == ""
    assert captured_after_finish.out == ""
    assert captured_after_finish.err == ""

    renderer.render(MessageEndEvent(message=AssistantMessage(content="Final answer")))
    ok = renderer.finish()
    captured = capsys.readouterr()

    assert ok is True
    assert captured.out == "Final answer\n"


def test_final_text_renderer_prints_errors_on_finish(capsys: pytest.CaptureFixture[str]) -> None:
    renderer = FinalTextRenderer()

    renderer.render(ErrorEvent(message="provider failed", recoverable=False))
    before_finish = capsys.readouterr()
    ok = renderer.finish()
    after_finish = capsys.readouterr()

    assert ok is False
    assert before_finish.err == ""
    assert "Error: provider failed" in after_finish.err


def test_json_renderer_emits_jsonl(capsys: pytest.CaptureFixture[str]) -> None:
    renderer = JsonEventRenderer()

    renderer.render(MessageStartEvent())
    renderer.render(QueueUpdateEvent(steering=("adjust",), follow_up=("after",)))
    renderer.render(ThinkingDeltaEvent(delta="hidden reasoning"))
    renderer.render(ErrorEvent(message="provider failed", recoverable=False))

    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert json.loads(lines[0]) == {"type": "message_start", "message_role": "assistant"}
    assert json.loads(lines[1]) == {
        "type": "queue_update",
        "steering": ["adjust"],
        "follow_up": ["after"],
    }
    assert json.loads(lines[2]) == {"type": "thinking_delta", "delta": "hidden reasoning"}
    assert json.loads(lines[3])["type"] == "error"
    assert renderer.finish() is False
