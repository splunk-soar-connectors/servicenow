# Pending fixes

## Remaining ServiceNow `on_poll` hardening

Confirm the timezone ServiceNow returns for `sys_updated_on`, then normalize every
checkpoint read, comparison, and write to one canonical representation, preferably
timezone-aware UTC / ISO 8601. Do not parse an API timestamp as UTC and then convert
it to the asset timezone unless the API contract guarantees that the original value
is UTC. An incorrect conversion can advance the checkpoint and skip records.

## Lower-priority polling hardening

- Make a `MAX_PAGES` truncation an explicit partial-result/failure condition rather
  than returning a partial list as though it were complete.
- When the first scheduled poll completes successfully with no records, capture the
  poll start time before querying ServiceNow and save it as the baseline checkpoint
  rather than leaving `last_time` empty and repeatedly falling back to first-run
  behavior. Use the same canonical UTC representation as normal checkpoints, and do
  not advance the checkpoint when the API request or poll fails.
