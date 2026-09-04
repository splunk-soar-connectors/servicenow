**Unreleased**

* Migrated the app to the Splunk SOAR SDK.
* Added the `make request` action for issuing arbitrary requests to ServiceNow API endpoints.
* Added OAuth client credentials grant support.
* Added an explicit basic_auth option so assets can use Basic Auth even when OAuth secrets remain saved in the UI.
* Updated On Poll to honor SOAR-provided `start_time` and `end_time` parameters when supplied as epoch milliseconds.
* Updated severity lookup to use the SOAR `/rest/container_options` endpoint, which only requires container view permissions available to the automation role by default.
* Updated scheduled On Poll checkpointing to use deterministic `sys_updated_on` and `sys_id` ordering, allowing records sharing a timestamp to be processed across poll limits.
