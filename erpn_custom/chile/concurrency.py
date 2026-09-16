from erpn_custom.chile.schedule import parse_datetime

STALE_JOB_STATUSES = frozenset({"finished", "failed", "stopped", "canceled"})
ACTIVE_JOB_STATUSES = frozenset({"queued", "started", "deferred", "scheduled"})
MISSING_JOB_GRACE_SECONDS = 120


def is_stale_run(status, started_at, creation, now, ttl_seconds, job_status=None):
    if status not in ("Queued", "Running"):
        return False
    try:
        ttl = max(int(ttl_seconds), 1)
    except (TypeError, ValueError):
        ttl = 1800
    current = parse_datetime(now) or now
    if job_status in STALE_JOB_STATUSES:
        return True
    ref = started_at if (status == "Running" and started_at) else creation
    ref_dt = parse_datetime(ref)
    if ref_dt is None:
        return job_status not in ACTIVE_JOB_STATUSES
    age = (current - ref_dt).total_seconds()
    if age >= ttl:
        return True
    if job_status in ACTIVE_JOB_STATUSES:
        return False
    return age >= min(MISSING_JOB_GRACE_SECONDS, ttl)
