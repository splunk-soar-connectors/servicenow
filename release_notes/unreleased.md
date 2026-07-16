**Unreleased**

* Escape ServiceNow values before embedding them in custom-view JavaScript.
* Validate table names and ticket identifiers before inserting them into ServiceNow REST paths.
* Strip known credential columns before persisting arbitrary table-query results.
* Preserve internationalized URLs when extracting indicators from ServiceNow tickets.
* Bound pagination independently of ServiceNow-provided result counters.
* Redact OAuth token endpoint responses from connector debug logs.
* Scope polling deduplication lookups to containers created by the current asset.
* Advance scheduled-poll checkpoints only after all fetched records and artifacts are saved.
