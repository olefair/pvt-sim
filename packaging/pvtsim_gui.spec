# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

block_cipher = None

# SPECPATH is injected as a global by PyInstaller during spec execution
# Note: SPECPATH is the directory containing the spec file, not the file path
try:
    repo_root = Path(SPECPATH).resolve().parent
except NameError:
    repo_root = Path(__file__).resolve().parent.parent
onefile = os.environ.get("PVT_ONEFILE") == "1"
build_cli = os.environ.get("PVT_BUILD_CLI", "1") != "0"

hiddenimports = []
hiddenimports += collect_submodules("PySide6")
hiddenimports += collect_submodules("pyqtgraph")
hiddenimports += collect_submodules("matplotlib.backends")
hiddenimports += [
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_qt",
    "matplotlib.backends.backend_agg",
]
hiddenimports = list(dict.fromkeys(hiddenimports))

datas = []
datas += collect_data_files("matplotlib")
datas += collect_data_files("pyqtgraph")
datas += collect_data_files("PySide6", include_py_files=False)
datas += [(str(repo_root / "data" / "pure_components"), "data/pure_components")]

binaries = []
binaries += collect_dynamic_libs("PySide6")

def make_analysis(scripts):
    return Analysis(
        scripts,
        pathex=[str(repo_root)],
        binaries=list(binaries),
        datas=list(datas),
        hiddenimports=list(hiddenimports),
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=[],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
    )


a_gui = make_analysis([
    str(repo_root / "src" / "pvtapp" / "main.py"),
])
pyz_gui = PYZ(a_gui.pure, a_gui.zipped_data, cipher=block_cipher)
exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    a_gui.binaries,
    a_gui.zipfiles,
    a_gui.datas,
    name="pvtsim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    exclude_binaries=not onefile,
)

exe_cli = None

if build_cli:
    a_cli = make_analysis([
        str(repo_root / "src" / "pvtapp" / "cli.py"),
    ])
    pyz_cli = PYZ(a_cli.pure, a_cli.zipped_data, cipher=block_cipher)
    exe_cli = EXE(
        pyz_cli,
        a_cli.scripts,
        a_cli.binaries,
        a_cli.zipfiles,
        a_cli.datas,
        name="pvtsim-cli",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        exclude_binaries=not onefile,
    )
if onefile:
    app = exe_gui
    if build_cli and exe_cli:
        app_cli = exe_cli
else:
    collect_items = [exe_gui]
    if exe_cli:
        collect_items.append(exe_cli)
    collect_items.extend([a_gui.binaries, a_gui.zipfiles, a_gui.datas])
    if exe_cli:
        collect_items.extend([a_cli.binaries, a_cli.zipfiles, a_cli.datas])

    coll = COLLECT(
        *collect_items,
        strip=False,
        upx=True,
        name="pvtsim",
    )
