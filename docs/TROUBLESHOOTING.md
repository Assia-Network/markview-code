# Solución de problemas

## El ejecutable no inicia

Ejecute la aplicación desde una terminal para ver el error:

```bash
./dist/MarkView/MarkView
```

Si aparece `FileNotFoundError: ... latex2mathml/unimathsymbols.txt`, el empaquetado no incluyó los datos de `latex2mathml`. Si aparece `No module named 'pymdownx'`, faltan las extensiones cargadas dinámicamente. Compile usando el script del proyecto:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt pyinstaller
bash scripts/build-linux.sh
```

## El explorador queda dentro de una carpeta favorita

Utilice `Alt+↑` para subir un nivel, `Alt+←` para retroceder, `Alt+Inicio` para volver a su carpeta personal o el botón de raíz `/`. También puede pulsar `Ctrl+L`, escribir la ruta y confirmar con Enter. La carpeta favorita permanecerá anclada.

## El icono personalizado no se muestra en Ubuntu

Los archivos WEBP pueden convertirse a PNG con ImageMagick 6:

```bash
convert markview.webp -resize 256x256 -background none -gravity center -extent 256x256 markview.png
mkdir -p ~/.local/share/icons/hicolor/256x256/apps
cp markview.png ~/.local/share/icons/hicolor/256x256/apps/markview.png
```

En el archivo `~/.local/share/applications/markview.desktop`, configure `Icon=markview`. El icono interno de la ventana requiere configuración adicional en PySide6.

## Diferencias entre la ejecución por Python y el ejecutable

Si el programa funciona con `python MarkView.py` pero no desde `dist/MarkView/MarkView`, revise los recursos recogidos por PyInstaller. No es necesario volver a instalar todas las dependencias en el sistema: el paquete `--onedir` debe conservar la carpeta `_internal`.

## Diagnóstico de fallos gráficos

Puede probar una ejecución sin aceleración gráfica de Chromium:

```bash
QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu" python MarkView.py
```

Utilícela como prueba de diagnóstico, no como ajuste obligatorio.
