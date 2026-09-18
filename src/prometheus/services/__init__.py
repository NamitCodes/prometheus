"""Application services -- the layer CLI/API handlers call into.

CLI and (eventually) FastAPI routes must go through here rather than
touching SQLAlchemy/ChromaDB directly (new-plan.md section 4).
"""
