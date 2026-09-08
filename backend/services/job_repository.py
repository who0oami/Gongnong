import uuid
from schemas.job import Job, JobStatus

_jobs: dict[str, Job] = {}


def create_job(url: str) -> Job:
    job_id = str(uuid.uuid4())

    job = Job(
        job_id=job_id,
        status=JobStatus.QUEUED,
        url=url,
    )

    _jobs[job_id] = job

    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def update_job(job_id: str, **changes) -> Job | None:
    job = _jobs.get(job_id)

    if job is None:
        return None

    updated = job.model_copy(update=changes)
    _jobs[job_id] = updated

    return updated