# Pending fixes

## Lower-priority polling hardening

- Make a `MAX_PAGES` truncation an explicit partial-result/failure condition rather
  than returning a partial list as though it were complete.
