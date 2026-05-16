# SQL optimisation tips and tricks

A slow query is rarely slow because SQL is slow. It is slow because the database engine made a decision — about which index to use, which join algorithm to pick, in what order to combine tables — and that decision turned out badly for your data. Once you understand how the engine *thinks*, optimisation stops being a bag of folklore tricks and starts being something closer to a conversation: you make a change, you ask the planner what it now intends to do, you check whether it lined up with reality, and you iterate.

This lesson is a practical tour of that conversation. We will walk through how a query is actually executed, how to read what the planner tells you, what makes an index useful (or useless), the common ways people accidentally defeat indexes, and the structural patterns — pagination, batching, caching — that matter once your queries themselves are reasonable.

The examples lean on PostgreSQL and SQL Server syntax, but the underlying mechanics — B-tree indexes, cost-based optimisers, cardinality estimates, hash and merge joins — are essentially universal across the mainstream relational engines.

## How the database actually runs your query

When you send `SELECT ...` to the database, it goes through four phases before any rows come back. Parsing turns the text into a syntax tree. Binding resolves table and column names against the catalog. Then the **query optimiser** rewrites the tree into a *plan*: a concrete sequence of physical operations, like "scan this table, then probe this index, then hash-join the results, then sort." Finally the execution engine runs that plan.

The optimiser is the interesting bit. It does not know your data; it guesses, using **statistics** collected from your tables — histograms of value distributions, counts of distinct values, average row sizes. From those, it estimates how many rows each step will produce (its *cardinality*), assigns a *cost* to every candidate plan based on disk and CPU constants, and picks the cheapest. The whole edifice rests on the cardinality estimates being roughly right. When they are wildly wrong, the optimiser picks a plan that looked cheap on paper and is catastrophic in practice.

The most important consequence of this for you, the query author, is that **the optimiser cannot read your mind, only your statistics**. If a column's statistics say "this filter returns 5% of the table" and reality is 90%, the engine will happily nested-loop through what it thought was a small set, and you will wait.

## Reading a query plan

Every mainstream database has a way to ask "what would you do with this query?". In PostgreSQL it is `EXPLAIN`. In SQL Server it is `SET SHOWPLAN_ALL ON` or the GUI's "Display Estimated Execution Plan". In MySQL it is `EXPLAIN`. In Oracle it is `EXPLAIN PLAN FOR`. They all show the same kind of thing: a tree of operations the engine intends to perform.

Here is a typical PostgreSQL plan:

```text
EXPLAIN SELECT * FROM orders WHERE customer_id = 42;

 Bitmap Heap Scan on orders  (cost=4.36..39.38 rows=10 width=244)
   Recheck Cond: (customer_id = 42)
   ->  Bitmap Index Scan on orders_customer_id_idx  (cost=0.00..4.36 rows=10 width=0)
         Index Cond: (customer_id = 42)
```

Read it inside-out, like a function call stack. The leaves at the bottom are the data sources; the parent nodes combine, filter, or transform their children. Here the engine plans to use the index to find row pointers (the inner `Bitmap Index Scan`) and then fetch those rows from the table itself (the outer `Bitmap Heap Scan`).

The numbers next to each node are the planner's guesses. `cost=4.36..39.38` is a pair: the *startup cost* (work done before the first row comes out) and the *total cost* (work done to produce every row), in arbitrary internal units. `rows=10` is the estimated row count. `width=244` is the estimated average row size in bytes.

`EXPLAIN ANALYZE` (or `EXPLAIN (ANALYZE, BUFFERS)` for cache statistics) actually runs the query and adds *measured* values alongside the estimates:

```text
 Bitmap Heap Scan on orders  (cost=4.36..39.38 rows=10 width=244)
                             (actual time=0.041..0.084 rows=12 loops=1)
```

You compare the two. If the planner expected 10 rows and got 12, all is well. If it expected 10 and got 10 million, you have a cardinality problem — and almost any plan built on top of that estimate will be wrong.

A handful of node types you will see constantly:

