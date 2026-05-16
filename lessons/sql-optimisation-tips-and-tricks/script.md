Welcome. This lesson is about making slow SQL queries fast.

Here is the mental model to start with. A slow query is rarely slow because SQL itself is slow. It is slow because the database engine made a decision, about which index to use, which join algorithm to pick, what order to combine tables in, and that decision turned out badly for your data. Once you understand how the engine thinks, optimisation stops being a bag of folklore tricks. It starts being something closer to a conversation. You make a change. You ask the planner what it now intends to do. You check whether that lined up with reality. Then you iterate.

The examples lean on PostgreSQL and SQL Server, but the underlying mechanics are essentially universal across the mainstream relational engines. B-tree indexes, cost-based optimisers, cardinality estimates, hash joins, merge joins, they all behave in broadly the same way.

So let us start with how a query is actually run.

When you send a SELECT to the database, it goes through four phases before any rows come back. Parsing turns the text into a syntax tree. Binding resolves the table and column names against the catalog. Then the query optimiser rewrites that tree into a plan, a concrete sequence of physical operations. Something like, scan this table, probe this index, hash-join the results, then sort. Finally, the execution engine actually runs that plan.

The optimiser is the interesting bit. It does not know your data. It guesses, using statistics the database has collected from your tables. Histograms of value distributions, counts of distinct values, average row sizes. From those, it estimates how many rows each step will produce. That estimate is called the cardinality. It then assigns a cost to every candidate plan based on disk and CPU constants, and it picks the cheapest. The whole thing rests on the cardinality estimates being roughly right. When they are wildly wrong, the optimiser picks a plan that looked cheap on paper and is catastrophic in practice.

The takeaway is this. The optimiser cannot read your mind, only your statistics. If a column's statistics say a filter returns five percent of the table, and reality is ninety percent, the engine will happily nested-loop through what it thought was a small set, and you will wait.

Now, how do you see what the engine is planning to do? Every mainstream database has a way to ask that question. In PostgreSQL it is EXPLAIN. In SQL Server you turn on showplan or use the graphical estimated execution plan. In MySQL it is EXPLAIN. In Oracle it is EXPLAIN PLAN FOR. They all show the same kind of thing, a tree of operations the engine intends to perform.

You read a plan inside-out, like a function call stack. The leaves at the bottom are the data sources. The parent nodes combine, filter, or transform their children. So a simple lookup might show a bitmap index scan at the inner level, finding row pointers, wrapped by a bitmap heap scan at the outer level, fetching the actual rows from the table.

Next to each node you will see the planner's guesses. A startup cost, which is work done before the first row comes out. A total cost, which is work done to produce every row. These are in arbitrary internal units, not seconds. An estimated row count. And an average row width in bytes. Cost is what the optimiser uses to compare candidate plans.

If you add ANALYZE to EXPLAIN, the database actually runs the query and prints the measured numbers alongside the estimates. This is the single most important diagnostic in SQL optimisation. You compare estimate and reality. If the planner expected ten rows and got twelve, all is well. If it expected ten and got ten million, you have a cardinality problem, and almost any plan built on top of that estimate will be wrong.

A few node types come up constantly. A sequential scan, or table scan, reads every row in the table. Fine for small tables or queries that legitimately want most of the rows. An alarm bell for big tables with selective filters. An index scan walks the index in order to find row pointers, then fetches each row from the heap. It is cheap when few rows match and expensive when many do, because random heap I/O adds up. An index only scan reads the answer straight out of the index without touching the table at all. It is the fastest read pattern, and it only happens when every column the query needs is in the index. A bitmap index scan followed by a bitmap heap scan is a compromise. It collects matching row pointers, sorts them, then reads the heap in physical order. That is good for medium-sized result sets.

For joins, you will see three main shapes. A nested loop, for each row on the outer side, looks up matches on the inner side. Excellent when the outer side is tiny. Terrible when it is large. A hash join builds a hash table from one side, then probes it with the other. Good for medium and large joins with equality conditions. A merge join walks two pre-sorted inputs in lock-step. Excellent when both sides happen to be sorted already.

So, quick recap. When a query is slower than you expect, look at the plan, find where estimated and actual rows diverge most, and investigate that node.

Now let us talk about indexes, because most query optimisation in practice is index design.

An index is a sorted, on-disk structure, almost always a B-tree, that lets the engine find rows matching a value or a range without scanning the whole table. The key property of a useful index is selectivity, which is how thoroughly it narrows the set of candidate rows. An index on country, in a global users table where sixty percent of users are from one country, has terrible selectivity for that country. An index on email, effectively unique, is maximally selective.

