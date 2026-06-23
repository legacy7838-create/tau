"""Pi-style final text renderer for print mode."""

import time
from collections.abc import Callable

import typer

from tau_agent import AgentEvent, ErrorEvent, MessageEndEvent
from tau_coding.elapsed import format_elapsed_line


class FinalTextRenderer:
    """Render only the final assistant text after the run finishes."""

    def __init__(
        self,
        *,
        started_at: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        show_elapsed: bool = True,
    ) -> None:
        self._last_assistant_text = ""
        self._failed = False
        self._error_messages: list[str] = []
        self._started_at = clock() if started_at is None else started_at
        self._clock = clock
        self._show_elapsed = show_elapsed

    def render(self, event: AgentEvent) -> None:
        """Record events needed for final text output."""
        if isinstance(event, MessageEndEvent):
            self._last_assistant_text = event.message.content
            return

        if isinstance(event, ErrorEvent):
            if not event.recoverable:
                self._failed = True
            self._error_messages.append(event.message)

    def finish(self) -> bool:
        """Print final text or errors and return whether the run succeeded."""
        if self._failed:
            for message in self._error_messages:
                typer.echo(f"Error: {message}", err=True)
            return False

        if self._last_assistant_text:
            typer.echo(self._last_assistant_text)
        if self._show_elapsed:
            typer.echo(format_elapsed_line(self._clock() - self._started_at), err=True)
        return True
