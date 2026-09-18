"""Versioned API routes (new-plan.md section 50), mounted under /api/v1.

Each route module calls the same `prometheus.services.*` functions the CLI
uses -- no business logic lives here, matching new-plan.md section 7's
architectural boundary (CLI and API are both just clients of the same
application services).
"""
