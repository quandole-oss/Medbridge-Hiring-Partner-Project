"""API key validation middleware.

Authentication is handled via FastAPI dependency injection (see api/dependencies.py)
rather than middleware, so this module exists as a hook point for
future middleware-based auth patterns (e.g., JWT validation).
"""
