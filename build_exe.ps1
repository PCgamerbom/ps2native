# Gera PS2Native.exe (interface gráfica) no Windows.
# Uso:  powershell -ExecutionPolicy Bypass -File build_exe.ps1
$ErrorActionPreference = "Stop"
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m unittest discover -s tests -t .
.\.venv\Scripts\pyinstaller --noconfirm --windowed --name PS2Native --collect-submodules ps2native run_gui.py
Write-Host "Pronto: dist\PS2Native\PS2Native.exe"
