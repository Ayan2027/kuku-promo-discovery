
import pytest

from src.utils.timestamps import (
    parse_timestamp,
    seconds_to_timestamp,
    validate_interval,
    intervals_overlap,
    calculate_overlap_duration,
)


def test_parse_timestamp():
    assert parse_timestamp("00:12.50") == 12.5
    assert parse_timestamp("01:30.00") == 90.0
    assert parse_timestamp("01:02:30.0") == 3750.0


def test_seconds_to_timestamp():
    assert seconds_to_timestamp(12.5) == "00:12.50"
    assert seconds_to_timestamp(90) == "01:30.00"


def test_invalid_timestamp():
    with pytest.raises(ValueError):
        parse_timestamp("invalid")

    with pytest.raises(ValueError):
        parse_timestamp("00:65.00")


def test_interval_validation():
    assert validate_interval(10, 30)[0] is True

    assert validate_interval(30, 10)[0] is False

    assert validate_interval(10, 50, 40)[0] is False


def test_intervals_overlap():
    assert intervals_overlap(0, 10, 5, 15) is True

    assert intervals_overlap(0, 5, 5, 10) is False


def test_overlap_duration():
    assert calculate_overlap_duration(
        0, 10, 5, 15
    ) == 5

    assert calculate_overlap_duration(
        0, 5, 5, 10
    ) == 0
