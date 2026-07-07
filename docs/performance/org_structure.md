# Org Structure Performance Notes

## Query Patterns

The org endpoints are optimized for the current directory use cases:

- `GET /api/org/departments/`: paginated flat department list with direct active employee counts.
- `GET /api/org/structure/`: full department tree with direct active employee counts, without embedding employees.
- `GET /api/org/employees/`: paginated active employee directory with direct department filter and name/email/login search.

`/api/org/employees/` uses `select_related()` for `department`, `manager`,
`manager.department`, `hrbp`, and `hrbp.department` to avoid N+1 queries when
serializing nested manager and HRBP references.

## Indexes

Existing indexes used by these endpoints:

- `employees(last_name, first_name)`: stable name ordering.
- `employees(department, is_active)`: direct department filter.
- unique indexes on `employees.email`, `employees.login`, and `org_department.code`.
- `org_department(parent, name)`: nested department traversal.

Added for the org employee directory:

- `employee_active_name_idx` on `employees(is_active, last_name, first_name)`.

This index matches the default active employee list ordered by name. Substring
search currently uses `icontains`; PostgreSQL may not use btree indexes for
`%term%` searches. Add `pg_trgm` only after measuring slow search on real data.

## Regression Targets

The test suite contains query-count regression checks for the key API paths:

- `/api/org/employees/`: 3 queries for an authenticated paginated list response:
  viewer employee lookup, pagination count, and page query with joined relations.
- `/api/org/structure/`: 1 query for the department tree and employee counts.

## Local Measurement

Create performance data:

```bash
uv run --env-file .env --no-sync python manage.py seed_org_data --employees 10000
```

Measure query plans in PostgreSQL after seeding:

```sql
EXPLAIN ANALYZE
SELECT id, employee_uuid, email, login, first_name, last_name, department_id
FROM employees_employee
WHERE is_active = true
ORDER BY last_name, first_name, employee_uuid
LIMIT 20;

EXPLAIN ANALYZE
SELECT id, employee_uuid, email, login, first_name, last_name, department_id
FROM employees_employee
WHERE is_active = true
  AND department_id = 1
ORDER BY last_name, first_name, employee_uuid
LIMIT 20;
```

Record before/after numbers in this file when changing query shape or indexes.
