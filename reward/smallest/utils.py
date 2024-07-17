import decimal


def round_down(x):
    return x.quantize(decimal.Decimal('.000001'), rounding=decimal.ROUND_DOWN)


def split_array_index(arr_len, batch_size=2000):
    for i in range(0, arr_len, batch_size):
        yield i, min(i + batch_size, arr_len)
