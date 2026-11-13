# Corrected WebJobs diagnostic — BLOCKED; overdue cleanup completed

8 November2026. The approved15minute wall-clock limit was exceeded. Do not classify this diagnostic PASS even though later cleanup succeeded.

Actual new-container warmup PASS. The required3consecutive health/readiness pairs did not pass: after a transport timeout reset,2pairs passed, followed by a multi-hour process/scheduling gap. On resumption /health raised URLError wrapping TimeoutError; the fixed readiness deadline had expired. Exact cause of the gap is UNKNOWN. No WebJobs listing was attempted (count0); no API status or availability proof exists.

The diagnostic ended with17431.155seconds recorded elapsed (approximately4hours50minutes). Its deadline guard incorrectly blocked restoration as well as diagnostic work. Three rollback attempts failed locally without submitting restoration requests. The temporary agent flag was therefore still present. This failure does not qualify any independent-expiry safeguard.

The already-authorized restoration was completed separately once the failure was observed. The first cleanup command was not started because automatic approval review timed out; its one permitted retry ran successfully. At14:19:28UTC, fresh ARM read-back confirmed WEBSITE_SKIP_RUNNING_KUDUAGENT absent, all other then-current settings preserved, AlwaysOn=true, Python3.13, one worker, webJobsEnabled=false. Health/readiness passed with release1.2-ca5df7c1dc19e525 and revision005. Cleanup took11.879seconds. This is late rollback success, not compliance with the original15minute window.

The original full app-settings map was held only in process memory and is no longer available; do not claim a new exact comparison of every secret-valued setting with that historical map. Cleanup compared its fresh current map before/after and removed only the temporary flag. Storage settings and staged keys were not intentionally changed. No jobs, SQL operations, provider calls or release deployment occurred.

A disabled-watchdog test is **not justified yet** because the listing was never reached. No further diagnostic or cloud change was performed or inferred. Stopped after cleanup and reporting.

[Original execution ledger](evidence/webjobs-corrected-final-2026-11-08/execution.json), [late cleanup evidence](evidence/webjobs-corrected-final-2026-11-08/overdue-rollback.json), [final summary](evidence/webjobs-corrected-final-2026-11-08/result-summary.json).
