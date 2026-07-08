# Safe Migration Notes

## Education Length Increase

Migration:

- `apps/employees/migrations/0004_employee_add_location_employee_location_and_more.py`

Change:

- `Employee.education` was increased from `CharField(max_length=255)` to
  `CharField(max_length=2500)`.

Safety notes:

- This is a widening schema change.
- Existing rows remain valid.
- No data backfill is required.
- API validation is covered for 2500 and 2501 character values.

Rollback limitation:

- Rolling this migration back narrows `education` to 255 characters.
- Rollback can fail or truncate externally if any row contains more than 255
  characters.
- Before rollback, inspect and shorten long values explicitly:

```sql
SELECT id, employee_uuid, length(education)
FROM employees_employee
WHERE length(education) > 255;
```

## City Fallback Fields

Migration:

- `apps/employees/migrations/0004_employee_add_location_employee_location_and_more.py`
- `apps/employees/migrations/0005_backfill_employee_location_fields.py`
- `apps/employees/migrations/0006_employee_location_fields_not_null.py`

Change:

- Added HR source fields:
  - `add_location`
  - `location_city`
  - `location`

The legacy `city` field remains in place. Public API responses continue using
the `city` key, but the value is resolved by this fallback order:

1. `add_location`
2. `location_city`
3. `location`
4. `city`

`PATCH /api/profile/me/` still updates the legacy/manual `city` field. If HR
source location fields are populated, they continue to take precedence in API
responses until a later HR sync changes or clears them.

Safety notes:

- New fields are added nullable first, without a one-shot `DEFAULT '' NOT NULL`
  column add. This schema migration is non-atomic so each quick DDL step can
  commit independently.
- A temporary database default of `''` is set after the nullable add so old app
  code cannot insert new `NULL` values during rollout. The final migration drops
  that default after enforcing `NOT NULL`.
- Existing rows are backfilled to empty strings in small batches in a non-atomic
  data migration.
- The final `NOT NULL` rollout happens only after the backfill. PostgreSQL
  check/validate steps prepare the constraint before `ALTER COLUMN SET NOT NULL`.
- No semantic data transform is required; the backfill only normalizes newly
  added `NULL` values to empty strings.
- No new indexes or unique constraints are added for these fields.
- HR sync can populate the new source fields as payload support becomes
  available.
- Before applying this migration to a very large production table, inspect lock
  behavior in a staging database and run the batch backfill during a low-write
  window.

Rollback limitation:

- Reversing `0006` relaxes the `NOT NULL` constraint.
- Reversing `0005` is intentionally a no-op; it cannot know which empty strings
  were original values and which were backfilled.
- Reversing `0004` drops `add_location`, `location_city`, and `location`.
- Any HR source location values stored only in those fields will be lost.
- If rollback is required, export or copy the preferred fallback value into
  `city` first.

## Org Directory Index

Migration:

- `apps/employees/migrations/0003_employee_employee_active_name_idx.py`

Change:

- Added `employee_active_name_idx` on
  `(is_active, last_name, first_name)` for the active org directory list.

Safety notes:

- The index is created with PostgreSQL `CREATE INDEX CONCURRENTLY`.
- The migration is non-atomic because PostgreSQL does not allow concurrent index
  creation inside a transaction.

Rollback limitation:

- Reversing the migration removes the index concurrently.
- Query plans for `GET /api/org/employees/` should be checked before removing
  it on a large table.

## Employee UUID Rollout

`employee_uuid` already exists as a non-null unique field in the initial
project migration, so this milestone does not add another staged rollout.

For a production table that did not already have UUIDs, use a staged rollout:

1. Add nullable `employee_uuid`.
2. Backfill in batches with a management command or data migration that does
   not lock the table for a long period.
3. Add a unique index/constraint after the backfill.
4. Make the field non-null after every row has a value.

Rollback limitation:

- After external API clients depend on UUIDs, removing the field is an API
  compatibility break, not only a database rollback.
