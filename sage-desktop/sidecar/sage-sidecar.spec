# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the SAGE Desktop sidecar.
#
# Produces a single self-contained ``sage-sidecar.exe`` that Tauri can
# spawn via the externalBin path in production. The bundle embeds:
#   * The sidecar app (app.py, rpc.py, dispatcher.py, errors.py, handlers/)
#   * The SAGE framework (``src/``) so ``from src.core...`` resolves
#     without relying on sys.path or SAGE_ROOT.
#   * A runtime hook that puts the bundle's embedded repo on sys.path,
#     replacing the SAGE_ROOT-based path manipulation in app.py.
#
# Build with: bash sage-desktop/scripts/build-sidecar.sh
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules


# SPECPATH is set by PyInstaller at spec-eval time to the spec file's dir.
sidecar_root = Path(SPECPATH).resolve()
repo_root = sidecar_root.parents[1]

# Every ``from src.X import Y`` that _wire_handlers / _PROBE_IMPORTS
# performs at runtime. PyInstaller can't see these as static imports
# because they're guarded behind try/except inside a function body.
explicit_hidden = [
    "src",
    "src.core",
    "src.core.project_loader",
    "src.core.proposal_store",
    "src.core.proposal_executor",
    "src.core.onboarding",
    "src.core.llm_gateway",
    "src.core.queue_manager",
    "src.core.feature_request_store",
    "src.memory",
    "src.memory.audit_logger",
    "src.integrations",
    "src.integrations.build_orchestrator",
    # Sidecar modules — referenced via importlib-style string lookups in
    # dispatcher.register; safe to list explicitly.
    "rpc",
    "dispatcher",
    "errors",
    "handlers",
    "handlers.agents",
    "handlers.approvals",
    "handlers.audit",
    "handlers.backlog",
    "handlers.builds",
    "handlers.handshake",
    "handlers.llm",
    "handlers.onboarding",
    "handlers.queue",
    "handlers.solutions",
    "handlers.status",
    "handlers.yaml_edit",
]

# ``collect_submodules`` walks every submodule of ``src`` so we don't
# have to enumerate every file the framework might reach (agents,
# reflection_engine, consensus_engine, etc). Guarded with a try so the
# spec still evaluates if src/ has an optional module that fails to import.
try:
    framework_submodules = collect_submodules("src")
except Exception:
    framework_submodules = []

hiddenimports = list(dict.fromkeys(explicit_hidden + framework_submodules))

# Data files: ship the entire ``src/`` tree alongside the .py submodules
# so any ``Path(__file__).parent``-relative asset lookup inside the
# framework still resolves post-bundle. Also ships the solutions/
# starter template so onboarding can copy from it at runtime.
datas = [
    (str(repo_root / "src"), "src"),
    (str(repo_root / "solutions" / "starter"), "solutions/starter"),
]


block_cipher = None


a = Analysis(
    [str(sidecar_root / "__main__.py")],
    pathex=[str(sidecar_root), str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(sidecar_root / "sage_sidecar_runtime_hook.py")],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="sage-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
)
