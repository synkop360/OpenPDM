# Platform Modules

Platform Modules under this package implement the current Platform Core capabilities and expose their facades through the composition root.

Each Platform Module must:

* own one business responsibility;
* expose a Public Module Interface;
* keep internal implementation details private to the module;
* communicate with other Platform Modules only through Public Module Interfaces.

The current composition includes Authentication, Organization, Project, Assets, Blobs, Relationships, Collaboration, Metadata, Search, Plugins and Notifications capabilities. Audit and domain-event behavior is provided through its public audit contract and configured implementation.

Organization membership and Project role assignment remain separate responsibilities. Application-layer orchestration coordinates cross-module Organization removal through public operations; the Organization Platform Module does not depend on Project internals.
