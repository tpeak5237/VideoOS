"""Pure deterministic edit planning from local analysis artifacts."""

from .shorts import ShortCandidate, score_short_candidates
from .talking_head import plan_talking_head

__all__ = ["ShortCandidate", "plan_talking_head", "score_short_candidates"]