A useful rule of thumb. If a query needs more than about five to ten percent of a table's rows, the engine will correctly prefer a sequential scan over an index scan, because random I/O for many rows is more expensive than streaming the whole table.

Composite indexes deserve their own segment. A composite index, sometimes called a compound index, is sorted lexicographically. First by the leftmost column, then by the next, and so on. This has an important consequence called the leftmost prefix rule. An index on columns A, B, C, in that order, can be used efficiently for queries filtering on A, on A and B, or on all three. But it cannot be used efficiently for a query filtering only on B, or only on C. Without a value for A, there is no useful starting point in the B-tree.

Two design heuristics fall out of this. First, put equality predicates before range predicates. An index on customer_id then created_at works beautifully for a query like, customer_id equals forty-two and created_at greater than some date. The B-tree dives straight to the matching customer and scans a contiguous slice of dates. The reverse order, created_at then customer_id, performs much worse for the same query, because the engine has to walk every row in the date range and check the customer separately. Second, put more selective columns earlier, all else being equal. The leading column does the bulk of the row narrowing.

Next, covering indexes. A covering index is one that contains every column a particular query needs to return. The engine can then answer the whole query out of the index, without touching the heap. That triggers an index only scan, which tends to be many times faster than the equivalent index plus heap fetch. PostgreSQL 11 and later, SQL Server, and others support an INCLUDE clause for exactly this case. You list your sort key columns normally, and then list payload columns inside INCLUDE. The included columns live in the leaf nodes of the index but are not part of the sort key. They cannot be used to filter or order, but they let the engine return them without going back to the table. Use INCLUDE for columns you only need to return, not to search on. It keeps the upper levels of the B-tree slim.

Indexes are not free. Every index slows down INSERT, UPDATE on indexed columns, and DELETE, because the index has to be kept in sync. Indexes also consume storage and memory. A table with twelve indexes writes twelve times as much index data per insert as a table with one. The right number of indexes is the smallest number that makes your read workload acceptable, not one per query. And for very large bulk loads, it is often faster to drop indexes, load the data, then rebuild them at the end, rather than maintaining them incrementally during the load.

Now let us turn to the anti-patterns. These are the common ways people accidentally write queries that prevent the engine from using the indexes that already exist.

The first is SELECT star. Selecting every column has two costs. The small cost is that you return more data over the wire than you need. The bigger cost is that it makes index only scans impossible. The engine cannot return columns the index does not have, so it falls back to a heap fetch even if the filter is fully covered by the index. Always list the columns you actually need.

The second is wrapping an indexed column in a function. The index is sorted by the column's raw value, not by the function's output, so applying a function disables the index. This is the single most common reason a correct-looking query refuses to use an obviously suitable index. For example, filtering by DATE of created_at equals a particular date cannot use an index on created_at, because the index is sorted by the full timestamp. The fix is to rewrite as a range, created_at greater than or equal to that date, and less than the next day. Similarly, filtering by LOWER of email equals some string cannot use a plain index on email. Your options are to store the value already lowercased, to use a case-insensitive collation, or to create a functional index on the lowercase form of the column, so that the index itself stores the function's output.

The third anti-pattern, and one of the most insidious, is implicit type conversion. If you compare a column of one type against a value of another, the engine has to convert one side. Crucially, when it converts the column side, which it often does because the constant is fixed and the column is not, it has effectively applied a function to the column, and the index becomes unusable. The plan silently degrades to a full scan, and cardinality estimates can go wildly wrong because the histogram is on the original type. A classic example is comparing a varchar phone number column against a numeric literal. The engine converts every row's phone to an integer before comparing. The fix is trivial, quote the literal so the types match. Real-world reports of one-hour queries dropping to seconds after fixing a single implicit conversion are not exaggerated. SQL Server 2022 even added a dedicated query antipattern extended event partly because this problem is so widespread.

The fourth is leading wildcards. A LIKE pattern that starts with a percent sign cannot use a regular index, because the engine has no idea where in the B-tree to start. A LIKE pattern that ends with a percent sign can. If you genuinely need infix or suffix search, you want a different data structure altogether, a trigram index in PostgreSQL, a reversed-string column, or a real full-text search engine.

The fifth is OR across unrelated columns. A WHERE clause like, A equals something OR B equals something, typically cannot use an index on A and an index on B at the same time efficiently. The engine often gives up and table-scans. Rewriting as a UNION of two single-condition queries lets each branch use its own index. PostgreSQL's bitmap scans help here, because the engine can combine two index scans into a single bitmap, but the UNION form is more reliable across engines.

