#!/usr/bin/env python
"""
CLI script: initialize the Findings DB schema (and optionally seed it with
sample reports for local development / demos).

Usage (once implemented):
    python scripts/seed_findings_db.py --with-sample-data

TODO:
  - Create tables from prometheus.findings.models (Base.metadata.create_all)
  - Optional --with-sample-data flag to insert a couple of fake reports so
    the Streamlit dashboard has something to show before Phase 3 is done
"""

if __name__ == "__main__":
    raise NotImplementedError("Phase 1: implement DB seeding CLI")
