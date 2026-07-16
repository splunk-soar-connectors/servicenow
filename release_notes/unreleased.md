**Unreleased**

* Escape ServiceNow values before embedding them in custom-view JavaScript.
* Validate table names and ticket identifiers before inserting them into ServiceNow REST paths.
* Strip known credential columns before persisting arbitrary table-query results.
* Preserve internationalized URLs when extracting indicators from ServiceNow tickets.
* Bound pagination independently of ServiceNow-provided result counters.
