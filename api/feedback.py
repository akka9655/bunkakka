try:
    from api.index import app
except ImportError:
    from index import app
