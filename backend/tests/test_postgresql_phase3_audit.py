"""Optional PostgreSQL integration coverage for ADR-0032 transaction durability."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from openpdm.infrastructure.database import get_session_factory, initialize_database
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.audit import AuditOutcome, Phase3AuditContext
from openpdm.platform_core.modules.audit.implementation import SqlAlchemyAuditEvents
from openpdm.platform_core.modules.models import AuditRecord, User


def test_failed_phase3_audit_survives_business_rollback_on_postgresql() -> None:
    database_url = os.getenv("OPENPDM_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("Set OPENPDM_TEST_POSTGRES_URL to run PostgreSQL audit integration tests.")
    settings = Settings(database_url=database_url)
    initialize_database(settings)
    factory = get_session_factory(settings)
    actor_id = str(uuid4())
    request_resource_id = str(uuid4())

    with factory() as setup_db:
        setup_db.add(
            User(
                id=actor_id,
                email=f"audit-{actor_id}@example.com",
                display_name="ADR-0032 audit test",
                password_hash="not-used",
            )
        )
        setup_db.commit()

    business_db = factory()
    try:
        business_db.add(
            User(
                email=f"rollback-{actor_id}@example.com", display_name="rollback", password_hash="x"
            )
        )
        business_db.rollback()
        SqlAlchemyAuditEvents().record_phase3_outcome(
            business_db,
            context=Phase3AuditContext(
                actor_user_id=actor_id,
                event_type="RelationshipCreated",
                resource_type="relationship",
                resource_id=request_resource_id,
                source_asset_id=request_resource_id,
                target_asset_id=str(uuid4()),
            ),
            outcome=AuditOutcome("failed", "Persistence failure."),
            independent=True,
        )
    finally:
        business_db.close()

    with factory() as verification_db:
        audit = verification_db.scalar(
            select(AuditRecord).where(AuditRecord.resource_id == request_resource_id)
        )
        assert audit is not None
        assert audit.details["result"] == "failed"
        verification_db.execute(
            delete(AuditRecord).where(AuditRecord.resource_id == request_resource_id)
        )
        verification_db.execute(delete(User).where(User.id == actor_id))
        verification_db.commit()
