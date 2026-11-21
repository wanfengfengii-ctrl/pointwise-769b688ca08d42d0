from dataclasses import dataclass

from media.positions import ReadingPosition
from receive.provenance import ReceivedReading
from station.provenance import FrameSource


@dataclass(frozen=True)
class RetestRow:
    value: int
    position: ReadingPosition
    source: FrameSource


def build_dispatch(readings):
    return tuple(RetestRow(reading.value, reading.position, reading.source) for reading in readings)
