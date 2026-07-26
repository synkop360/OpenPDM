"""Composition root for the OpenPDM Platform Modules.

Only this module is allowed to bind public Platform Module contracts to their
current implementations. Application adapters must obtain modules here rather
than importing persistence models or implementation modules directly.
"""

from dataclasses import dataclass

from openpdm.platform_core.modules.audit.implementation import SqlAlchemyAuditEvents
from openpdm.platform_core.modules.services import (
    AssetsModule,
    AuthModule,
    BlobModule,
    CollaborationModule,
    MetadataModule,
    NotificationsModule,
    OrganizationModule,
    PluginsModule,
    ProjectModule,
    RelationshipsModule,
    SearchModule,
    configure_audit_events,
)

AUDIT_EVENTS = SqlAlchemyAuditEvents()
configure_audit_events(AUDIT_EVENTS)


@dataclass(frozen=True, slots=True)
class PlatformModules:
    authentication: type[AuthModule] = AuthModule
    organizations: type[OrganizationModule] = OrganizationModule
    projects: type[ProjectModule] = ProjectModule
    blobs: type[BlobModule] = BlobModule
    assets: type[AssetsModule] = AssetsModule
    relationships: type[RelationshipsModule] = RelationshipsModule
    collaboration: type[CollaborationModule] = CollaborationModule
    metadata: type[MetadataModule] = MetadataModule
    search: type[SearchModule] = SearchModule
    plugins: type[PluginsModule] = PluginsModule
    notifications: type[NotificationsModule] = NotificationsModule


MODULES = PlatformModules()
