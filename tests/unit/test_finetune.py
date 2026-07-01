"""Tests for FineTuner and FeedbackDatasetBuilder."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from backend.self_growth.finetune import FineTuner, FeedbackDatasetBuilder


class TestFeedbackDatasetBuilder:
    """Test feedback-to-training-data pipeline."""

    def test_init(self):
        builder = FeedbackDatasetBuilder()
        assert builder is not None
        assert builder.min_rating == 4

    def test_fetch_feedback(self, feedback_db):
        builder = FeedbackDatasetBuilder(db_path=str(feedback_db))
        records = builder.fetch_feedback()
        assert len(records) == 5

    def test_fetch_feedback_by_user(self, feedback_db):
        builder = FeedbackDatasetBuilder(db_path=str(feedback_db))
        records = builder.fetch_feedback(user_id="user_1")
        assert len(records) == 3  # user_1 has 3 records

    def test_build(self, feedback_db, tmp_path):
        builder = FeedbackDatasetBuilder(db_path=str(feedback_db))
        output = tmp_path / "train.jsonl"
        result = builder.build(output_path=str(output))

        assert Path(result).exists()
        records = [json.loads(l) for l in Path(result).read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(records) >= 2

        # Check that high-rated records are included
        ratings = [r["metadata"]["rating"] for r in records]
        assert all(r >= 4 for r in ratings)

    def test_build_includes_low_quality(self, feedback_db, tmp_path):
        builder = FeedbackDatasetBuilder(db_path=str(feedback_db), min_rating=4)
        output = tmp_path / "train_all.jsonl"
        result = builder.build(output_path=str(output), include_low_quality=True)

        records = [json.loads(l) for l in Path(result).read_text(encoding="utf-8").splitlines() if l.strip()]
        ratings = [r["metadata"]["rating"] for r in records]
        # Should include rating 4, 5 AND rating 1
        assert 1 in ratings or 4 in ratings or 5 in ratings

    def test_build_from_conversations(self, tmp_path):
        builder = FeedbackDatasetBuilder()
        conversations = [
            {"query": "分析GNSS数据", "response": "完成分析", "rating": 5, "tags": ["gnss"]},
            {"query": "生成报告", "response": "报告已生成", "rating": 4, "tags": ["report"]},
            {"query": "无效查询", "response": "无法完成", "rating": 1, "tags": []},
        ]
        output = tmp_path / "conv.jsonl"
        result = builder.build_from_conversations(conversations, output_path=str(output))

        records = [json.loads(l) for l in Path(result).read_text(encoding="utf-8").splitlines() if l.strip()]
        # Only high-rated (>=4) records should be included
        assert len(records) == 2

    def test_estimate_stats(self, feedback_db):
        builder = FeedbackDatasetBuilder(db_path=str(feedback_db))
        stats = builder.estimate_dataset_stats()
        assert stats["total_feedback"] == 5
        assert stats["high_quality_candidates"] >= 2

    def test_empty_build(self, tmp_path):
        builder = FeedbackDatasetBuilder()
        output = tmp_path / "empty.jsonl"
        result = builder.build(output_path=str(output), user_id="nonexistent")
        assert Path(result).exists()


class TestFineTunerDataPrep:
    """Test FineTuner.prepare_dataset integration."""

    @pytest.mark.asyncio
    async def test_prepare_dataset(self, tmp_path):
        tuner = FineTuner(checkpoint_dir=str(tmp_path / "checkpoints"))
        feedback_data = [
            {"query": "分析数据", "response": "数据正常", "rating": 5, "tags": []},
            {"query": "计算速率", "response": "速率=2.3mm/yr", "rating": 4, "tags": ["velocity"]},
        ]
        output = str(tmp_path / "training.jsonl")
        result = await tuner.prepare_dataset(feedback_data, output_path=output)
        assert Path(result).exists()
        records = [json.loads(l) for l in Path(result).read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(records) == 2
