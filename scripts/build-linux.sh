#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! python -m PyInstaller --version >/dev/null 2>&1; then
  echo 'PyInstaller no está instalado. Ejecute: python -m pip install pyinstaller' >&2
  exit 1
fi

python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name MarkView \
  --collect-all latex2mathml \
  --collect-all pymdownx \
  --collect-all markdown \
  --collect-all pygments \
  MarkView.py

echo 'Compilación finalizada: dist/MarkView/MarkView'
