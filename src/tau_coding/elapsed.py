"""Elapsed-time formatting for Tau coding frontends."""


def format_elapsed_time(seconds: float) -> str:
    """Format elapsed seconds as M:SS or H:MM:SS."""
    total_seconds = max(0, round(seconds))
    minutes, seconds_part = divmod(total_seconds, 60)
    hours, minutes_part = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes_part:02d}:{seconds_part:02d}"
    return f"{minutes_part}:{seconds_part:02d}"


def format_elapsed_line(seconds: float) -> str:
    """Format Tau's user-facing elapsed-time line."""
    return f"took tau {format_elapsed_time(seconds)}"
