from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import select

from openpdm.extension_api import (
    Capability,
    InvocationResponse,
    PluginManifest,
    build_plugin_package,
)
from openpdm.infrastructure.database import dispose_engines, initialize_database, session_scope
from openpdm.infrastructure.plugin_packages import PluginPackageStorage
from openpdm.infrastructure.plugin_secrets import PluginSecretCipher
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.models import (
    AuditRecord,
    PluginConfiguration,
    PluginEventDelivery,
    PluginRecord,
    User,
)
from openpdm.platform_core.modules.services import PluginsModule, emit_event
from openpdm.plugin_runtime.dispatcher import dispatch_due_plugin_events
from openpdm.plugin_runtime.supervisor import RuntimeResult


class SuccessfulSupervisor:
    def invoke(
        self, component: bytes, *, export_name: str, arguments: list[str] | None = None
    ) -> RuntimeResult:
        assert component.startswith(b"\x00asm")
        assert export_name == "handle-event"
        assert arguments and "AssetCreated" in arguments[0]
        return RuntimeResult(True, result=InvocationResponse(success=True).model_dump_json())


def settings_for(tmp_path: Path) -> Settings:
    dispose_engines()
    return Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'events.db'}",
        plugin_package_root=str(tmp_path / "plugins"),
    )


def test_plugin_configuration_secrets_are_encrypted_and_never_audited(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    initialize_database(settings)
    cipher = PluginSecretCipher(Fernet.generate_key().decode())
    with session_scope(settings) as db:
        admin = User(
            email="admin@example.com",
            display_name="Admin",
            password_hash="unused",
            is_platform_admin=True,
        )
        plugin = PluginRecord(
            id="org.openpdm.config-test",
            name="Config Test",
            version="1.0.0",
            plugin_type="community",
            capabilities=["metadata_provider"],
            configuration_schema={
                "type": "object",
                "properties": {
                    "prefix": {"type": "string", "secret": False},
                    "token": {"type": "string", "secret": True},
                },
                "required": ["prefix", "token"],
                "additionalProperties": False,
            },
        )
        db.add_all([admin, plugin])
        db.flush()
        PluginsModule.set_configuration(
            db,
            plugin_id=plugin.id,
            values={"prefix": "safe", "token": "hostile-secret"},
            actor=admin,
            cipher=cipher,
        )

    with session_scope(settings) as db:
        configuration = db.get(PluginConfiguration, "org.openpdm.config-test")
        assert configuration is not None
        assert configuration.public_values == {"prefix": "safe"}
        assert configuration.encrypted_secrets is not None
        assert "hostile-secret" not in configuration.encrypted_secrets
        assert cipher.decrypt(configuration.encrypted_secrets) == {"token": "hostile-secret"}
        audit = db.scalar(
            select(AuditRecord).where(AuditRecord.action == "plugin.configuration.updated")
        )
        assert audit is not None
        assert "hostile-secret" not in str(audit.details)


def test_post_commit_delivery_is_persisted_and_dispatched_once(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    initialize_database(settings)
    storage = PluginPackageStorage(settings.plugin_package_root)
    archive = build_plugin_package(
        PluginManifest(
            id="org.openpdm.event-test",
            name="Event Test",
            version="1.0.0",
            extension_api_versions=[1],
            component="plugin.wasm",
            capabilities=[Capability.EVENT_HANDLER],
            event_subscriptions=["AssetCreated"],
        ),
        b"\x00asm\x0d\x00\x01\x00",
    )
    package = storage.put(hashlib.sha256(archive).hexdigest(), archive)
    assert Path(package).is_file()
    digest = Path(package).stem

    with session_scope(settings) as db:
        plugin = PluginRecord(
            id="org.openpdm.event-test",
            name="Event Test",
            version="1.0.0",
            plugin_type="community",
            capabilities=["event_handler"],
            event_subscriptions=["AssetCreated"],
            extension_api_versions=[1],
            component="plugin.wasm",
            package_digest=digest,
            lifecycle_state="running",
            enabled=True,
        )
        db.add(plugin)
        db.flush()
        emit_event(db, event_type="AssetCreated", resource_type="asset", resource_id="asset-1")

    with session_scope(settings) as db:
        delivery = db.scalar(select(PluginEventDelivery))
        assert delivery is not None
        assert delivery.status == "pending"
        processed = dispatch_due_plugin_events(
            db,
            package_storage=storage,
            supervisor=SuccessfulSupervisor(),  # type: ignore[arg-type]
        )
        assert processed == 1

    with session_scope(settings) as db:
        delivery = db.scalar(select(PluginEventDelivery))
        assert delivery is not None
        assert delivery.status == "delivered"
        assert delivery.attempt_count == 1
