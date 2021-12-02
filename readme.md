[comment]: # " File: readme.md"
[comment]: # "  Copyright (c) 2016-2021 Splunk Inc."
[comment]: # ""
[comment]: # "Licensed under the Apache License, Version 2.0 (the 'License');"
[comment]: # "you may not use this file except in compliance with the License."
[comment]: # "You may obtain a copy of the License at"
[comment]: # ""
[comment]: # "    http://www.apache.org/licenses/LICENSE-2.0"
[comment]: # ""
[comment]: # "Unless required by applicable law or agreed to in writing, software distributed under"
[comment]: # "the License is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,"
[comment]: # "either express or implied. See the License for the specific language governing permissions"
[comment]: # "and limitations under the License."
[comment]: # ""
**Notes**

-   **Asset Configuration Parameter**

      

    -   on_poll_table: Table to ingest issues from.
    -   on_poll_filter: Filter to use with On Poll separated by '^' (e.g. description=This is a
        test^assigned_to=test.name).
    -   first_run_container: Maximum containers to ingest for the first run of scheduled polling.
    -   max_container: Maximum containers to ingest for subsequent runs of scheduled polling.

      

-   **The functioning of On Poll**

      

    -   On Poll ingests the details of the tickets/records of a table provided by the user. An
        ingested container's name will be set to the 'short_description' of the ticket/record. If
        the ticket/record does not have any short_description then a default name will be given to
        the container.

          
          

    -   **Two ways of polling**

          

        -   Manual polling

              

            -   The application will fetch the number of tickets/records controlled by the
                container_count parameter set in the Poll Now window.
            -   Tickets/records can be restricted by providing a filter in the configuration
                parameter.

              

        -   Scheduled Polling

              

            -   The application will fetch the number of tickets/records, controlled by the
                'first_run_container' configuration parameter for the first run of Scheduled Polling
                and by the 'max_container' configuration parameter for the other runs of Scheduled
                Polling. Each poll will ingest tickets/records which have been created or updated
                since the previous run of Scheduled Polling.

      

-   **Specific functionality of ServiceNow On Poll**

      

    -   When the app is installed with Python version 2 and if the data is ingested using On Poll
        with query A and label B, it will list down the containers accordingly. If the ticket that
        is already ingested is updated, and then if the On Poll is executed again with the same
        label i.e. label B and with the same query A, it will add details of the updated ticket as
        an artifact in the already created container and update the container properties
        accordingly.
    -   When the app is installed with Python version 3 and if the data is ingested using On Poll
        with query A and label B, it will list down the containers accordingly. If the ticket that
        is already ingested is updated, and then if the On Poll is executed again with the same
        label i.e. label B and with the same query A, it will not update the container properties
        but will add the updated ticket as an artifact in the already created container.

  
