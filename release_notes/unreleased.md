**Unreleased**

* Preserves literal backslashes and Unicode text in ticket descriptions, work notes, and comments.
* Prevents future ServiceNow record timestamps from poisoning scheduled poll checkpoints.
* Handles non-object JSON error responses without crashing connector actions.
* Preserves RFC-valid tildes when extracting URL artifacts from polled tickets.
* Adds a 30-second timeout to upstream ServiceNow API, OAuth, and attachment requests.
