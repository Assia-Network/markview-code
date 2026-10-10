# MarkView Code

**MarkView Code** es una aplicación de escritorio desarrollada en Python para leer documentos Markdown con una interfaz inspirada en los entornos de desarrollo. Integra un visor renderizado, pestañas y un explorador de archivos con rutas favoritas persistentes.

La interfaz está diseñada para consultar notas técnicas, documentación de software, manuales y archivos de investigación sin tener que editar el código Markdown ni cambiar constantemente de aplicación.

## 1. Motivación del proyecto

Los documentos Markdown suelen abrirse en editores de texto o visores con opciones limitadas de navegación. MarkView Code se desarrolló para resolver tres necesidades concretas:

1. **Lectura estructurada:** presentar documentos con títulos, tablas, listas, código y ecuaciones en una vista legible.
2. **Navegación en colecciones locales:** pasar entre carpetas y archivos desde un panel lateral, sin abandonar el lector.
3. **Acceso rápido:** conservar carpetas de uso frecuente como favoritas, con etiquetas y colores configurables.

El contenido de los documentos se lee desde el sistema de archivos local. La aplicación no incorpora un asistente de inteligencia artificial ni envía automáticamente los documentos a un servicio de IA.

## 2. Funcionalidades

| Área | Descripción |
|---|---|
| Visualización | Renderizado de archivos `.md`, `.markdown`, `.mdown`, `.mkd` y `.mdx`. |
| Documentos | Pestañas reordenables y cerrables, con apertura simultánea de varios archivos. |
| Markdown | Títulos, enlaces, tablas, listas de tareas, citas, admoniciones y bloques de código resaltados. |
| Matemáticas | Conversión de expresiones LaTeX a MathML mediante `latex2mathml`. |
| Mermaid | Intento de visualización de diagramas desde un módulo remoto; requiere conexión para renderizar. |
| Explorador | Panel derecho con carpetas y archivos, índice de secciones y ruta editable. |
| Navegación | Historial atrás/adelante, carpeta superior, carpeta personal y raíz `/`. |
| Favoritas | Anclar carpetas, asignar colores, editar nombres visibles y conservar la configuración. |
| Archivos | Crear archivos y carpetas, renombrar, mover, duplicar y eliminar desde el explorador. |
| Lectura | Búsqueda, zoom, alternancia entre tema oscuro/claro y actualización ante cambios externos. |

**Advertencia sobre eliminación:** la opción **Eliminar** del explorador borra de forma definitiva, sin enviar los archivos a la papelera.

## 3. Requisitos

- Python 3.10 o superior.
- Ubuntu 24.04 o una distribución Linux con escritorio gráfico; también puede ejecutarse en otros sistemas compatibles con PySide6.
- Dependencias declaradas en `requirements.txt`.
- Conexión a internet **únicamente** para renderizar los diagramas Mermaid desde el CDN; la lectura Markdown estándar es local.

## 4. Instalación desde el código fuente

```bash
# Ubicarse dentro del proyecto
cd markview-code

# Crear y activar un entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar las dependencias
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Abrir MarkView
python MarkView.py
```

Para abrir uno o varios documentos desde la terminal:

```bash
python MarkView.py "/ruta/manual.md" "/ruta/notas.md"
```

## 5. Uso de la interfaz

### 5.1 Apertura de archivos

Seleccione **Abrir .md** o utilice `Ctrl+O`. Los documentos se muestran en pestañas superiores; puede cambiarlas de posición con el ratón o cerrar cada una individualmente.

### 5.2 Explorador de carpetas

Seleccione **Workspace** (`Ctrl+Shift+O`) para abrir una carpeta. A partir de ese momento, su contenido aparece en el panel derecho. Haga doble clic en otra carpeta para entrar; haga doble clic en un archivo Markdown para abrirlo en una pestaña.

La barra de ubicación permite escribir una ruta absoluta (`/home/usuario/Documentos`), una ruta relativa o una ruta abreviada (`~/Documentos`). Pulse `Enter` para navegar hasta ella. También admite rutas de archivos Markdown.

### 5.3 Favoritas

Haga clic derecho sobre una carpeta en el explorador y elija **Anclar carpeta en favoritas**; también puede anclar la carpeta actual desde el botón de estrella. Una carpeta favorita se abre haciendo clic en su entrada del panel **Rutas favoritas**.

En el menú contextual de una carpeta favorita puede asignar un color predefinido, elegir uno personalizado, cambiar el nombre visible o desanclarla. Los favoritos se conservan entre sesiones mediante `QSettings`.

Las carpetas favoritas no restringen la navegación: utilice **Atrás**, **Arriba**, **Inicio**, **Raíz** o la barra de ruta para salir de cualquiera de ellas.