- **Seq Scan / Table Scan.** Read every row in the table. Fine for small tables or queries that legitimately want most rows; an alarm bell for big tables with selective filters.
- **Index Scan.** Walk the index in order to find row pointers, then fetch each row from the heap. Cheap when few rows match, expensive when many do (random heap I/O).
- **Index Only Scan.** Read the answer straight out of the index without touching the table. The fastest read pattern. Requires that every column the query needs is in the index.
- **Bitmap Index Scan + Bitmap Heap Scan.** A compromise between the two — collect all matching row pointers from the index, sort them, then read the heap in physical order. Good for medium-sized result sets.
- **Nested Loop join.** For each row on the outer side, look up matching rows on the inner side. Excellent when the outer side is tiny; terrible when it is large.
- **Hash Join.** Build a hash table from one side, probe it with the other. Good for medium-to-large joins with equality conditions.
- **Merge Join.** Walk two pre-sorted inputs in lock-step. Excellent when both sides happen to be sorted already.

Whenever a query is slower than you expect, your first instinct should be to look at the plan, find where the estimated and actual row counts diverge most, and investigate that node.

## Index design and selectivity

An index is a sorted, on-disk structure (almost always a B-tree) that lets the engine find rows matching a value or range without scanning the whole table. The key property of a *useful* index is **selectivity** — how thoroughly it narrows the set of candidate rows. An index on `country` in a global users table where 60% of users are from one country has terrible selectivity for that country; an index on `email` (effectively unique) is maximally selective.

A useful rule of thumb: if a query needs more than about 5–10% of a table's rows, the engine will (correctly) prefer a sequential scan over an index scan, because random I/O for many rows is more expensive than streaming the whole table.

### Composite indexes and the leftmost prefix rule

An index on multiple columns — sometimes called a composite or compound index — is sorted lexicographically: first by the leftmost column, then by the next, and so on. This has an important consequence called the **leftmost prefix rule**: an index on `(a, b, c)` can be used efficiently for queries filtering on `a`, on `a` and `b`, or on `a`, `b`, and `c`, but **not** for a query filtering only on `b` or `c`.

Concretely:

```sql
CREATE INDEX idx_orders_customer_status_date
  ON orders (customer_id, status, created_at);

-- Uses the index efficiently:
SELECT * FROM orders WHERE customer_id = 42;
SELECT * FROM orders WHERE customer_id = 42 AND status = 'shipped';
SELECT * FROM orders WHERE customer_id = 42 AND status = 'shipped'
  AND created_at > '2026-01-01';

-- Does NOT use the index efficiently:
SELECT * FROM orders WHERE status = 'shipped';
SELECT * FROM orders WHERE created_at > '2026-01-01';
```

Two design heuristics follow from this. First, **put equality predicates before range predicates**. An index on `(customer_id, created_at)` works beautifully for `customer_id = 42 AND created_at > x`, because the B-tree can dive straight to the matching `customer_id` and then scan a contiguous slice of dates. An index on `(created_at, customer_id)` for the same query has to walk every row in the date range and check the customer separately.

Second, **put more selective columns earlier**, all else being equal. The leading column does the bulk of the row narrowing; less selective columns later sharpen what is already a small set.

### Covering indexes and `INCLUDE`

A *covering* index is one that contains every column a particular query needs to return, so the engine can answer the whole query from the index without ever touching the heap. That triggers the magical `Index Only Scan` plan and tends to be many times faster than the equivalent index-plus-heap-fetch.

PostgreSQL 11+, SQL Server, and others support an `INCLUDE` clause for exactly this case:

```sql
CREATE INDEX idx_orders_customer_covering
  ON orders (customer_id)
  INCLUDE (status, total_cents, created_at);
```

The leading `customer_id` is the *key* — what the index is sorted by and what the engine can search on. The `INCLUDE`d columns are stored only in the leaf nodes; they are payload, not sort keys, so they cannot be used to filter or order, but they let `SELECT status, total_cents, created_at FROM orders WHERE customer_id = ?` be answered without a heap fetch.

Use `INCLUDE` for the columns you only need to *return*, not to *search on*. It keeps the upper levels of the B-tree slim.

### The cost of indexes

Indexes are not free. Every index slows down `INSERT`, `UPDATE` (when an indexed column changes), and `DELETE`, because the index has to be kept in sync. Indexes also consume storage and memory. A table with twelve indexes will write twelve times as much index data per insert as a table with one. The right number of indexes is "the smallest number that makes the workload's reads acceptable", not "one per query".

