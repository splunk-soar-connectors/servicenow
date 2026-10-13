**Unreleased**

* Migrated the app to the Splunk SOAR SDK.
* Minimum supported Splunk SOAR version is 7.0.0.
* Added the `make request` action for issuing arbitrary requests to ServiceNow API endpoints.
* Added OAuth client credentials authentication support.
* Added the `oauth_grant_type` asset setting. Select `basic_auth`, `password_grant`, or `client_credentials` to match the asset's authentication method.
* Existing Basic Auth assets with only a username and password continue to work after upgrade. If a client secret is also saved without a client ID, select `basic_auth` in `oauth_grant_type`.
* Added options to extract IP addresses, hashes, and URLs during On Poll.
* Updated scheduled polling to use UTC checkpoints while retaining the configured timezone only for legacy checkpoint migration and compatibility state.
* Updated severity lookup to use the SOAR `/rest/container_options` endpoint, which only requires container view permissions available to the automation role by default.
