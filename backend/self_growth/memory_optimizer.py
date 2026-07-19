"""Memory weight optimization module.

Adjusts memory weights based on user feedback, time decay,
and usage patterns to keep the most relevant memories at the top.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("research_agent.memory_optimizer")


class MemoryOptimizer:
    """Optimizes memory weights based on feedback and usage."""

    # Feedback rating to weight delta mapping
    RATING_DELTAS = {5: 0.2, 4: 0.1, 3: 0.0, 2: -0.1, 1: -0.2, -1: -0.3}
    MAX_WEIGHT = 5.0
    MIN_WEIGHT = 0.0
    DEFAULT_HALF_LIFE_DAYS = 30.0

    def update_weight(self, feedback_rating: int) -> float:
        """Calculate weight delta from feedback rating.

        Args:
            feedback_rating: Rating value (5=excellent, 1=poor, -1=negative)

        Returns:
            Weight delta to apply
        """
        return self.RATING_DELTAS.get(feedback_rating, 0.0)

    def decay(self, weight: float, days: float, half_life: float = None) -> float:
        """Apply time-based decay using exponential half-life model.

        Args:
            weight: Current weight value
            days: Number of days elapsed
            half_life: Half-life in days (default: 30)

        Returns:
            Decayed weight value
        """
        if half_life is None:
            half_life = self.DEFAULT_HALF_LIFE_DAYS
        if days <= 0 or half_life <= 0:
            return weight
        decay_factor = 0.5 ** (days / half_life)
        new_weight = weight * decay_factor
        return max(self.MIN_WEIGHT, new_weight)

    def update_with_feedback(self, current_weight: float, feedback_rating: int,
                              days_since_last_access: float = 0.0) -> float:
        """Combined update: apply feedback delta then time decay.

        Args:
            current_weight: Current memory weight
            feedback_rating: User feedback rating
            days_since_last_access: Days since memory was last accessed

        Returns:
            New weight value
        """
        delta = self.update_weight(feedback_rating)
        applied = current_weight + delta
        if days_since_last_access > 0:
            applied = self.decay(applied, days_since_last_access)
        return max(self.MIN_WEIGHT, min(self.MAX_WEIGHT, applied))

    def normalize_weights(self, memories: list) -> list:
        """Normalize weights to [0, 1] range across a memory list.

        Args:
            memories: List of dicts with "weight" key

        Returns:
            Same list with normalized weights
        """
        if not memories:
            return memories

        weights = [m.get("weight", 0.0) for m in memories]
        max_w = max(weights) if weights else 1.0
        min_w = min(weights) if weights else 0.0
        range_w = max_w - min_w if max_w != min_w else 1.0

        for m in memories:
            raw = m.get("weight", 0.0)
            m["weight_normalized"] = round((raw - min_w) / range_w, 3)
        return memories

    def merge(self, memories: list, similarity_threshold: float = 0.7) -> list:
        """Merge duplicate or highly similar memories.

        Args:
            memories: List of memory dicts with key, value, weight
            similarity_threshold: Threshold for key similarity

        Returns:
            Merged memory list with deduplication
        """
        if not memories:
            return []

        # Group by similar keys (simple prefix matching)
        merged = {}
        for m in memories:
            key = str(m.get("key", ""))
            value = str(m.get("value", ""))
            weight = float(m.get("weight", 0.5))

            # Check if similar key exists
            found = False
            for existing_key in list(merged.keys()):
                # Simple Jaccard similarity on key characters
                set1 = set(key[:min(len(key), 20)])
                set2 = set(existing_key[:min(len(existing_key), 20)])
                if not set1 or not set2:
                    continue
                jaccard = len(set1 & set2) / len(set1 | set2)
                if jaccard >= similarity_threshold:
                    # Merge: use higher weight, concatenate values
                    existing = merged[existing_key]
                    existing["weight"] = max(existing.get("weight", 0), weight)
                    if value not in existing.get("value", ""):
                        existing["value"] = existing.get("value", "") + "; " + value
                    found = True
                    break

            if not found:
                merged[key] = {"key": key, "value": value, "weight": weight}

        return list(merged.values())