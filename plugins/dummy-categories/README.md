# Asset Categories API Test Plugin

This Community Plugin is a domain-neutral Extension API v1 demonstration. “Category” is stored as generic metadata owned by the plugin; it is not a Platform Core concept.

The plugin demonstrates:

* an Asset Provider that creates an authorized Asset with a configured name prefix;
* a Metadata Provider that contributes `classification.category` and `classification.managed_by`;
* an Option Provider that publishes selectable document, drawing, model and assembly categories;
* an idempotent event hook subscribed to committed `asset.created` events;
* deployment-scoped configuration for the default category and name prefix.

Build and run its end-to-end API test:

```bash
uv run python scripts/build_dummy_categories_plugin.py
uv run pytest backend/tests/test_dummy_categories_plugin_e2e.py -v
```

The package is emitted under `plugins/dummy-categories/dist/`. Install it as a Community Plugin through `POST /plugins/packages`, configure it, and enable it. The Web UI then discovers its provider capabilities, presents its category options and can apply the selected category as generic Asset metadata. The same workflow is available through the routes documented in [`docs/API_REFERENCE.md`](../../docs/API_REFERENCE.md).
