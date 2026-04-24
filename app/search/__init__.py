"""Elasticsearch client, index management, and document mapping."""

from app.search.es_client import close_es, get_es

__all__ = ["get_es", "close_es"]
