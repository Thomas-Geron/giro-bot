# -*- mode: python ; coding: utf-8 -*-
"""Empacota o Giro Bot como aplicativo Windows (janela, sem terminal).

Usa o Edge/Chrome já instalado na máquina, então NÃO embutimos navegador —
só o driver do Playwright, que é coletado por collect_all.
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hiddenimports = collect_all("playwright")
datas += collect_data_files("sv_ttk") + [("assets", "assets")]  # tema e ícone da janela

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["canais.whatsapp", "canais.simulado"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "setuptools"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="GiroBot",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # sem janela preta de terminal
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name="GiroBot",
)
