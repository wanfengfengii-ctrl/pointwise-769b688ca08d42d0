from dataclasses import dataclass


@dataclass(frozen=True)
class ReadingPosition:
    frame_index: int
    reading_index: int
    ordinal: int


@dataclass(frozen=True)
class PositionedReading:
    position: ReadingPosition
    value: int


def iter_positions(frame_reading_counts):
    ordinal = 0
    for frame_index, count in enumerate(frame_reading_counts):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('frame reading count must be a non-negative integer')
        for reading_index in range(count):
            yield ReadingPosition(frame_index, reading_index, ordinal)
            ordinal += 1
