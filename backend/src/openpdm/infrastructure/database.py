"""Database infrastructure boundary for PostgreSQL.

Phase 0 defines the dependency boundary only. Schema and repositories are
introduced with Platform Core capabilities in later phases.
"""

from sqlalchemy import MetaData

metadata = MetaData()
