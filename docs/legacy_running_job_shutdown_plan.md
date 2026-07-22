# Legacy Alignment Running Job Shutdown Plan

## Scope

This plan defines how operators should stop the isolated legacy runtime. It is
not an executable recovery tool and does not mutate existing jobs.

## Known Constraint

Legacy `alignment_run` jobs record `locked_by` and `locked_at`, but have no
heartbeat, stale reclaim, ownership fencing, or atomic run/job finalization.
An old `running` record cannot prove whether its former worker stopped before
or after side effects were written. Automatic replay can therefore duplicate
or overwrite legacy cards.

## Recommended Disposition

Use **bounded drain, then safe failure**:

1. disable new route admission after the observation and notice gates;
2. keep exactly one explicit `legacy-alignment` worker running;
3. allow queued and retrying work a bounded drain interval;
4. stop the worker process and prove the process is no longer active;
5. inspect each remaining `running` job with its `AlignmentRun`, events, and
   card side effects;
6. use a separately reviewed transactional operator action to mark an
   unrecoverable stale job and its linked run failed with a safe operational
   reason;
7. verify `queued = 0`, `running = 0`, and `retrying = 0` before shutdown is
   accepted.

Do not migrate an in-flight legacy job into Formal Workflow: the data model,
idempotency scope, item bootstrap, and provider identity are different. Do
not blindly requeue or directly call `run_background_job()` for an old
`running` record because ownership and side-effect completion are unknown.

## Per-State Action

| State | Recommended action | Reason |
|---|---|---|
| `queued` | drain through one dedicated legacy worker | execution has not started |
| `retrying` | drain only if attempt/error classification permits; otherwise safe failure | immediate retries have no backoff |
| recent `running` with verified live owner | wait through a bounded grace period | avoid concurrent disposition |
| stale `running` with confirmed dead owner | inspect writes, then safe failure through reviewed tooling | replay is not idempotent or fenced |
| `completed` | retain history | terminal data contract is separate |
| `failed` | retain; do not manually retry during shutdown | avoids reopening the queue |
| `canceled` | reconcile linked run and retain | generic cancel may leave the run active |

The future safe-failure action must update the Job and linked `AlignmentRun`
in one reviewed transaction, append a sanitized event, preserve historical
cards, reject active owners, support dry-run output, and be auditable. That
tool is outside Task 9C.5N.1.

## Shutdown Checklist

1. enumerate target databases and all worker processes;
2. name the drain owner and rollback owner;
3. capture sanitized counts and oldest ages;
4. disable HTTP route admission without enabling 410;
5. stop `standard` workers only if separately required; they cannot consume
   legacy jobs and need not stop for legacy shutdown;
6. drain with one `--mode legacy-alignment` process;
7. stop that process before stale-job disposition;
8. reconcile job/run mismatches;
9. hold zero active counts for the approved verification period;
10. retain the signed observation and shutdown report.

## Rollback

Rollback is permitted while the compatibility window remains open:

1. re-enable `LEGACY_ALIGNMENT_ROUTE_ADMISSION_ENABLED=true` if the approved
   trigger is met;
2. restart one explicit `legacy-alignment` worker only after confirming no
   prior legacy worker is active;
3. requeue only jobs independently proven not to have started side effects;
4. do not reverse a safe-failure disposition by blind replay;
5. record the trigger, owner, affected jobs, and restored request behavior;
6. restart the observation window after the rollback.

Formal workers remain available throughout because they no longer share
legacy queue ownership.

## Exit Boundary

This plan makes shutdown mechanically separable but does not prove external
consumer absence, environment-authoritative queue drain, or a rehearsed
safe-failure tool.

```text
LEGACY_RUNNING_JOB_RECOVERY_GAP
LEGACY_ALIGNMENT_410_NOT_AUTHORIZED
```
