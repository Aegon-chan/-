"""Progressive learning module.
Tracks task execution patterns and improves speed
through accumulated experience.
"""
from __future__ import annotations
import logging
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger("research_agent.progressive")

class ProgressiveLearner:
    """Tracks task execution and improves over time."""
    def __init__(self):
        self.task_history = defaultdict(list)
        self.learning_enabled = True

    def record_task(self, task_type, duration_ms, success=True):
        """Record a task execution for analysis."""
        self.task_history[task_type].append({
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.task_history[task_type]) % 10 == 0:
            self._analyze_trend(task_type)

    def get_task_stats(self, task_type):
        """Get statistics for a task type."""
        tasks = self.task_history.get(task_type, [])
        if not tasks:
            return {"count":0}
        durations = [t["duration_ms"] for t in tasks]
        success_rate = sum(1 for t in tasks if t["success"]) / len(tasks)
        recent = durations[-max(5,len(durations)):]
        return {
            "count": len(tasks),
            "avg_duration_ms": round(sum(durations)/len(durations),1),
            "recent_avg_ms": round(sum(recent)/len(recent),1),
            "success_rate": round(success_rate,3),
            "learning_progress": "improving" if self._is_improving(durations) else "stable",
        }

    def _is_improving(self, durations):
        """Check if recent tasks are trending faster."""
        if len(durations) < 10:
            return False
        half = len(durations)//2
        first_half = sum(durations[:half])/half
        second_half = sum(durations[half:])/len(durations[half:])
        return second_half < first_half * 0.9

    def _analyze_trend(self, task_type):
        stats = self.get_task_stats(task_type)
        if stats["count"] >= 10:
            logger.info("Progressive learning [%s]: %d tasks, avg=%.0fms, rate=%.0f%%",
                task_type, stats["count"], stats["avg_duration_ms"], stats["success_rate"]*100)

    def reset(self):
        """Clear all task history."""
        self.task_history.clear()
        logger.info("Progressive learning history cleared")
