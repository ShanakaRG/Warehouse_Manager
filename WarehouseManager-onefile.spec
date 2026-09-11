# Single-file build: one WarehouseManager.exe the client can run without installing anything.
# Build with:  pyinstaller --noconfirm --clean WarehouseManager-onefile.spec   (-> dist/WarehouseManager.exe)
# Starts a few seconds slower than the folder build because it unpacks itself on every start.
from pathlib import Path

version_file = Path("build/version_info.txt")

a = Analysis(
    ["main.py"],
    datas=[("assets/app.ico", "assets"), ("assets/app.png", "assets")],
    hiddenimports=["openpyxl"],
    excludes=["pytest", "PyInstaller", "numpy", "PIL", "lxml", "yaml", "pandas",
              "matplotlib", "scipy", "IPython", "setuptools"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WarehouseManager",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/app.ico",
    version=str(version_file) if version_file.exists() else None,
)
