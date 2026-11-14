"""Shared lesson completion rules used by progress and checkpoint flows."""

COMPLETION_THRESHOLD = 0.1


def is_lesson_completed(duration_seconds, watched_seconds: float) -> bool:
    """Return whether a learner has watched the configured share of a lesson."""
    return bool(
        duration_seconds
        and duration_seconds > 0
        and watched_seconds >= duration_seconds * COMPLETION_THRESHOLD
    )


def sync_lesson_progress_completion(lesson, progress) -> bool:
    """Recompute a stored progress flag, including rows predating duration backfill."""
    completed = is_lesson_completed(
        lesson.duration_seconds,
        progress.watched_seconds,
    )
    if progress.completed != completed:
        progress.completed = completed
    return completed
