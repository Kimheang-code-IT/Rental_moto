def test_create_scheduler_registers_deadline_and_outbox_jobs():
    from app.scheduler import create_scheduler

    scheduler = create_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "scan-deadline-alerts" in job_ids
    assert "dispatch-outbox" in job_ids
    assert "scan-overdue-rentals" in job_ids
    assert "precompute-dashboard" in job_ids
    assert "cleanup-expired-data" in job_ids
    assert "daily-telegram-summary" in job_ids


def test_scheduler_jobs_never_overlap_and_coalesce_missed_ticks():
    """max_instances=1 prevents duplicate/overlapping runs; coalesce collapses backlog."""
    from app.scheduler import create_scheduler

    scheduler = create_scheduler()
    # Defaults apply to every job; private attrs are stable for the pinned
    # APScheduler version and verify the actual configuration.
    assert scheduler._job_defaults["max_instances"] == 1
    assert scheduler._job_defaults["coalesce"] is True
