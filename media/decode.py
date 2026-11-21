from dataclasses import dataclass

from media.framing import EncodedVolume, unpack_frame
from media.positions import ReadingPosition, iter_positions


@dataclass(frozen=True)
class DecodedVolume:
    frame_readings: tuple[tuple[int, ...], ...]
    readings: tuple[int, ...]
    positions: tuple[ReadingPosition, ...]

    @property
    def frame_counts(self):
        return tuple(len(frame) for frame in self.frame_readings)


def decode_volume(volume):
    if not isinstance(volume, EncodedVolume):
        raise TypeError('volume must be an EncodedVolume')
    previous_value, previous_delta = volume.header_seed
    frame_readings = []
    for frame_bytes in volume.frames:
        values = []
        for second_delta in unpack_frame(frame_bytes):
            previous_delta += second_delta
            previous_value += previous_delta
            values.append(previous_value)
        frame_readings.append(tuple(values))
    counts = tuple(len(frame) for frame in frame_readings)
    positions = tuple(iter_positions(counts))
    readings = tuple(value for frame in frame_readings for value in frame)
    return DecodedVolume(tuple(frame_readings), readings, positions)
