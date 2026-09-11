# PyInstaller build recipe.  Build with:  python run.py --build
#   (or: pyinstaller --noconfirm --clean WarehouseManager.spec)
# Produces a folder build (dist/WarehouseManager/) which the Inno Setup installer packages.
# A folder build starts faster than --onefile and is flagged by antivirus less often.
from pathlib import Path

version_file = Path("build/version_info.txt")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets/app.ico", "assets"), ("assets/app.png", "assets")],
    hiddenimports=["openpyxl"],          # imported lazily by the export button
    hookspath=[],
    runtime_hooks=[],
    # openpyxl uses these only if present; excluding them keeps the build small
    excludes=["pytest", "PyInstaller", "numpy", "PIL", "lxml", "yaml", "pandas",
              "matplotlib", "scipy", "IPython", "setuptools"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WarehouseManager",
    debug=False,
    strip=False,
    upx=False,
    console=False,                       # no black console window
    icon="assets/app.ico",
    version=str(version_file) if version_file.exists() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="WarehouseManager")
