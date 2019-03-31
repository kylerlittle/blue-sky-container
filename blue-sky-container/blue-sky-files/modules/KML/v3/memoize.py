__all__ = ['memoizeme']

def _memoize_cache_key(*args, **kwargs):
    return '/'.join([
        '-'.join([str(a) for a in args]), #str(args),
        '-'.join(['='.join([e[0],str(e[1])]) for e in kwargs.items()]) #str(kwargs)
    ])


def memoizeme(f):
    cache = {}

    def memoized(*args, **kwargs):
        key = _memoize_cache_key(*args, **kwargs)
        if key not in cache:
            cache[key] = f(*args, **kwargs)
        return cache[key]

    return memoized