For very large bulk loads, it is often faster to drop indexes, load the data, and rebuild the indexes at the end than to maintain them incrementally during the load.

## Anti-patterns that defeat indexes

Many of the most common SQL performance problems come from writing queries in ways that prevent the engine from using indexes that *exist*.

### `SELECT *`

Selecting every column has two costs. It returns more data over the wire than you need, which is the small one. The bigger one is that it makes index-only scans impossible: the engine cannot return columns the index does not have, so it has to fall back to a heap fetch even if the filter is fully covered by the index. Always list the columns you actually need.

### Functions on indexed columns

Wrapping an indexed column in a function disables the index, because the index is sorted by the column's *raw* value, not by the function's output. This is the single most common reason a "correct-looking" query refuses to use an obviously suitable index.

```sql
-- Bad: index on created_at is unusable
SELECT * FROM orders WHERE DATE(created_at) = '2026-05-16';

-- Good: range condition that the index can satisfy
SELECT * FROM orders
WHERE created_at >= '2026-05-16'
  AND created_at <  '2026-05-17';
```

Similarly, `WHERE LOWER(email) = 'a@b.com'` cannot use a plain index on `email`. You either store the value already lowercased, use a case-insensitive collation, or create a **functional index** (`CREATE INDEX ... ON users (LOWER(email))`) so the index stores the function's output.

### Implicit type conversions

If you compare a column of one type against a value of another, the engine has to convert one side. Crucially, when it converts the *column* side — which it often does, since the value side is a constant the planner does not control — it has applied a function to the column, and the index becomes unusable. The plan silently degrades to a full scan, and cardinality estimates can go wildly wrong because the histogram is on the original type.

```sql
-- 'phone' is VARCHAR. The constant is an integer. SQL Server
-- converts every row's phone to integer before comparing.
SELECT * FROM users WHERE phone = 5551234567;

-- The fix: match the column's type
SELECT * FROM users WHERE phone = '5551234567';
```

Real-world reports of one-hour queries dropping to seconds after fixing a single implicit conversion are not exaggerated. SQL Server 2022 even added a dedicated `query_antipattern` extended event partly because this problem is so widespread.

### Leading wildcards

`WHERE name LIKE '%smith'` cannot use a regular index, because the engine has no idea where in the B-tree to start. `WHERE name LIKE 'smith%'` can. If you genuinely need infix or suffix search, you want a different data structure: a trigram index (`pg_trgm` in PostgreSQL), a reversed-string column, or a real full-text search engine.

### `OR` across unrelated columns

`WHERE a = ? OR b = ?` typically cannot use an index on `a` *and* an index on `b` at the same time efficiently; the engine often gives up and table-scans. Rewriting as `UNION` (or `UNION ALL` if duplicates are impossible) lets each branch use its own index:

```sql
SELECT * FROM users WHERE email = ?
UNION
SELECT * FROM users WHERE phone = ?;
```

Bitmap scans help here on PostgreSQL — it can combine two index scans into a single bitmap — but the `UNION` form is more reliable across engines.

### `NOT IN` with a nullable subquery

If the subquery returns even a single `NULL`, `NOT IN` becomes equivalent to "not in a set containing NULL", which SQL evaluates as unknown and returns *no rows at all*. Beyond the correctness footgun, `NOT IN` also tends to optimise worse than `NOT EXISTS`. Prefer `NOT EXISTS` (or `LEFT JOIN ... WHERE x IS NULL`) for "rows on the left with no match on the right".

## Rewriting subqueries and joins

Most modern optimisers can rewrite a subquery into a join when it is equivalent — PostgreSQL, SQL Server, and recent MySQL all do this for many cases — but not always, especially when the subquery is correlated or contains aggregates. Knowing how to rewrite manually is still useful, both as a fallback and as a way of clarifying what you actually mean.

### `IN` versus `EXISTS`

`SELECT ... WHERE x IN (SELECT y FROM ...)` and `SELECT ... WHERE EXISTS (SELECT 1 FROM ... WHERE y = x)` are usually logically equivalent for non-null `y`. The difference is intent: `EXISTS` is a **semi-join** — "do any matching rows exist?" — and the engine can stop searching for the inner table as soon as it finds one match. For large inner tables, that early termination is a significant win, and most engines will produce a Semi Join plan node for `EXISTS` automatically.