### 5.4 Visualización y búsqueda

Use el panel **Índice** para acceder a los encabezados del documento actual, `Ctrl+F` para buscar palabras y los botones `A+`/`A−` para ajustar el tamaño de visualización. La aplicación comprueba periódicamente si cambió un archivo abierto para actualizar la lectura.

## 6. Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+O` | Abrir archivos Markdown. |
| `Ctrl+Shift+O` | Seleccionar carpeta de trabajo. |
| `Ctrl+Shift+P` | Anclar carpeta actual a favoritas. |
| `Ctrl+L` | Activar la barra de rutas. |
| `Alt+←` | Retroceder en el historial del explorador. |
| `Alt+→` | Avanzar en el historial del explorador. |
| `Alt+↑` | Subir una carpeta. |
| `Alt+Inicio` | Ir a la carpeta personal. |
| `Ctrl+W` | Cerrar la pestaña actual. |
| `Ctrl+Tab` | Ir a la siguiente pestaña. |
| `Ctrl+Shift+Tab` | Ir a la pestaña anterior. |
| `Ctrl+F` | Buscar en el documento activo. |
| `Ctrl+R` o `F5` | Recargar el documento activo. |
| `Ctrl++` o `Ctrl+=` | Aumentar el zoom. |
| `Ctrl+-` | Disminuir el zoom. |
| `Ctrl+0` | Restablecer el zoom. |
| `Esc` | Ocultar la barra de búsqueda. |

Los atajos se han comprobado contra los métodos registrados en `MarkView.py`.

## 7. Compilación para Ubuntu

Para obtener un ejecutable independiente del entorno virtual, instale PyInstaller y ejecute el script de compilación:

```bash
source .venv/bin/activate
python -m pip install pyinstaller
bash scripts/build-linux.sh
./dist/MarkView/MarkView
```

El ejecutable se genera en `dist/MarkView/` (modo `--onedir`). **No copie únicamente el archivo ejecutable:** mantenga también la carpeta `_internal`.

El script incluye explícitamente los recursos de `latex2mathml`, `pymdownx`, `markdown` y `pygments` para prevenir errores relacionados con `unimathsymbols.txt` o módulos no encontrados.

Para instalarlo en el usuario actual:

```bash
mkdir -p "$HOME/.local/opt" "$HOME/.local/share/applications"
cp -a dist/MarkView "$HOME/.local/opt/"
cat > "$HOME/.local/share/applications/markview.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=MarkView Code
Comment=Lector local de documentos Markdown
Exec=$HOME/.local/opt/MarkView/MarkView %f
Icon=markview
Terminal=false
Categories=Development;Office;TextEditor;
MimeType=text/markdown;
StartupNotify=true
EOF
```

El valor `Icon=markview` supone que el usuario ya instaló un icono con ese nombre. Si no existe, sustituya la línea por `Icon=accessories-text-editor`. Si su icono original está en formato WEBP, puede convertirlo a PNG e instalarlo en el tema de iconos local. El icono de la ventana requiere asimismo que el programa lo configure mediante `QIcon`.

## 8. Estructura del repositorio

```text
markview-code/
├── MarkView.py                 Aplicación principal
├── README.md                   Documentación de usuario
├── requirements.txt            Dependencias de Python
├── .gitignore                  Exclusiones para Git
├── CONTRIBUTING.md             Proceso de contribución y pull requests
├── scripts/
│   ├── build-linux.sh          Compilación mediante PyInstaller
│   └── publicar-github.sh      Publicación inicial usando GitHub CLI
└── tests/
    └── test_navigation.py      Comprobación de la navegación sin abrir Qt
```

## 9. Comprobaciones

```bash
python -m py_compile MarkView.py
python tests/test_navigation.py
```

Las comprobaciones incluidas verifican la sintaxis y una selección de operaciones de navegación. **No sustituyen las pruebas gráficas** de la interfaz PySide6 en un escritorio real.

## 10. Desarrollo y contribuciones

Las propuestas de cambio deben utilizar ramas independientes y pull requests dirigidos a `main`. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para el procedimiento de revisión y fusión.

## 11. Alcance y limitaciones

- **Lector, no editor Markdown:** el contenido del documento se presenta renderizado, pero no se edita en este visor.
- La representación de algunos componentes Markdown puede variar respecto de otros motores.
- Mermaid necesita acceso a su CDN para renderizar los diagramas; cuando no está disponible se mantiene visible el contenido del bloque.
- El programa es una aplicación local de escritorio y requiere un entorno gráfico funcional.
- El proyecto no incluye todavía una licencia de redistribución; debe definirse explícitamente antes de promover contribuciones o reutilizaciones externas.