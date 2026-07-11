import requests, json, sys
BASE = "http://127.0.0.1:8010"

resp = requests.post(f"{BASE}/api/v1/sessions/", json={"user_id": "default", "title": "test", "model_id": "deepseek-chat"})
assert resp.status_code == 200, f"Session creation failed: {resp.text}"
sid = resp.json()["id"]
print(f"[PASS] 1. Session created: {sid}")

resp2 = requests.post(f"{BASE}/api/v1/chat/completions", json={"session_id": sid, "message": "自我介绍"})
assert resp2.status_code == 200, f"Chat failed: {resp2.text}"
content = resp2.json().get("content", "")
print(f"[PASS] 2. Chat reply ({len(content)} chars)")

resp3 = requests.get(f"{BASE}/api/v1/sessions/{sid}")
msgs = resp3.json().get("messages", [])
assert len(msgs) == 2, f"Expected 2 msgs, got {len(msgs)}"
print(f"[PASS] 3. Session has {len(msgs)} messages")

sys.path.insert(0, ".")
sys.path.insert(0, ".venv/Lib/site-packages")
from backend.core.agent import ResearchAgent

agent = ResearchAgent(session_id=sid, model_id="deepseek-chat", user_id="default")
agent.load_history([{"role": m["role"], "content": m["content"]} for m in msgs])
assert len(agent.messages) == 2, f"Expected 2, got {len(agent.messages)}"
print(f"[PASS] 4. Agent loaded {len(agent.messages)} messages from history")

agent2 = ResearchAgent(session_id=sid, model_id="deepseek-chat", user_id="default")
agent2.load_history([{"role": m["role"], "content": m["content"]} for m in msgs])
assert len(agent2.messages) == 2
print(f"[PASS] 5. Refresh sim: agent reloaded {len(agent2.messages)} messages")

print("[ALL TESTS PASSED]")
