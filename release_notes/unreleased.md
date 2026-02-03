**Unreleased**

* Migrated the app to the Splunk SOAR SDK.
* Added the `make request` action for issuing arbitrary requests to ServiceNow API endpoints.
* Updated severity lookup to use the SOAR `/rest/container_options` endpoint, which only requires container view permissions available to the automation role by default.
