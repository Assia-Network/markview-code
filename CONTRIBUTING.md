# Contribuciones a MarkView Code

## Objetivo

Mantener un historial de cambios verificables y facilitar su revisión antes de integrar modificaciones en la rama `main`.

## Flujo de trabajo

1. Cree una rama con un nombre descriptivo: `feat/...`, `fix/...` o `docs/...`.
2. Realice un cambio concreto y delimitado.
3. Ejecute al menos las comprobaciones de sintaxis y navegación.
4. Publique la rama y abra un pull request hacia `main`.
5. Describa la motivación, los archivos modificados y las pruebas realizadas.
6. Fusione solo cuando el cambio esté revisado y sea integrable.

### Ejemplo

```bash
git switch main
git pull --ff-only origin main
git switch -c docs/actualizar-instrucciones

# Editar README.md o cualquier archivo relevante
python -m py_compile MarkView.py
python tests/test_navigation.py

git add README.md
git commit -m "docs: actualizar las instrucciones de uso"
git push -u origin docs/actualizar-instrucciones

gh pr create --base main --head docs/actualizar-instrucciones \
  --title "docs: actualizar instrucciones" \
  --body "Se actualizan los pasos de instalación y uso."
```

Después de la revisión y aprobación, la fusión puede realizarse desde GitHub o con:

```bash
gh pr merge --squash --delete-branch
```

## Política de revisión

- No se deben abrir pull requests sin modificaciones reales ni repetir cambios artificialmente.
- La rama `main` debe mantenerse estable.
- Los cambios en gestión de archivos deben tratar expresamente el riesgo de pérdida de datos.
- En cada PR se debe documentar si se probaron la interfaz gráfica y la compilación para Linux.
- No incluya credenciales, archivos personales, cachés, entornos virtuales o binarios generados.