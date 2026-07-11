import os
import sys

# Set matplotlib backend to Agg for headless rendering
os.environ.setdefault("MPLBACKEND", "Agg")

# Ensure data directories exist
_data_dirs = [
    "data/logs",
    "data/chroma_db",
    "data/memories",
    "data/lora_checkpoints",
    "reports/output",
]
for d in _data_dirs:
    os.makedirs(os.path.join(os.path.dirname(sys.executable), d), exist_ok=True)
    os.makedirs(d, exist_ok=True)

# Try to apply user config
try:
    import json
    cfg_path = os.path.join(os.path.dirname(sys.executable), "data", "user_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r") as f:
            cfg = json.load(f)
        for k, v in cfg.items():
            if v:
                env_key = {
                    "deepseek_key": "DEEPSEEK_API_KEY",
                    "kimi_key": "KIMI_API_KEY",
                    "openai_key": "OPENAI_API_KEY",
                }.get(k)
                if env_key:
                    os.environ[env_key] = v
except Exception:
    pass
