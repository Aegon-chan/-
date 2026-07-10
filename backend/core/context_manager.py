"""对话上下文管理模块

管理 ResearchAgent 的对话上下文累积，在每次 LLM 调用前自动修剪，
防止上下文无限膨胀导致响应变慢。

支持策略：
- truncate: 直接截断，保留最近 N 轮 + 当前系统上下文
- summarize: (预留) 用 LLM 将旧对话压缩为摘要
"""

from __future__ import annotations

import logging

from backend.models.base import Message

logger = logging.getLogger("research_agent.core.context")

# 粗略估算：混合中英文文本约 4 字符 / token
CHARS_PER_TOKEN = 4.0


def estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数"""
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def count_messages_tokens(messages: list[Message]) -> int:
    """估算消息列表的总 token 数"""
    return sum(estimate_tokens(m.content) for m in messages)


def count_rounds(messages: list[Message]) -> int:
    """统计对话轮数（user + assistant 配对，忽略 system 消息）"""
    conv = [m for m in messages if m.role != "system"]
    pairs = 0
    i = 0
    while i < len(conv) - 1:
        if conv[i].role == "user" and conv[i + 1].role == "assistant":
            pairs += 1
            i += 2
        else:
            i += 1
    return pairs


def _format_summary_prompt(old_messages: list[Message]) -> str:
    """构造历史摘要的 prompt"""
    lines = []
    for m in old_messages:
        role_label = "用户" if m.role == "user" else "助手"
        content = m.content[:200] if m.content else ""
        lines.append(f"{role_label}: {content}")
    return (
        "请将以下对话历史压缩为一段简洁的中文摘要（50-100 字），"
        "保留关键信息：用户的偏好、提到的知识点、已执行的分析操作。\n\n"
        + "\n".join(lines)
    )


class ContextManager:
    """对话上下文管理器

    在每次 LLM 调用前修剪 `messages` 列表，防止无限膨胀。
    直接修改原列表（原地操作）。

    Attributes:
        max_rounds: 最大保留的对话轮数 (user+assistant 配对)
        max_tokens: 消息列表的最大估算 token 数
        reserve_recent_rounds: 保留的最近对话轮数（始终保留）
        strategy: 修剪策略 ("truncate" 或 "summarize")
        enabled: 是否启用上下文管理
    """

    def __init__(
        self,
        max_rounds: int = 30,
        max_tokens: int = 12000,
        reserve_recent_rounds: int = 10,
        strategy: str = "truncate",
        enabled: bool = True,
    ):
        self.max_rounds = max_rounds
        self.max_tokens = max_tokens
        self.reserve_recent_rounds = reserve_recent_rounds
        self.strategy = strategy
        self.enabled = enabled

        # 历史统计
        self._trim_count: int = 0
        self._summary: str = ""
        self._last_trimmed_rounds: int = 0

    # ---- 主入口 ----

    def trim_context(self, messages: list[Message]) -> list[Message]:
        """修剪消息列表，使其不超过限制。

        Args:
            messages: 当前对话消息列表（会被原地修改）

        Returns:
            修剪后的消息列表
        """
        if not self.enabled or not messages:
            return messages

        total_tokens = count_messages_tokens(messages)
        total_rounds = count_rounds(messages)

        if total_tokens <= self.max_tokens and total_rounds <= self.max_rounds:
            return messages

        self._last_trimmed_rounds = total_rounds
        logger.info(
            "Trimming context: %d rounds, ~%d tokens "
            "(limit: %d rounds / %d tokens)",
            total_rounds, total_tokens, self.max_rounds, self.max_tokens,
        )

        if self.strategy == "summarize" and total_rounds > self.reserve_recent_rounds * 2:
            result = self._summarize_old(messages)
        else:
            result = self._truncate(messages)

        self._trim_count += 1
        trimmed_tokens = total_tokens - count_messages_tokens(result)
        logger.info(
            "Context trimmed (#%d): %d rounds -> ~%d tokens saved. "
            "Kept %d messages.",
            self._trim_count, total_rounds, trimmed_tokens, len(result),
        )
        return result

    # ---- 截断策略 ----

    def _truncate(self, messages: list[Message]) -> list[Message]:
        """保留最新的系统上下文 + 最近的 N 轮对话。

        - 只保留最后一条 system 消息（当前查询的上下文）
        - 保留最近 reserve_recent_rounds 轮对话
        """
        last_system_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "system":
                last_system_idx = i
                break

        kept_system = []
        if last_system_idx >= 0:
            kept_system.append(messages[last_system_idx])

        conversation = [m for m in messages if m.role != "system"]
        recent_count = self.reserve_recent_rounds * 2  # user + assistant 成对
        recent_conversation = conversation[-recent_count:] if conversation else []

        result = kept_system + recent_conversation
        messages[:] = result
        return result

    def _summarize_old(self, messages: list[Message]) -> list[Message]:
        """将旧对话压缩为摘要 + 保留最近对话。

        策略：
        1. 保留最后一条 system 消息
        2. 保留最近 reserve_recent_rounds 轮完整对话
        3. 将更早的对话替换为一条 system 摘要消息

        注意：当前使用简单截断作为 fallback，
        LLM 摘要功能后续实现。
        """
        last_system_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "system":
                last_system_idx = i
                break

        kept_system = []
        if last_system_idx >= 0:
            kept_system.append(messages[last_system_idx])

        conversation = [m for m in messages if m.role != "system"]
        recent_count = self.reserve_recent_rounds * 2

        if len(conversation) > recent_count:
            old_part = conversation[:-recent_count]
            recent_part = conversation[-recent_count:]

            # 如果已有历史摘要，追加新内容
            if self._summary:
                old_text = _format_summary_prompt(old_part)
                summary_content = (
                    f"[对话历史摘要]\n{self._summary}\n\n"
                    f"[新增历史]\n{old_text[:500]}"
                )
            else:
                summary_content = _format_summary_prompt(old_part)[:600]

            summary_msg = Message(
                role="system",
                content=summary_content,
            )
            result = kept_system + [summary_msg] + recent_part
        else:
            result = kept_system + conversation

        messages[:] = result
        return result

    # ---- 配置与状态 ----

    def update_summary(self, summary: str) -> None:
        """更新历史摘要"""
        self._summary = summary

    def get_summary(self) -> str:
        """获取当前的历史摘要"""
        return self._summary

    def get_stats(self) -> dict:
        """获取上下文管理的统计信息"""
        return {
            "enabled": self.enabled,
            "strategy": self.strategy,
            "max_rounds": self.max_rounds,
            "max_tokens": self.max_tokens,
            "reserve_recent_rounds": self.reserve_recent_rounds,
            "trim_count": self._trim_count,
            "last_trimmed_rounds": self._last_trimmed_rounds,
            "has_summary": bool(self._summary),
        }

    def to_config(self) -> dict:
        """导出配置（不含运行时状态）"""
        return {
            "max_rounds": self.max_rounds,
            "max_tokens": self.max_tokens,
            "reserve_recent_rounds": self.reserve_recent_rounds,
            "strategy": self.strategy,
            "enabled": self.enabled,
        }
