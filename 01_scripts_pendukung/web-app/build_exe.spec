# -*- mode: python ; coding: utf-8 -*-
import sys, os
from pathlib import Path

sys.setrecursionlimit(5000)

_cwd = os.getcwd()
dist_dir = Path(_cwd) / 'dist'
if not dist_dir.is_dir():
    raise SystemExit(f'ERROR: Build not found at {dist_dir}. Run npm run build first.')

# Bersihkan sisa .exe lama di dist jika ada, agar tidak terjadi recursive bundling
for old_exe in dist_dir.glob('*.exe'):
    try:
        old_exe.unlink()
    except Exception:
        pass

# Masukkan hanya aset frontend web (html, js, css, svg, json, worker), jangan sertakan binary
datas = []
for p in dist_dir.rglob('*'):
    if p.is_file() and p.suffix.lower() not in ('.exe', '.zip', '.tmp', '.pdb', '.log'):
        rel_parent = p.relative_to(dist_dir).parent
        target_folder = 'dist' if str(rel_parent) == '.' else f'dist/{rel_parent.as_posix()}'
        datas.append((str(p), target_folder))

timemark_dir = Path(_cwd) / 'timemark_engine'
if timemark_dir.is_dir():
    datas.append((str(timemark_dir), 'timemark_engine'))

tesseract_dir = Path(r'C:\Program Files\Tesseract-OCR')
if tesseract_dir.is_dir():
    datas.append((str(tesseract_dir), 'tesseract'))

poppler_dir = Path(_cwd).parent / 'Aplikasi' / 'poppler'
if poppler_dir.is_dir():
    datas.append((str(poppler_dir), 'poppler'))

block_cipher = None

a = Analysis(
    ['run_desktop_webview.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'webview',
        'webview.platforms.edgechromium',
        'http.server', 'socketserver',
        'json', 'base64', 'urllib.parse', 'threading',
        'pytesseract', 'pdf2image', 'PIL', 'PIL.ImageOps', 'PIL.Image',
        'tempfile', 'io', 're',
        'requests', 'playwright', 'playwright.sync_api',
        'fitz', 'pdfplumber', 'pypdf', 'openpyxl', 'numpy',
        'cryptography', 'pypdf._crypt_providers._cryptography',
        'updater_engine', 'timemark_engine', 'timemark_engine.pipeline_runner',
        'timemark_engine.date_changer_engine',
        'timemark_engine.personnel_changer_engine',
        'timemark_engine.extract_file_personnel',
        'timemark_engine.export_schedule_excel',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[
        'tkinter', 'unittest', 'pdb', 'test',
        'torch', 'torchvision', 'torchaudio',
        'cv2', 'scipy', 'pandas', 'matplotlib',
        'transformers', 'sympy', 'IPython', 'jupyter',
        'sklearn', 'scikit_learn', 'nltk', 'spacy',
        'lxml', 'websockets', 'uvicorn', 'anyio',
        'jsonschema', 'setuptools', 'pip', 'wheel', 'tensorboard',
    ],
    cipher=block_cipher, noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name='SintelisUtility', debug=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=True,
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
