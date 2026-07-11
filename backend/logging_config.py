import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "./data/logs/research_agent.log",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True,
) -> logging.Logger:
    """Configure structured logging with rotation."""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        fh = RotatingFileHandler(
            str(log_path), maxBytes=max_bytes,
            backupCount=backup_count, encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(fh)

    if console and not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in root.handlers
    ):
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-5s | %(message)s", datefmt="%H:%M:%S",
        ))
        root.addHandler(ch)

    for name in ("uvicorn.access", "chromadb", "httpx", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return root
