# Build from the project root on Windows x64.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis(
    [str(root / 'app.py')], pathex=[str(root)],
    binaries=[], datas=[(str(root / 'task.ps1'), '.'),
                        (str(root / 'THIRD_PARTY_NOTICES.txt'), '.'),
                        (str(root / 'third_party_licenses'), 'third_party_licenses')],
    hiddenimports=[], hookspath=[], runtime_hooks=[], excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='SparkKeeper', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False,
          uac_admin=False)
