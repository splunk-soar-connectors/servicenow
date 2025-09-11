**Unreleased**

* Bug fix: Adding json.dumps to create_ticket and update_ticket to convert fields input to a json string before converting to a python dictionary that's passed to the ServiceNow API. This ensuures the behaviour of the fields input is the same as prior to version 2.6.5 of the app.