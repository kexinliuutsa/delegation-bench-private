"""Versioned automatic QC for v1.3 post-proposal failures."""
import json
from pathlib import Path
class MissingRawProposalForFailedJob(RuntimeError):pass
def assert_failed_job_has_raw_proposal(job_or_trajectory_id,raw_log,proposal_received=True,status='POST_PROPOSAL_FAILURE'):
 if status=='PRE_PROPOSAL_FAILURE' or not proposal_received:return True
 path=Path(raw_log)
 if not path.exists() or not path.stat().st_size:raise MissingRawProposalForFailedJob('MISSING_RAW_PROPOSAL_FOR_FAILED_JOB')
 try:rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
 except Exception as exc:raise MissingRawProposalForFailedJob('MISSING_RAW_PROPOSAL_FOR_FAILED_JOB') from exc
 if not any((r.get('trajectory_id')==job_or_trajectory_id or r.get('pair_id')==job_or_trajectory_id) and r.get('raw_structured_proposal') is not None for r in rows):raise MissingRawProposalForFailedJob('MISSING_RAW_PROPOSAL_FOR_FAILED_JOB')
 return True
