# DBRE Diagnostic Playbook v1
## Priority Order:
1. Check EXPLAIN ANALYZE for sequential scans → always add index if found
2. Check for N+1 patterns → rewrite as JOIN
3. Check join order → put smallest table first
4. Check for SELECT * → replace with specific columns
5. Check for functions on indexed columns → rewrite to use index
6. Verify correctness by comparing row count with original
