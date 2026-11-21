from dataclasses import dataclass

from receive.provenance import ReceivedReading


@dataclass(frozen=True)
class ThresholdResult:
    anomalies: tuple[ReceivedReading, ...]
    peak: int | None


def validate_threshold(threshold):
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
        raise ValueError('threshold must be a non-negative integer')
    return threshold


def evaluate_threshold(readings, threshold):
    validate_threshold(threshold)
    values = tuple(readings)
    anomalies = tuple(reading for reading in values if abs(reading.value) >= threshold)
    peak = max((abs(reading.value) for reading in values), default=None)
    return ThresholdResult(anomalies, peak)
