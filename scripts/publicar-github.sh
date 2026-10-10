#!/usr/bin/env bash
# Publicación inicial del proyecto en el GitHub de Assia-Network.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="Assia-Network/markview-code"

for program in git gh; do
  if ! command -v "$program" >/dev/null 2>&1; then
    printf 'Falta %s. Instálelo antes de continuar.\n' "$program" >&2
    exit 1
  fi
done

if ! gh auth status >/dev/null 2>&1; then
  echo 'Inicie sesión en GitHub CLI: gh auth login' >&2
  exit 1
fi

LOGIN="$(gh api user --jq .login)"
if [[ "$LOGIN" != "Assia-Network" ]]; then
  echo "La sesión actual es $LOGIN; se esperaba Assia-Network. Se cancela por seguridad." >&2
  exit 1
fi

if gh repo view "$REPO" >/dev/null 2>&1; then
  echo "El repositorio $REPO ya existe. No se sobrescribirá ni se publicará encima." >&2
  exit 1
fi

if [[ ! -d .git ]]; then
  git init -b main
fi

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo 'La rama actual debe llamarse main. Revise el estado del repositorio.' >&2
  exit 1
fi

if [[ -n "$(git remote)" ]]; then
  echo 'Hay un remoto configurado; revise el repositorio antes de publicar.' >&2
  exit 1
fi

if ! git var GIT_AUTHOR_IDENT >/dev/null 2>&1; then
  echo 'Configure git user.name y user.email antes de publicar.' >&2
  exit 1
fi

git add MarkView.py README.md requirements.txt .gitignore CONTRIBUTING.md scripts tests
if ! git diff --cached --quiet; then
  git commit -m "chore: publicación inicial de MarkView Code"
fi

if ! git rev-parse HEAD >/dev/null 2>&1; then
  echo 'No existe un commit para publicar.' >&2
  exit 1
fi

gh repo create "$REPO" \
  --public \
  --description 'Lector Markdown de escritorio en Python con pestañas, navegación y carpetas favoritas.' \
  --source=. \
  --remote=origin \
  --push

printf '\nRepositorio publicado: https://github.com/%s\n' "$REPO"
