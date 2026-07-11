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
         # .env.example for first-run setup
         ('.env.example', '.'),
         # NiceGUI static assets
         ('frontend\\assets\\*', 'frontend\\assets'),
         # User config (will be created on first run)
         ('data\\user_config.json', 'data'),
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
         # ── NiceGUI additional ──
         'nicegui',
         'nicegui.elements',
         'nicegui.elements.chat_message',
         'nicegui.elements.markdown',
         'nicegui.functions',
         'nicegui.globals',
         'nicegui.storage',
         'nicegui.background_tasks',
         'nicegui.native',
         'websockets',
         'websockets.legacy',
         'httptools',
         # ── ChromaDB ──
         'chromadb.api.segment',
         'chromadb.api.fastapi',
         'chromadb.segment.impl.manager.distributed',
         'chromadb.segment.impl.metadata',
         'chromadb.segment.impl.vector',
         'chromadb.telemetry.posthog',
         'chromadb.telemetry.product',
         # ── Sentence-Transformers ──
         'sentence_transformers.models',
         'sentence_transformers.cross_encoder',
         'sentence_transformers.SentenceTransformer',
         'sentence_transformers.util',
         # ── Pydantic v1 compat (needed by ChromaDB) ──
         'pydantic.v1',
         'pydantic.v1.fields',
         'pydantic.v1.main',
         'pydantic.v1.generics',
         'pydantic.v1.schema',
         'pydantic.v1.types',
         'pydantic.v1.utils',
         'pydantic.v1.error_wrappers',
         'pydantic.v1.validators',
         'pydantic.v1.dataclasses',
         'pydantic.v1.class_validators',
         'pydantic.v1.json',
         'pydantic.v1.networks',
         'pydantic.v1.color',
         'pydantic.v1.datetime_parse',
         'pydantic.v1.env_settings',
         # ── SQLAlchemy / Alembic additional ──
         'sqlalchemy.ext.asyncio',
         'mako',
         'mako.runtime',
         'alembic.runtime.migration',
         'alembic.script',
         'alembic.script.base',
         'alembic.autogenerate',
         'alembic.ddl',
         'alembic.ddl.sqlite',
         # ── Matplotlib backends ──
         'matplotlib.backends.backend_agg',
         'matplotlib.backends.backend_pdf',
         'matplotlib.backends.backend_svg',
         # ── Plotly ──
         'plotly.validators',
         # ── Report generators ──
         'docx.shared',
         'docx.enum',
         'docx.enum.text',
         'docx.oxml',
         'fpdf.fonts',
         # ── Data science ──
         'numpy.core.multiarray',
         'pandas._libs.parsers',
         'scipy.special',
         'scipy.spatial',
         'scipy.ndimage',
         'statsmodels.tsa.stattools',
         'statsmodels.regression.linear_model',
         # ── Pydantic Settings ──
         'pydantic_settings',
         'pydantic_settings.sources',
         'dotenv',
         # ── Net / HTTP ──
         'httpx',
         'httpcore',
         'httpcore._async',
         'sniffio',
         'anyio',
         'anyio.streams',
         'anyio.streams.memory',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
         'frontend\\runtime_hook.py',
    excludes=[
        'tkinter',
        'matplotlib.tests',
         'matplotlib.backends.backend_qt5agg',
         'matplotlib.backends.backend_qt4agg',
         'matplotlib.backends.backend_gtk3agg',
         'matplotlib.backends.backend_gtk4agg',
         'matplotlib.backends.backend_tkagg',
         'matplotlib.backends.backend_wxagg',
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
         'notebook',
         'ipython',
         'jupyter',
         'jedi',
         'parso',
         'trl',
         'accelerate',
         'bitsandbytes',
        'chromadb.test',
         'test',
         'tests',
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
