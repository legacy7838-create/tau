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
from tau_coding.elapsed import format_elapsed_line, format_elapsed_time
from tau_coding.rendering import FinalTextRenderer, JsonEventRenderer, TranscriptRenderer


def test_format_elapsed_time_uses_short_and_long_forms() -> None:
    assert format_elapsed_time(0.4) == "0:00"
    assert format_elapsed_time(65) == "1:05"
    assert format_elapsed_time(3661) == "1:01:01"
    assert format_elapsed_line(65) == "took tau 1:05"


def test_transcript_renderer_streams_text_and_tool_events(
    capsys: pytest.CaptureFixture[str],
) -> None:
    renderer = TranscriptRenderer(started_at=0, clock=lambda: 65)

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

    assert renderer.finish() is True
    captured = capsys.readouterr()
    assert captured.out == "Hello\n"
    assert "hidden reasoning" not in captured.out
    assert "hidden reasoning" not in captured.err
    assert "… Retrying provider request 2/3 after HTTP 503." in captured.err
    assert "→ read a.py" in captured.err
    assert "… reading" in captured.err
    assert "✓ read" in captured.err
    assert "done" in captured.err
    assert "took tau 1:05" in captured.err


def test_transcript_renderer_fails_on_non_recoverable_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    renderer = TranscriptRenderer()

    renderer.render(ErrorEvent(message="provider failed", recoverable=False))

    captured = capsys.readouterr()
    assert renderer.finish() is False
    assert "Error: provider failed" in captured.err


def test_final_text_renderer_prints_only_final_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    renderer = FinalTextRenderer(show_elapsed=False)

    renderer.render(ThinkingDeltaEvent(delta="hidden reasoning"))
    renderer.render(MessageDeltaEvent(delta="ignored"))
    captured_before_finish = capsys.readouterr()
    ok = renderer.finish()
    captured_after_finish = capsys.readouterr()

    assert ok is True
    assert captured_before_finish.out == ""
    assert captured_after_finish.out == ""
    assert captured_after_finish.err == ""

    renderer = FinalTextRenderer(started_at=0, clock=lambda: 65)
    renderer.render(MessageEndEvent(message=AssistantMessage(content="Final answer")))
    ok = renderer.finish()
    captured = capsys.readouterr()

    assert ok is True
    assert captured.out == "Final answer\n"
    assert captured.err == "took tau 1:05\n"


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
