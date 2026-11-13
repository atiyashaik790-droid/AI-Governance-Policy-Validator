# Temporary SQL firewall verification — PASS

8 November 2026,08:37:00–08:38:29UTC (14:07:00–14:08:29IST),89.113seconds total; within approved15minutes. Exact subscription, logical server and Azure-SQL-reported blocked client45.127.46.209 verified before adding only `gpv-operator-20261108-readonly` with identical start/end IP.

SELECT-only source verification passed on `sqldb-governance-validator-dev`: Alembic005, deployed005 schema/SSO contract; required columns, indexes, keys and history triggers; trusted/enabled foreign keys. Catalog inventory:18tables,45indexes,31constraints,8foreign keys,3triggers. Migration006/007 tables and008 execution immutability trigger absent, as expected before migration. No006–008 readiness or failure-cycle completion is inferred.

Contained application identity mapping, existing runtime role membership and51explicit runtime grant records match the last passed source baseline. Operator CONNECT/SELECT/VIEW DEFINITION/CONTROL were observed, not changed. Runtime permissions were inspected through catalog metadata; no impersonation or direct managed-identity authentication was performed. This is not hosted008 runtime acceptance.

The temporary firewall rule was removed immediately after verification. Fresh final inventory confirms its absence and exact preservation of every original rule. No production records, SQL permissions, migrations, application settings/code, temporary databases or providers were changed/called. No broad Azure-access rule was enabled. Original firewall state is restored, so later operator access from this IP again requires approved access. Existing application egress rules remain intact.

[Window evidence](evidence/firewall-verification-2026-11-08/result.json), [SELECT/catalog/grant results](evidence/firewall-verification-2026-11-08/sql-select-results.json), original/final firewall snapshots in the same directory.

Recovery proof, compatible-copy preservation/controlled migration failures and independent temporary-database expiry remain blocked. Production deployment remains NO-GO. No further action or approval is inferred. Stopped after approved verification.
