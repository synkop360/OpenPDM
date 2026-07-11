"""Post-commit event dispatcher coordinated through public contracts."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from openpdm.extension_api import InvocationResponse, validate_plugin_package
from openpdm.infrastructure.plugin_packages import PluginPackageStorage
from openpdm.platform_core.modules.services import PluginsModule
from openpdm.plugin_runtime.supervisor import WasmtimeWorkerSupervisor


def dispatch_due_plugin_events(
    db: Session,
    *,
    package_storage: PluginPackageStorage,
    supervisor: WasmtimeWorkerSupervisor,
    limit: int = 100,
) -> int:
    """Attempt each due delivery once in deterministic per-plugin order."""

    processed = 0
    for delivery in PluginsModule.list_due_event_deliveries(db, limit=limit):
        try:
            archive = package_storage.read(delivery.package_digest)
            package = validate_plugin_package(archive)
            if (
                package.digest != delivery.package_digest
                or package.manifest.id != delivery.plugin_id
            ):
                raise ValueError("Installed plugin package integrity check failed.")
            result = supervisor.invoke(
                package.component,
                export_name="handle-event",
                arguments=[json.dumps(delivery.payload, sort_keys=True, separators=(",", ":"))],
            )
            if not result.success or result.result is None:
                raise ValueError(result.diagnostic_reason or "Plugin event handler failed.")
            response = InvocationResponse.model_validate_json(result.result)
            if not response.success:
                raise ValueError(
                    response.error.message if response.error else "Plugin event handler failed."
                )
        except Exception as exc:
            PluginsModule.record_event_delivery_result(
                db,
                delivery_id=delivery.id,
                success=False,
                diagnostic_reason=" ".join(str(exc).split())[:1024],
            )
        else:
            PluginsModule.record_event_delivery_result(
                db, delivery_id=delivery.id, success=True, diagnostic_reason=None
            )
        processed += 1
    return processed
