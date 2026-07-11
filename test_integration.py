# -*- coding: utf-8 -*-
"""Integration test for the new agent chat + analysis + report pipeline."""
import asyncio, os, sys, json
sys.path.insert(0, r"C:\Users\24622\Desktop\科研Agent")
os.chdir(r"C:\Users\24622\Desktop\科研Agent")

from backend.models import init_models
from backend.config import settings
print(f"DeepSeek key set: {bool(settings.deepseek_api_key)}")
print(f"Key prefix: {settings.deepseek_api_key[:8] if settings.deepseek_api_key else 'N/A'}...")
init_models()

from backend.core.agent import ResearchAgent

# Test 1: _detect_intent
print("\n" + "=" * 60)
print("TEST 1: _detect_intent")
print("=" * 60)

agent = ResearchAgent(session_id="test-intent")

test_cases = [
    ("你好，今天天气怎么样？", False, False),
    ("分析GNSS位移数据", True, False),
    ("分析InSAR形变数据并生成报告", True, True),
    ("帮我计算降雨量趋势", True, False),
    ("生成日报", False, True),
    ("地下水位变化分析", True, False),
    ("孔压数据异常检测", True, False),
    ("生成月度报告", False, True),
    ("帮我看看这个数据", False, False),
]

all_pass = True
for query, exp_analysis, exp_report in test_cases:
    result = agent._detect_intent(query)
    a_ok = result["needs_analysis"] == exp_analysis
    r_ok = result["needs_report"] == exp_report
    status = chr(10003) if (a_ok and r_ok) else chr(10007)
    if status == chr(10007):
        all_pass = False
    print(f"  {status} query={query[:30]:30s} -> analysis={result['needs_analysis']} report={result['needs_report']}")

print(f"\n  Intent detection: {'ALL PASS' if all_pass else 'SOME FAILED'}")

# Test 2: _format_analysis_summary
print("\n" + "=" * 60)
print("TEST 2: _format_analysis_summary (mock data)")
print("=" * 60)

mock_result = {
    "success": True,
    "code": "import numpy as np\nprint('hello')",
    "result": {
        "stdout": "trend slope: 0.025\nmax velocity: 3.2 mm/yr\n",
        "data": {"trend_slope": 0.025, "max_velocity": 3.2},
        "figures": [{"id": "fig_0", "mime": "image/png", "b64": "dGVzdA=="}],
        "execution_time_ms": 1234.5,
    }
}

summary = agent._format_analysis_summary(mock_result)
print(f"  Summary length: {len(summary)} chars")
assert "分析输出" in summary, "Missing analysis output"
assert "trend_slope" in summary, "Missing data"
print("  chr(10003) Format analysis summary PASS")

# Test 3: _format_analysis_stream
print("\n" + "=" * 60)
print("TEST 3: _format_analysis_stream (mock data)")
print("=" * 60)

stream_text = agent._format_analysis_stream(mock_result)
print(f"  Stream text length: {len(stream_text)} chars")
assert "分析完成" in stream_text, "Missing completion marker"
print("  chr(10003) Format analysis stream PASS")

# Test 4: full streaming chat with analysis intent
print("\n" + "=" * 60)
print("TEST 4: stream_chat with GNSS analysis query")
print("=" * 60)

async def test_analysis_stream():
    agent4 = ResearchAgent(session_id="test-full-analysis")
    collected = []
    async for token in agent4.stream_chat("分析GNSS位移数据的趋势和突变点"):
        collected.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()
    
    full = "".join(collected)
    has_status = "正在分析数据" in full or "开始分析" in full
    has_analysis = "分析完成" in full or "数据" in full
    print(f"\n\n  Total: {len(full)} chars, {len(collected)} chunks")
    print(f"  Has status: {has_status}")
    print(f"  Has analysis content: {has_analysis}")
    
    # Check for uploaded chart images
    import glob
    charts = sorted(glob.glob("data/uploads/analysis_*.png"))
    print(f"  Generated charts: {len(charts)}")
    for c in charts:
        sz = os.path.getsize(c)
        print(f"    {c} ({sz} bytes)")

asyncio.run(test_analysis_stream())

print("\n" + "=" * 60)
print("ALL TESTS COMPLETE")
print("=" * 60)