For small inner sets that are essentially constant, `IN (a, b, c, ...)` is fine and the optimiser will turn it into a hash or a sorted list.

### Correlated subqueries

A *correlated* subquery references a column from the outer query, so it logically runs once per outer row:

```sql
SELECT c.id,
       (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.id) AS order_count
FROM customers c;
```

A good optimiser will often rewrite this to a single join with `GROUP BY`. A less good one will execute the subquery `N` times. You can rewrite manually:

```sql
SELECT c.id, COALESCE(o.order_count, 0) AS order_count
FROM customers c
LEFT JOIN (
  SELECT customer_id, COUNT(*) AS order_count
  FROM orders
  GROUP BY customer_id
) o ON o.customer_id = c.id;
```

The manual rewrite makes the join algorithm choice explicit and tends to perform predictably regardless of optimiser version.

### Join order and the optimiser

You generally do *not* need to write joins in a particular order — the optimiser will reorder them based on costs. The exception is when statistics are bad and the optimiser keeps choosing wrong; then you either fix the statistics, add appropriate indexes, or use optimiser hints as a last resort. Hints are a smell: they are pinning the plan against future data changes, and if your data shifts the hint can become the new performance problem.

## Statistics, cardinality, and keeping the planner honest

We said earlier that the optimiser's cost-based plans rely on cardinality estimates, and cardinality estimates come from statistics. The corollary is that **stale statistics are a common cause of bad plans** — not because the SQL is wrong, but because the optimiser is reasoning about a version of the table that no longer exists.

Most databases auto-update statistics, but the triggers are heuristic and can lag behind real workload. PostgreSQL runs `ANALYZE` as part of `VACUUM` (and `autovacuum`); SQL Server has `AUTO_UPDATE_STATISTICS`; MySQL samples on the fly. After a bulk load, a schema change, or a sudden shift in data distribution, it is often worth running statistics manually:

```sql
-- PostgreSQL
ANALYZE orders;

-- SQL Server
UPDATE STATISTICS orders;
```

The other big source of estimate error is **column correlation**. The optimiser usually assumes columns are statistically independent — that the selectivity of `country = 'GB' AND city = 'London'` is the product of the two individual selectivities. Reality is wildly different (almost everyone with `city = 'London'` also has `country = 'GB'`). Some databases support multi-column statistics (PostgreSQL's `CREATE STATISTICS`, SQL Server's filtered statistics) to teach the planner about correlations explicitly.

When you read `EXPLAIN ANALYZE` and see a node whose estimated rows are off by more than ~10x from actual rows, that is your first thing to investigate. The fix is sometimes "run `ANALYZE`", sometimes "add multi-column stats", sometimes "rewrite the query to avoid the correlated predicate altogether".

## Pagination: keyset beats offset

The most common pagination pattern in beginner SQL is `LIMIT N OFFSET M`:

```sql
SELECT * FROM articles ORDER BY published_at DESC LIMIT 20 OFFSET 10000;
```

This looks innocent and is fine for the first few pages. The problem is that to skip `OFFSET` rows, the database has to *produce* those rows first — sort them, walk them, and then throw them away. Performance degrades linearly with depth, and by page 500 of a large table you can be reading hundreds of thousands of rows to return twenty. Benchmarks routinely show **10x to 100x speedups** when switching to keyset pagination on large tables.

**Keyset** (or "seek", or "cursor") pagination remembers where you left off and asks the database for "the next N rows after this key":

```sql
SELECT * FROM articles
WHERE (published_at, id) < (?, ?)   -- the last row from the previous page
ORDER BY published_at DESC, id DESC
LIMIT 20;
```

If `(published_at, id)` is indexed (the `id` tiebreak is essential — `published_at` alone is not necessarily unique), this is an index seek followed by a 20-row scan. It is O(1) in page depth instead of O(N). The trade-offs are that you cannot jump to "page 837" directly, only "next" and "previous"; and you have to remember and pass back the last key. For UIs that are infinite-scroll, "load more", or API cursors, this is a clear win. For UIs with numbered page links, you may need offset, but you can usually cap the depth.

## Batching

Single-row `INSERT`, `UPDATE`, and `DELETE` statements have a fixed overhead per round trip — parsing, planning, network latency, transaction bookkeeping, index maintenance — that dominates when you are doing many of them. Sending 10,000 inserts as 10,000 separate statements can be more than 10x slower than sending them as a single multi-row insert.

