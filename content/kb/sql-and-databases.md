---
title: SQL queries, indexes and transactions
categories: [databases]
license: CC-BY-4.0
attribution: CareerPilot AI contributors
---
# Joins

An inner `JOIN` keeps only rows that match on both sides. A `LEFT JOIN` keeps every row of the left table
and fills the right side with NULLs when nothing matches: use it when "including those with none" appears
in the question (customers without orders, users without logins). A filter on the right table placed in
`WHERE` turns a left join back into an inner join; put it in the `ON` clause instead.

# Aggregation and NULLs

`COUNT(*)` counts rows, `COUNT(column)` counts non-NULL values. After a `LEFT JOIN`, a customer with no
orders still produces one row with NULLs, so `COUNT(*)` returns 1 and `COUNT(o.id)` returns 0. `SUM`,
`AVG`, `MIN` and `MAX` ignore NULLs too. `WHERE` filters rows before grouping, `HAVING` filters groups
after `GROUP BY`. Every selected column must be grouped or aggregated.

# Indexes

A B-tree index speeds up equality, range and `ORDER BY` on its leading columns: an index on
`(customer_id, created_at)` serves `WHERE customer_id = ?` and `WHERE customer_id = ? ORDER BY created_at`,
but not a filter on `created_at` alone. Indexes cost write time and disk, so add them for real queries and
check with `EXPLAIN ANALYZE` (look for sequential scans on large tables, and estimated versus actual rows).
A function on the column (`WHERE lower(email) = ?`) needs an expression index.

# Transactions and isolation

ACID: atomic, consistent, isolated, durable. Read committed (the PostgreSQL default) avoids dirty reads
but allows non-repeatable reads; repeatable read and serializable give stronger guarantees at the cost of
retries. For "read then update" logic, use `SELECT … FOR UPDATE` or a conditional `UPDATE … WHERE` to avoid
lost updates. Keep transactions short: long ones hold locks and block vacuum.

# Scaling a database

Start with indexes, query fixes and connection pooling (PgBouncer). Then read replicas for read-heavy
loads (accept replication lag), caching for hot keys, partitioning for very large tables, and sharding
only when one primary can no longer take the writes. Back up and test restores; define RPO and RTO.
