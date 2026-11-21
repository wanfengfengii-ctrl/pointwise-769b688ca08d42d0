def encode_signed(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('value must be an integer')
    if value < 0:
        return '-' + format(-value, 'x')
    return format(value, 'x')


def decode_signed(value):
    if not isinstance(value, str) or not value:
        raise ValueError('encoded integer must be a non-empty string')
    if value.startswith('-'):
        digits = value[1:]
        if not digits:
            raise ValueError('encoded integer has no digits')
        return -int(digits, 16)
    return int(value, 16)