Strategies, in roughly the order you should reach for them:

1. **Multi-row inserts.** `INSERT INTO t (a, b) VALUES (1, 2), (3, 4), (5, 6), ...`. Trivial change, large win.
2. **Batched transactions.** Wrap N inserts in a single transaction so the WAL / log flush happens once at commit, not once per row.
3. **Prepared statements.** Send the SQL once, then send N bindings. Saves repeated parsing and planning.
4. **Bulk-load utilities.** `COPY` in PostgreSQL, `BULK INSERT` in SQL Server, `LOAD DATA INFILE` in MySQL. Bypasses much of the per-row plumbing and is the right answer for very large loads.
5. **Drop and rebuild indexes around very large loads.** Maintaining ten indexes incrementally over a billion rows can be slower than dropping them, inserting, and rebuilding.

For reads, the corresponding anti-pattern is the **N+1 query problem**: fetching a list of N parent rows, then issuing one query per parent for the children. Replace it with a single join or a single `WHERE child.parent_id IN (...)` round trip.

## Caching

Once your queries are individually reasonable and your batching is sensible, the next lever is not running the query at all. Caching is generally cheaper than any query optimisation.

There are three layers worth distinguishing:

- **The buffer pool / page cache.** Built into the database. Frequently accessed pages live in RAM, and a query that hits the cache costs orders of magnitude less than one that does not. You influence this by sizing memory appropriately (`shared_buffers` in PostgreSQL, the buffer pool in SQL Server / MySQL), and by writing queries that touch small, hot working sets rather than scanning cold pages. `EXPLAIN (ANALYZE, BUFFERS)` in PostgreSQL shows cache hits versus disk reads.
- **The plan cache.** The database also caches *compiled plans*, keyed by query text or a parameter shape. Parameterised queries (using `?` or `$1`, not string concatenation) reuse plans across calls; string-concatenated queries are seen as unique every time and force a fresh compilation on each call.
- **Application-level cache.** For results that are read often, change rarely, and are tolerant of slight staleness — reference data, leaderboard snapshots, user profiles — a Redis or Memcached layer in front of the database is usually the best return on effort. The hard parts are not the cache; they are choosing a TTL or an invalidation strategy that matches your consistency needs.

A pragmatic order of operations: make the underlying query fast first, then cache, not the other way around. A cached slow query is a slow query waiting for the next cold start.

## A workable optimisation loop

Putting it all together, here is the loop that tends to work in practice when a query is slow:

1. **Measure.** Get actual numbers — execution time, rows returned, whether the query is CPU-bound, I/O-bound, or waiting on locks. Without a measurement, you are guessing.
2. **Get the plan.** Run `EXPLAIN ANALYZE` (or your engine's equivalent). Read it bottom-up.
3. **Look for the lie.** Find the node where estimated and actual row counts diverge most. That is where the planner's model and reality disagree, and it is almost always the root cause of the bad plan.
4. **Ask why.** Is a needed index missing? Is an existing index being defeated by a function, an implicit conversion, or a leading wildcard? Are statistics stale? Is a column correlation confusing the estimator?
5. **Change one thing.** Add the index, fix the predicate, run `ANALYZE`. One change at a time, so you know what helped.
6. **Re-plan and re-measure.** Confirm the plan changed in the way you expected, and that the wall-clock time matches.

Most of the dramatic wins — orders of magnitude, not percentages — come from this loop applied to the small number of queries that dominate your workload. Find the slow ones (the engine's slow-query log will tell you), fix them, and stop. The rest of the database can almost always be left alone.

## Further reading

- [PostgreSQL: Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html) — the canonical reference for reading plans.
- [Use The Index, Luke](https://use-the-index-luke.com/) — Markus Winand's free book on practical indexing, covering composite indexes, covering indexes, and the leftmost prefix rule across all major engines.
- [Microsoft Learn: Cardinality Estimation](https://learn.microsoft.com/en-us/sql/relational-databases/performance/cardinality-estimation-sql-server) — how SQL Server's estimator builds its row guesses.
- [Keyset pagination explained](https://use-the-index-luke.com/no-offset) — the case against `OFFSET` and the seek-method alternative.
