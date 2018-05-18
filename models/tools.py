from itertools import count, zip_longest

def range_chunk(iterable, chunksize=1):
    """Iterate over iterable in chunks of a specified size"""
    chunk_iterator = (filter(None, x)
                      for x in zip_longest(*([iter(iterable)] * chunksize)))
    for start, chunk in zip(count(step=chunksize), chunk_iterator):
        chunk = list(chunk)
        yield (range(start, start+len(chunk)), chunk)