The sixth is NOT IN with a nullable subquery. If the subquery returns even one NULL, NOT IN becomes equivalent to, not in a set containing NULL, which SQL evaluates as unknown, and the query returns no rows at all. Beyond the correctness footgun, NOT IN also tends to optimise worse than NOT EXISTS. Prefer NOT EXISTS, or a LEFT JOIN with a WHERE IS NULL filter, for rows on the left with no match on the right.

Now, rewriting subqueries and joins. Most modern optimisers can rewrite a subquery into a join when the two are equivalent. PostgreSQL, SQL Server, and recent MySQL all do this in many cases. But not always. Especially when the subquery is correlated or contains aggregates. Knowing how to rewrite manually is still useful, both as a fallback and as a way of clarifying what you actually mean.

The first useful pattern is IN versus EXISTS. A WHERE IN with a subquery and a WHERE EXISTS clause are usually logically equivalent for non-null values. The difference is intent. EXISTS expresses a semi-join, the question of whether any matching rows exist. The engine can stop searching the inner table as soon as it finds one match. For large inner tables, that early termination is a significant win, and most engines will produce a semi-join plan node for EXISTS automatically. For small inner sets that are essentially constant, IN with a literal list is fine. The optimiser will turn it into a hash or a sorted list.

The second is correlated subqueries. A correlated subquery references a column from the outer query, so logically it runs once per outer row. A good optimiser will often rewrite that to a single join with GROUP BY. A less good one will execute the subquery N times. You can rewrite manually by replacing the correlated subquery with a LEFT JOIN against a derived table that groups by the join key and computes the aggregate up front. The manual rewrite makes the join algorithm choice explicit and tends to perform predictably regardless of optimiser version.

On join order, you generally do not need to write joins in a particular sequence. The optimiser will reorder them based on costs. The exception is when statistics are bad and the optimiser keeps choosing wrong. Then you either fix the statistics, add appropriate indexes, or use optimiser hints as a last resort. Hints are a smell. They pin the plan against future data changes, and if your data shifts, the hint can become the new performance problem.

That brings us to statistics. The optimiser's cost-based plans rely on cardinality estimates, and cardinality estimates come from statistics. The corollary is that stale statistics are a common cause of bad plans. Not because the SQL is wrong, but because the optimiser is reasoning about a version of the table that no longer exists.

Most databases auto-update statistics, but the triggers are heuristic and can lag behind real workload. PostgreSQL runs ANALYZE as part of VACUUM and autovacuum. SQL Server has AUTO UPDATE STATISTICS. MySQL samples on the fly. After a bulk load, a schema change, or a sudden shift in data distribution, it is often worth running statistics manually. In PostgreSQL that is ANALYZE on the table. In SQL Server it is UPDATE STATISTICS.

The other big source of estimate error is column correlation. The optimiser usually assumes columns are statistically independent. So it computes the selectivity of, country equals GB and city equals London, as the product of the two individual selectivities. Reality is wildly different, because almost everyone with city equal to London also has country equal to GB. Some databases support multi-column statistics for exactly this case. PostgreSQL has CREATE STATISTICS. SQL Server has filtered statistics. These teach the planner about correlations explicitly.

When you read EXPLAIN ANALYZE and see a node whose estimated rows are off by more than about a factor of ten from actual rows, that is the first thing to investigate. The fix is sometimes to run ANALYZE, sometimes to add multi-column statistics, and sometimes to rewrite the query to avoid the correlated predicate altogether.

Now, pagination. Almost every web application gets this wrong at first. The most common pagination pattern in beginner SQL is LIMIT N OFFSET M, something like LIMIT twenty OFFSET ten thousand. This looks innocent and is fine for the first few pages. The problem is that to skip OFFSET rows, the database has to produce those rows first, sort them, walk them, then throw them away. Performance degrades linearly with depth. By page five hundred of a large table you can be reading hundreds of thousands of rows just to return twenty. Benchmarks routinely show ten-times to one-hundred-times speedups when switching to keyset pagination on large tables.

Keyset pagination, sometimes called seek pagination or cursor pagination, remembers where you left off and asks for the next N rows after a given key. So instead of OFFSET ten thousand, you say, where the published_at and id pair is less than the last row's published_at and id pair, ordered descending, LIMIT twenty. If that pair of columns is indexed, and the id tiebreak is essential because published_at alone is not necessarily unique, this becomes an index seek followed by a twenty-row scan. It is constant time in page depth instead of linear.

