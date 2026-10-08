# ponytail: in-memory job registry capped by count; persist jobs to disk if they must survive restarts.
MAX_FINISHED_JOBS = 50


def prune_finished_jobs(jobs: dict, is_finished, *linked: dict) -> None:
    """Drops the oldest finished jobs (dicts keep insertion order) beyond MAX_FINISHED_JOBS,
    plus their entries in linked dicts. Running jobs are never touched."""
    finished = [key for key, job in jobs.items() if is_finished(job)]
    for key in finished[:max(0, len(finished) - MAX_FINISHED_JOBS)]:
        jobs.pop(key, None)
        for d in linked:
            d.pop(key, None)
