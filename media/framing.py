import json
from dataclasses import dataclass

from media.integers import decode_signed, encode_signed

V1_VERSION = 1


@dataclass(frozen=True)
class EncodedVolume:
    header_seed: tuple[int, int]
    frames: tuple[bytes, ...]

    @property
    def header(self):
        return pack_header(*self.header_seed)


def pack_header(previous_value=0, previous_delta=0):
    if isinstance(previous_value, bool) or not isinstance(previous_value, int):
        raise ValueError('header previous value must be an integer')
    if isinstance(previous_delta, bool) or not isinstance(previous_delta, int):
        raise ValueError('header previous delta must be an integer')
    value = {'seed': [encode_signed(previous_value), encode_signed(previous_delta)], 'version': V1_VERSION}
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'), sort_keys=True).encode('ascii')


def unpack_header(data):
    try:
        value = json.loads(bytes(data).decode('ascii'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError('invalid volume header') from error
    if not isinstance(value, dict) or value.get('version') != V1_VERSION or not isinstance(value.get('seed'), list) or len(value['seed']) != 2:
        raise ValueError('invalid volume header')
    return decode_signed(value['seed'][0]), decode_signed(value['seed'][1])


def pack_frame(values):
    encoded = []
    for value in values:
        encoded.append(encode_signed(value))
    return json.dumps(encoded, ensure_ascii=True, separators=(',', ':')).encode('ascii')


def unpack_frame(data):
    try:
        value = json.loads(bytes(data).decode('ascii'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError('invalid volume frame') from error
    if not isinstance(value, list):
        raise ValueError('invalid volume frame')
    return tuple(decode_signed(item) for item in value)