The trade-offs are real. You cannot jump directly to page eight hundred and thirty-seven, only next and previous. And you have to remember and pass back the last key. For infinite-scroll UIs, load-more buttons, or API cursors, this is a clear win. For UIs with numbered page links, you may still need offset, but you can usually cap the depth.

Next, batching. Single-row INSERT, UPDATE, and DELETE statements have a fixed overhead per round trip. Parsing, planning, network latency, transaction bookkeeping, index maintenance. That overhead dominates when you are doing many of them. Sending ten thousand inserts as ten thousand separate statements can be more than ten times slower than sending them as a single multi-row insert.

The strategies, in roughly the order you should reach for them, run like this. Multi-row inserts, a single INSERT statement with many VALUES tuples. Trivial change, large win. Batched transactions, wrapping N inserts in a single transaction so the write-ahead log flush happens once at commit, not once per row. Prepared statements, sending the SQL once, then sending N bindings, saving repeated parsing and planning. Bulk-load utilities, COPY in PostgreSQL, BULK INSERT in SQL Server, LOAD DATA INFILE in MySQL. These bypass much of the per-row plumbing and are the right answer for very large loads. And, for very large loads, dropping and rebuilding indexes around the load, because maintaining ten indexes incrementally over a billion rows can be slower than dropping them, inserting, and rebuilding.

For reads, the corresponding anti-pattern is the N plus one query problem. You fetch a list of N parent rows, then issue one query per parent for the children. Replace it with a single join, or a single WHERE child parent_id IN list round trip.

Now, caching. Once your queries are individually reasonable and your batching is sensible, the next lever is to not run the query at all. Caching is generally cheaper than any query optimisation.

There are three layers worth distinguishing.

The first is the buffer pool, or page cache. This is built into the database. Frequently accessed pages live in RAM, and a query that hits the cache costs orders of magnitude less than one that does not. You influence this by sizing memory appropriately, with settings like shared_buffers in PostgreSQL, or the buffer pool in SQL Server and MySQL. And by writing queries that touch small, hot working sets rather than scanning cold pages. The BUFFERS option to EXPLAIN ANALYZE in PostgreSQL shows you cache hits versus disk reads.

The second is the plan cache. The database also caches compiled plans, keyed by query text or a parameter shape. Parameterised queries, the kind that use placeholders like a question mark or a dollar-one, reuse plans across calls. String-concatenated queries are seen as unique every time and force a fresh compilation on each call.

The third is application-level caching. For results that are read often, change rarely, and tolerate slight staleness, things like reference data, leaderboard snapshots, user profiles, a Redis or Memcached layer in front of the database is usually the best return on effort. The hard parts are not the cache itself. They are choosing a time-to-live or an invalidation strategy that matches your consistency needs.

A pragmatic order of operations. Make the underlying query fast first, then cache, not the other way around. A cached slow query is a slow query waiting for the next cold start.

So here is the workable optimisation loop, all in one place.

Measure. Get actual numbers, execution time, rows returned, whether the query is CPU-bound, I/O-bound, or waiting on locks. Without a measurement, you are guessing.

Get the plan. Run EXPLAIN ANALYZE, or your engine's equivalent. Read it bottom-up.

Look for the lie. Find the node where estimated and actual row counts diverge most. That is where the planner's model and reality disagree, and it is almost always the root cause of the bad plan.

Ask why. Is a needed index missing? Is an existing index being defeated by a function, an implicit conversion, or a leading wildcard? Are statistics stale? Is a column correlation confusing the estimator?

Change one thing. Add the index, fix the predicate, run ANALYZE. One change at a time, so you know what helped.

Then re-plan and re-measure. Confirm the plan changed in the way you expected, and that the wall-clock time matches.

Most of the dramatic wins, orders of magnitude rather than percentages, come from this loop applied to the small number of queries that dominate your workload. The engine's slow-query log will tell you which ones. Fix those, then stop. The rest of the database can almost always be left alone.

To recap. Understand the planner. Read the plans it produces. Design indexes that match your real access patterns. Avoid the anti-patterns that defeat those indexes, things like functions on indexed columns, implicit type conversions, leading wildcards, OR across unrelated columns, NOT IN with nullable subqueries, and SELECT star. Keep your statistics fresh, and watch out for column correlation. Paginate by key rather than by offset for deep pages. Batch your writes, and avoid the N plus one pattern on reads. Cache once the queries are already fast.

Do that, and most queries will be fast. The ones that are not will tell you exactly why, if you ask them properly.
