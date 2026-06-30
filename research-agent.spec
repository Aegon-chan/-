# -*- mode: python ; coding: utf-8 -*-
"""
Research Agent — PyInstaller spec

Builds a single-folder Windows executable containing the NiceGUI frontend
with all backend modules bundled inline.

Usage:
    pyinstaller research-agent.spec --clean --noconfirm
"""

import sys
from pathlib import Path

block_cipher = None

# ── Collect all backend modules ──
a = Analysis(
    ['frontend\\app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Jinja2 report templates
        ('backend\\reporting\\templates\\*.html.j2', 'backend\\reporting\\templates'),
        # Alembic migration config
        ('backend\\alembic.ini', 'backend'),
        ('backend\\db\\migrations\\*', 'backend\\db\\migrations'),
        ('backend\\db\\migrations\\versions\\*', 'backend\\db\\migrations\\versions'),
    ],
    hiddenimports=[
        # Backend core
        'backend',
        'backend.config',
        'backend.core',
        'backend.core.agent',
        'backend.core.exceptions',
        'backend.core.memory',
        'backend.core.sandbox',
        'backend.core.strategy',
        # Models
        'backend.models',
        'backend.models.base',
        'backend.models.registry',
        'backend.models.adapters',
        'backend.models.adapters.deepseek',
        'backend.models.adapters.kimi',
        'backend.models.adapters.openai_compat',
        # Analysis
        'backend.analysis',
        'backend.analysis.cache',
        'backend.analysis.codegen',
        'backend.analysis.cross_correlation',
        'backend.analysis.gnss',
        'backend.analysis.groundwater',
        'backend.analysis.insar',
        'backend.analysis.pore_pressure',
        'backend.analysis.rainfall',
        # Retrieval
        'backend.retrieval',
        'backend.retrieval.cases',
        'backend.retrieval.literature',
        'backend.retrieval.standards',
        'backend.retrieval.vector_store',
        # Reporting
        'backend.reporting',
        'backend.reporting.charts',
        'backend.reporting.charts_matplotlib',
        'backend.reporting.report_generator',
        # Self-growth
        'backend.self_growth',
        'backend.self_growth.feedback',
        'backend.self_growth.finetune',
        'backend.self_growth.memory_optimizer',
        'backend.self_growth.prompt_optimizer',
        # API
        'backend.api',
        'backend.api.analysis',
        'backend.api.chat',
        'backend.api.feedback',
        'backend.api.knowledge',
        'backend.api.models',
        'backend.api.self_growth',
        'backend.api.sessions',
        # Schemas
        'backend.schemas',
        'backend.schemas.chat',
        'backend.schemas.common',
        'backend.schemas.knowledge',
        'backend.schemas.sessions',
        # DB
        'backend.db',
        'backend.db.models',
        'backend.db.session',
        # Alembic
        'alembic',
        'alembic.runtime',
        'alembic.config',
        # NiceGUI dependencies
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.middleware',
        'uvicorn.middleware.asgi2',
        'uvicorn.middleware.wsgi',
        'uvicorn.middleware.proxy_headers',
        'uvicorn.workers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib.tests',
        'numpy.testing',
        'pandas.tests',
        'scipy.tests',
        'PIL',
        'cv2',
        'torch',
        'transformers',
        'peft',
        'datasets',
        'sentence_transformers',
        'chromadb.test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── Collect all package data files ──
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ResearchAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Hide console window (GUI mode)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend\\assets\\icon.ico' if Path('frontend\\assets\\icon.ico').exists() else None,
)

# ── Also create a one-folder bundle for easier debugging ──
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ResearchAgent',
)
