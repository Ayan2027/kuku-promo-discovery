
import re
from typing import Optional


TIMESTAMP_PATTERN = re.compile(
    r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2}(?:\.\d+)?)$"
)


def parse_timestamp(timestamp: str) -> float:
    """
    Convert MM:SS.ss or HH:MM:SS.ss into seconds.

    Examples:
        00:12.50    -> 12.5
        01:30.00    -> 90.0
        01:02:30.0  -> 3750.0
    """
    if not isinstance(timestamp, str):
        raise TypeError("Timestamp must be a string.")

    value = timestamp.strip()

    match = TIMESTAMP_PATTERN.fullmatch(value)

    if not match:
        raise ValueError(
            f"Invalid timestamp format: {timestamp}"
        )

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = float(match.group(3))

    if seconds >= 60:
        raise ValueError("Seconds must be less than 60.")

    if match.group(1) is not None and minutes >= 60:
        raise ValueError("Minutes must be less than 60 in HH:MM:SS.")

    if match.group(1) is None and minutes >= 60:
        raise ValueError("Minutes must be less than 60.")

    return hours * 3600 + minutes * 60 + seconds


def seconds_to_timestamp(seconds: float) -> str:
    """
    Convert seconds into MM:SS.ss.
    """
    if seconds < 0:
        raise ValueError("Seconds cannot be negative.")

    total_centiseconds = round(seconds * 100)

    total_seconds, centiseconds = divmod(
        total_centiseconds, 100
    )

    minutes, remaining_seconds = divmod(
        total_seconds, 60
    )

    return (
        f"{minutes:02d}:"
        f"{remaining_seconds:02d}."
        f"{centiseconds:02d}"
    )


def validate_interval(
    start: float,
    end: float,
    episode_duration: Optional[float] = None
) -> tuple[bool, str]:
    """
    Validate a time interval against episode boundaries.
    """

    if start < 0:
        return False, "Start timestamp is negative."

    if end <= start:
        return False, "End must be greater than start."

    if episode_duration is not None and end > episode_duration:
        return False, "End exceeds episode duration."

    return True, "Valid interval."


def intervals_overlap(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float
) -> bool:
    """
    Check whether two intervals overlap.

    Overlapping segments are allowed in screenplays.
    """

    return start_a < end_b and start_b < end_a


def calculate_overlap_duration(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float
) -> float:
    """
    Return the duration of the overlap between two intervals.
    """

    return max(
        0.0,
        min(end_a, end_b) - max(start_a, start_b)
    )
