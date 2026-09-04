# Pending fixes

## ServiceNow `on_poll` checkpoint correctness

### 1. Use a composite checkpoint and deterministic ordering

The scheduled-poll cursor currently stores only `sys_updated_on` with second precision
and queries using `sys_updated_on >= last_time`. If more records share one timestamp
than the configured poll limit, the connector can repeatedly retrieve the first batch
and never reach the remaining records at that timestamp.

Store both of these values for the final successfully emitted record:

- `last_updated_on`
- `last_sys_id`

Order results deterministically by both fields:

```text
ORDERBYsys_updated_on^ORDERBYsys_id
```

On the next poll, query records after that composite cursor: records with a newer
`sys_updated_on`, plus records with the same timestamp and a greater `sys_id`.

### 2. Use one canonical checkpoint timezone

Confirm the timezone ServiceNow returns for `sys_updated_on`, then normalize every
checkpoint read, comparison, and write to one canonical representation, preferably
timezone-aware UTC / ISO 8601. Do not parse an API timestamp as UTC and then convert
it to the asset timezone unless the API contract guarantees that the original value
is UTC. An incorrect conversion can advance the checkpoint and skip records.

## Lower-priority polling hardening

- Make a `MAX_PAGES` truncation an explicit partial-result/failure condition rather
  than returning a partial list as though it were complete.
- When the first scheduled poll returns no records, save a baseline checkpoint rather
  than leaving `last_time` empty and repeatedly falling back to first-run behavior.
- Decide on an explicit operator-visible policy for records missing `sys_id`; they
  cannot be safely deduplicated and are currently skipped while the checkpoint can
  advance past them.
