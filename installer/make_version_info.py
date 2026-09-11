"""Write build/version_info.txt so WarehouseManager.exe shows version, company and
product name under Windows 'Properties > Details'. Called by the CI workflow."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.version import __app_name__, __description__, __dev_company__, __version__  # noqa: E402

numbers = [int(n) for n in re.findall(r"\d+", __version__.split("-")[0])][:3]
numbers += [0] * (3 - len(numbers))
build = re.search(r"dev\.(\d+)", __version__)
numbers.append(int(build.group(1)) if build else 0)
tup = tuple(numbers)

TEMPLATE = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', {__dev_company__!r}),
      StringStruct('FileDescription', {__description__!r}),
      StringStruct('FileVersion', {__version__!r}),
      StringStruct('InternalName', 'WarehouseManager'),
      StringStruct('LegalCopyright', {('(c) ' + __dev_company__)!r}),
      StringStruct('OriginalFilename', 'WarehouseManager.exe'),
      StringStruct('ProductName', {__app_name__!r}),
      StringStruct('ProductVersion', {__version__!r})])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
out = ROOT / "build" / "version_info.txt"
out.parent.mkdir(exist_ok=True)
out.write_text(TEMPLATE, encoding="utf-8")
print(f"Wrote {out} for version {__version__} {tup}")
