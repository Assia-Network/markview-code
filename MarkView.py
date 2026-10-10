#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKVIEW CODE — lector Markdown con pestañas, explorador y carpetas favoritas.

Instalar dependencias:
    python -m pip install PySide6 markdown pymdown-extensions pygments latex2mathml

Ejecutar:
    python MarkView.py
    python MarkView.py documento.md otra_nota.md

Funciona sin conexión para Markdown, tablas, resaltado y fórmulas LaTeX.
Los diagramas Mermaid se intentan renderizar en línea cuando hay internet;
sin conexión se conserva visible su código original.
"""
from __future__ import annotations

import html
import json
import os
import tempfile
import uuid
import re
import shutil
import sys
from pathlib import Path

try:
    import markdown
    from pygments.formatters import HtmlFormatter
    from PySide6.QtCore import QDir, QModelIndex, QRectF, QSettings, Qt, QTimer, QUrl, Signal
    from PySide6.QtGui import (QColor, QDesktopServices, QIcon, QKeySequence,
                              QPainter, QPainterPath, QPen, QPixmap, QShortcut)
    from PySide6.QtWidgets import (
        QApplication, QColorDialog, QFileDialog, QFileSystemModel,
        QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
        QMenu, QMessageBox, QPushButton, QSplitter,
        QTabWidget, QToolButton, QTreeView, QTreeWidget,
        QTreeWidgetItem, QVBoxLayout, QWidget,
    )
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError as error:
    print('\nNo se encontraron algunas dependencias de MarkView.')
    print('Instálalas con este único comando:\n')
    print('  python -m pip install PySide6 markdown pymdown-extensions pygments latex2mathml\n')
    print(f'Detalle: {error}\n')
    raise SystemExit(1)

try:
    import latex2mathml.converter
    HAS_MATHML = True
except ImportError:
    HAS_MATHML = False

EXTS = {'.md', '.markdown', '.mdown', '.mkd', '.mdx'}
NAME_FILTERS = ['*.md', '*.markdown', '*.mdown', '*.mkd', '*.mdx']
APP_NAME = 'MarkView'  # Mismo QSettings para conservar ajustes de versiones anteriores.
FAVORITE_COLORS = [
    ('Menta', '#55d7b2'), ('Azul', '#68a9ff'), ('Lavanda', '#af96ff'),
    ('Rosa', '#fa8bbb'), ('Coral', '#ff8a75'), ('Ámbar', '#f9be62'),
    ('Lima', '#acd46f'), ('Turquesa', '#54c8d8'),
]
DEFAULT_FAVORITE_COLOR = FAVORITE_COLORS[0][1]


def existing_dir(path: Path) -> Path:
    return path if path.is_dir() else Path.home()


def read_note(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ('utf-8-sig', 'utf-16', 'cp1252'):
        try:
            return raw.decode(encoding)
        except UnicodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() in EXTS


def safe_name(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', text).strip(' .')


def mermaid_block(source: str, language: str, css_class: str, options: dict, md, **kwargs) -> str:
    # Conservar el código original como fallback si el CDN está desconectado.
    return '<div class="diagram"><pre class="mermaid">' + html.escape(source) + '</pre></div>'


def mathml_replace(html_doc: str) -> str:
    if not HAS_MATHML:
        return html_doc
    # arithmatex (generic=True) encapsula las fórmulas en span/div.arithmatex.
    pattern = re.compile(
        r'<(?P<tag>span|div) class="arithmatex">\\(?P<op>\(|\[)'
        r'(?P<math>.*?)\\(?P<cl>\)|\])</(?P=tag)>', re.DOTALL,
    )

    def convert(match: re.Match) -> str:
        if (match['op'], match['cl']) not in {(r'(', r')'), (r'[', r']')}:
            return match.group(0)
        try:
            rendered = latex2mathml.converter.convert(html.unescape(match['math']))
            mode = ' math-display' if match['tag'] == 'div' else ''
            return f'<{match["tag"]} class="math-container{mode}">{rendered}</{match["tag"]}>'
        except Exception:
            return match.group(0)

    return pattern.sub(convert, html_doc)


def toc_flat(nodes: list[dict], level: int = 0) -> list[tuple[str, str, int]]:
    result = []
    for item in nodes:
        label = re.sub(r'<[^>]*>', '', item.get('name', '')).strip()
        result.append((html.unescape(label), item.get('id', ''), int(item.get('level', level + 1))))
        result.extend(toc_flat(item.get('children', []), level + 1))
    return result


THEME = {
    'dark': {
        'app': '#0b0e12', 'panel': '#11161c', 'raised': '#1a222a',
        'text': '#e0e9f0', 'muted': '#8294a2', 'border': '#29323c',
        'hover': '#202c34', 'accent': '#56dfb2', 'code': '#0c1117',
        'article': '#0e1319', 'quote': '#15252a', 'table': '#141c23',
    },
    'light': {
        'app': '#edf1f4', 'panel': '#fafcfd', 'raised': '#e7eef1',
        'text': '#1e2b33', 'muted': '#62737e', 'border': '#d2dce1',
        'hover': '#e1ebee', 'accent': '#087c63', 'code': '#f1f6f7',
        'article': '#ffffff', 'quote': '#eaf7f2', 'table': '#f4f8f8',
    },
}


def app_styles(mode: str) -> str:
    c = THEME[mode]
    return f"""
    QMainWindow, QWidget#Root, QSplitter {{ background: {c['app']}; }}
    QWidget {{ color: {c['text']}; font-family: 'Noto Sans', 'Segoe UI', sans-serif; font-size: 12px; }}
    QWidget#Topbar, QWidget#TabArea, QWidget#Side, QWidget#Searchbar {{ background: {c['panel']}; }}
    QWidget#Topbar {{ border-bottom: 1px solid {c['border']}; }}
    QWidget#Side {{ border-left: 1px solid {c['border']}; }}
    QWidget#Searchbar {{ border-bottom: 1px solid {c['border']}; }}
    QTreeWidget#FavoriteTree {{ background: {c['app']}; border: 1px solid {c['border']};
        border-radius: 9px; padding: 5px; }}
    QTreeWidget#FavoriteTree::item {{ padding: 3px 5px; border-radius: 5px; min-height: 28px; }}
    QTreeWidget#FavoriteTree::item:selected {{ background: {c['raised']}; color: {c['text']}; }}
    QLabel#Brand {{ font-size: 15px; font-weight: 850; letter-spacing: 1px; color: {c['text']}; }}
    QLabel#Edition {{ background: {c['raised']}; color: {c['accent']}; border: 1px solid {c['border']};
        border-radius: 5px; padding: 4px 9px; font: 700 9px 'DejaVu Sans Mono', monospace; }}
    QLabel#SectionTitle {{ color: {c['text']}; font-weight: 700; font-size: 11px; letter-spacing: .7px; }}
    QLabel#CountBadge {{ background: {c['raised']}; border: 1px solid {c['border']}; border-radius: 8px;
        padding: 2px 7px; color: {c['muted']}; font-size: 10px; }}
    QLabel#BrandMark {{ font-weight: 900; font-size: 18px; color: {c['accent']}; }}
    QLabel#Caption {{ font-size: 10px; color: {c['muted']}; font-weight: 600; letter-spacing: 1px; }}
    QLabel#Path {{ color: {c['muted']}; font-size: 11px; }}
    QLineEdit#LocationBar {{ font-family: 'DejaVu Sans Mono', monospace; font-size: 11px;
        color: {c['text']}; padding: 6px 9px; }}
    QLabel#Meta {{ color: {c['muted']}; font-size: 11px; }}
    QPushButton, QToolButton {{ background: transparent; color: {c['text']}; padding: 7px 11px;
        border: 1px solid transparent; border-radius: 7px; font-weight: 600; }}
    QPushButton:hover, QToolButton:hover {{ background: {c['hover']}; border-color: {c['border']}; }}
    QPushButton:pressed, QToolButton:pressed {{ background: {c['raised']}; }}
    QPushButton#Primary {{ background: {c['accent']}; color: {c['app']}; padding: 8px 13px; }}
    QPushButton#Primary:hover {{ background: {c['accent']}; }}
    QPushButton#Subtle {{ background: {c['raised']}; border-color: {c['border']}; }}
    QPushButton#Subtle:hover {{ background: {c['hover']}; border-color: {c['accent']}; }}
    QLineEdit {{ border: 1px solid {c['border']}; border-radius: 7px;
        background: {c['raised']}; padding: 7px 10px; selection-background-color: {c['accent']}; }}
    QLineEdit:focus {{ border-color: {c['accent']}; }}
    QTabWidget::pane {{ border: 0; background: {c['panel']}; }}
    QTabBar {{ background: {c['panel']}; }}
    QTabBar::tab {{ background: {c['panel']}; color: {c['muted']}; padding: 11px 19px;
        min-width: 105px; border-right: 1px solid {c['border']};
        border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ color: {c['text']}; background: {c['raised']}; border-bottom: 2px solid {c['accent']}; }}
    QTabBar::close-button {{ padding: 2px; }}
    QTabBar::tab:hover:!selected {{ background: {c['hover']}; color: {c['text']}; }}
    QTreeView, QTreeWidget {{ background: {c['panel']}; alternate-background-color: {c['panel']};
        border: 0; outline: none; color: {c['text']}; }}
    QTreeView::item, QTreeWidget::item {{ min-height: 29px; padding: 1px 5px; border: 0; }}
    QTreeView::item:selected, QTreeWidget::item:selected {{ background: {c['raised']}; color: {c['accent']}; }}
    QTreeView::item:hover, QTreeWidget::item:hover {{ background: {c['hover']}; }}
    QMenu {{ background: {c['panel']}; border: 1px solid {c['border']}; padding: 5px; }}
    QMenu::item {{ padding: 7px 27px; border-radius: 5px; }}
    QMenu::item:selected {{ background: {c['hover']}; }}
    QSplitter::handle {{ background: {c['border']}; width: 1px; }}
    QStatusBar {{ background: {c['panel']}; color: {c['muted']}; border-top: 1px solid {c['border']}; }}
    QStatusBar::item {{ border: 0; }}
    QScrollBar:vertical {{ background: {c['panel']}; width: 10px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 35px; }}
    QScrollBar:horizontal {{ background: {c['panel']}; height: 10px; }}
    QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; }}
    """


def document_css(mode: str) -> str:
    c = THEME[mode]
    formatter = HtmlFormatter(style='monokai' if mode == 'dark' else 'friendly', nowrap=False)
    pygments_css = formatter.get_style_defs('.highlight')
    return f"""
    :root {{ color-scheme: {'dark' if mode == 'dark' else 'light'}; }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ background: {c['article']}; margin: 0; color: {c['text']};
        font: 15px/1.82 'Inter', 'Noto Sans', 'Segoe UI', system-ui, sans-serif;
        -webkit-font-smoothing: antialiased; overflow-wrap: anywhere; }}
    .document {{ max-width: 970px; margin: 0 auto; padding: 56px 70px 105px; }}
    .doc-head {{ margin: 0 0 42px; padding-bottom: 22px; border-bottom: 1px solid {c['border']}; }}
    .eyebrow {{ font-size: 11px; letter-spacing: 1.7px; color: {c['accent']}; font-weight: 800; }}
    .doc-filename {{ font-size: 13px; margin-top: 7px; color: {c['muted']}; overflow-wrap: anywhere; }}
    h1,h2,h3,h4,h5,h6 {{ color: {c['text']}; font-weight: 760; line-height: 1.3;
        scroll-margin-top: 25px; overflow-wrap: break-word; }}
    h1 {{ font-size: 2.25em; margin: 0 0 25px; letter-spacing: -.8px; }}
    h2 {{ font-size: 1.72em; margin: 46px 0 19px; padding-bottom: 11px; border-bottom: 1px solid {c['border']}; }}
    h3 {{ font-size: 1.37em; margin: 31px 0 13px; }}
    h4 {{ font-size: 1.12em; margin: 25px 0 11px; }}
    h5,h6 {{ font-size: 1em; margin: 22px 0 10px; }}
    p {{ margin: 0 0 19px; }}
    a {{ color: {c['accent']}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    strong {{ color: {c['text']}; }}
    hr {{ border: 0; border-top: 1px solid {c['border']}; margin: 36px 0; }}
    img {{ max-width: 100%; height: auto; border-radius: 8px; display: block; margin: 24px auto;
        border: 1px solid {c['border']}; }}
    figure {{ margin: 25px 0; text-align: center; }}
    figcaption {{ color: {c['muted']}; font-size: 12px; }}
    blockquote {{ border-left: 3px solid {c['accent']}; background: {c['quote']};
        padding: 17px 22px; border-radius: 0 8px 8px 0; margin: 23px 0; color: {c['muted']}; }}
    blockquote > :last-child {{ margin-bottom: 0; }}
    ul,ol {{ padding-left: 29px; margin: 13px 0 21px; }}
    li {{ margin: 5px 0; padding-left: 3px; }}
    li > ul,li > ol {{ margin: 4px 0; }}
    input[type='checkbox'] {{ accent-color: {c['accent']}; transform: scale(1.1); margin-right: 8px; }}
    code,kbd,pre {{ font-family: 'JetBrains Mono', 'Cascadia Code', 'DejaVu Sans Mono', monospace; }}
    :not(pre)>code {{ font-size: .87em; color: {c['accent']}; background: {c['raised']};
        border: 1px solid {c['border']}; padding: 2px 6px; border-radius: 5px; overflow-wrap: anywhere; }}
    pre {{ font-size: 12.7px; line-height: 1.69; overflow-x: auto; padding: 19px 22px;
        background: {c['code']}; border: 1px solid {c['border']}; border-radius: 9px;
        white-space: pre; tab-size: 4; }}
    .highlight {{ position: relative; margin: 23px 0; border: 1px solid {c['border']}; border-radius: 10px;
        background: {c['code']} !important; overflow: auto; }}
    .code-toolbar {{ display: flex; align-items: center; justify-content: space-between; padding: 7px 14px;
        border-bottom: 1px solid {c['border']}; font: 10px 'DejaVu Sans Mono', monospace;
        color: {c['muted']}; letter-spacing: 1.4px; }}
    .copy-code {{ color: {c['muted']}; background: {c['raised']}; border: 1px solid {c['border']};
        border-radius: 5px; padding: 4px 9px; cursor: pointer; font: 11px inherit; }}
    .copy-code:hover {{ color: {c['accent']}; }}
    .highlight pre {{ margin: 0; border: 0; border-radius: 0; background: transparent !important; }}
    {pygments_css}
    .table-wrap {{ max-width: 100%; overflow-x: auto; margin: 25px 0; border: 1px solid {c['border']}; border-radius: 8px; }}
    table {{ border-collapse: collapse; width: 100%; min-width: 240px; font-size: 13px; line-height: 1.55; }}
    th,td {{ border-bottom: 1px solid {c['border']}; padding: 12px 16px; text-align: left; vertical-align: top; }}
    tr:last-child td {{ border-bottom: 0; }}
    th {{ background: {c['raised']}; font-weight: 700; white-space: nowrap; }}
    tbody tr:nth-child(even) {{ background: {c['table']}; }}
    .admonition {{ border: 1px solid {c['border']}; border-left: 4px solid {c['accent']};
        border-radius: 8px; padding: 16px 20px; margin: 21px 0; background: {c['quote']}; }}
    .admonition-title {{ font-weight: 700; margin-bottom: 8px; }}
    .admonition>:last-child {{ margin-bottom: 0; }}
    .footnote {{ font-size: 13px; color: {c['muted']}; border-top: 1px solid {c['border']}; margin-top: 48px; }}
    .math-container {{ display: inline-block; max-width: 100%; vertical-align: middle; }}
    .math-display {{ display: block; text-align: center; overflow-x: auto; padding: 16px 0; }}
    math {{ font-size: 1.15em; }}
    .diagram {{ border: 1px solid {c['border']}; background: {c['raised']}; border-radius: 9px;
        padding: 14px; margin: 22px 0; overflow-x: auto; text-align: center; }}
    .diagram .mermaid {{ background: transparent; margin: 0; font-size: 12px; text-align: left; border: none; }}
    .diagram svg {{ max-width: 100%; }}
    .toc {{ background: {c['quote']}; border: 1px solid {c['border']}; border-radius: 8px;
        padding: 18px 24px; margin: 22px 0; }}
    .toc ul {{ margin-bottom: 0; }}
    .task-list-item {{ list-style-type: none; }}
    .task-list-item input {{ margin-left: -21px; }}
    ::selection {{ background: {c['accent']}; color: {c['article']}; }}
    ::-webkit-scrollbar {{ height: 10px; width: 10px; }}
    ::-webkit-scrollbar-thumb {{ background: {c['border']}; border-radius: 5px; }}
    ::-webkit-scrollbar-track {{ background: {c['article']}; }}
    @media(max-width:800px){{.document{{padding: 32px 27px 75px;}}h1{{font-size:1.9em;}}}}
    @media print {{ .document {{ max-width:none; padding:0; }} body{{background:white;color:black;}} }}
    """


DOC_JS = """
(() => {
  for (const table of document.querySelectorAll('.document table')) {
    if (table.parentElement.classList.contains('table-wrap')) continue;
    const wrapper = document.createElement('div');
    wrapper.className = 'table-wrap';
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  }
  document.querySelectorAll('.highlight').forEach(el => {
    const pre = el.querySelector('pre');
    if (!pre) return;
    const bar = document.createElement('div'); bar.className = 'code-toolbar';
    const lang = document.createElement('span'); lang.textContent = 'SOURCE CODE';
    const button = document.createElement('button'); button.className = 'copy-code';
    button.textContent = 'Copiar'; button.type = 'button';
    button.addEventListener('click', async () => {
      const value = pre.innerText;
      try { await navigator.clipboard.writeText(value); }
      catch (e) {
        const area = document.createElement('textarea'); area.value = value;
        document.body.appendChild(area); area.select(); document.execCommand('copy'); area.remove();
      }
      button.textContent = 'Copiado ✓'; setTimeout(() => button.textContent = 'Copiar', 1500);
    });
    bar.append(lang, button); el.prepend(bar);
  });
  document.querySelectorAll('a[href^="http"]').forEach(a => {
    a.setAttribute('title', 'Abrir en el navegador');
  });
  window.addEventListener('keydown', ev => {
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === '+' || ev.key === '-' || ev.key === '0')) ev.preventDefault();
  });
})();
"""


def render_markdown(path: Path, text: str, mode: str) -> tuple[str, list[tuple[str,str,int]]]:
    extensions = [
        'extra', 'toc', 'sane_lists', 'admonition',
        'pymdownx.superfences', 'pymdownx.highlight', 'pymdownx.tasklist',
        'pymdownx.tilde', 'pymdownx.caret', 'pymdownx.mark',
        'pymdownx.keys', 'pymdownx.magiclink', 'pymdownx.arithmatex',
    ]
    config = {
        'toc': {'permalink': False},
        'pymdownx.highlight': {'use_pygments': True, 'guess_lang': False, 'linenums': False},
        'pymdownx.tasklist': {'custom_checkbox': True, 'clickable_checkbox': False},
        'pymdownx.arithmatex': {'generic': True},
        'pymdownx.superfences': {
            'custom_fences': [
                {'name': 'mermaid', 'class': 'mermaid', 'format': mermaid_block},
            ],
        },
    }
    engine = markdown.Markdown(extensions=extensions, extension_configs=config, output_format='html5')
    body = mathml_replace(engine.convert(text))
    headings = toc_flat(getattr(engine, 'toc_tokens', []))
    label = html.escape(path.name)
    doc_style = document_css(mode)
    # Mermaid es opcional y depende de conexión: el código se ve aun sin red.
    mermaid_loader = '''
    <script type="module">
      try {
        if (document.querySelector('.mermaid')) {
          const module = await import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs');
          const mermaid = module.default;
          mermaid.initialize({startOnLoad: false, securityLevel: 'strict', theme: ''' + (
              "'dark'" if mode == 'dark' else "'default'"
          ) + '''});
          await mermaid.run({querySelector: '.mermaid'});
        }
      } catch (err) { /* Mantener el diagrama como código si no hay conexión */ }
    </script>'''
    doc_html = f'''<!doctype html><html lang="es"><head>
      <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
      <meta name="color-scheme" content="{'dark' if mode == 'dark' else 'light'}">
      <title>{label}</title><style>{doc_style}</style>
      </head><body><main class="document">
      <div class="doc-head"><span class="eyebrow">DOCUMENTO MARKDOWN</span>
      <div class="doc-filename">{label}</div></div>
      {body}
      </main><script>{DOC_JS}</script>{mermaid_loader}</body></html>'''
    return doc_html, headings


def welcome_html(mode: str) -> str:
    c = THEME[mode]
    return f'''<!doctype html><html><head><meta charset="utf-8">
      <style>{document_css(mode)}
      .welcome {{ display:flex; align-items:center; justify-content:center; min-height:87vh; padding:32px; }}
      .welcome-core {{ max-width:610px; text-align:center; }}
      .logo {{ display:inline-flex; padding:12px 22px; border:1px solid {c['border']};
        border-radius:14px; font-size:42px; font-weight:900; color:{c['accent']}; background:{c['raised']}; }}
      .welcome h1 {{ font-size:34px; margin:26px 0 15px; }}
      .lead {{ color:{c['muted']}; margin:0 0 35px; font-size:15px; }}
      .tips {{ display:grid; grid-template-columns:repeat(3,1fr); gap:11px; text-align:left; }}
      .tip {{ padding:18px 14px; border:1px solid {c['border']}; border-radius:11px; background:{c['raised']}; }}
      .tip strong {{ font-size:13px; }} .tip p {{ font-size:12px; color:{c['muted']}; margin:8px 0 0; line-height:1.5; }}
      kbd {{ background:{c['panel']}; border:1px solid {c['border']}; padding:4px 8px; border-radius:5px; }}
      </style></head><body><div class="welcome"><div class="welcome-core">
      <div class="logo">M<span style="color:{c['text']}">/</span></div>
      <h1>Markdown para quienes construyen.</h1>
      <p class="lead">Abre documentos, explora tus carpetas y cambia entre archivos en pestañas.
      Estilo IDE, código destacado, pestañas y rutas favoritas a un clic.</p>
      <div class="tips"><div class="tip"><strong><kbd>Ctrl+O</kbd></strong>
        <p>Abre uno o varios archivos Markdown.</p></div>
        <div class="tip"><strong><kbd>Ctrl+Shift+O</kbd></strong>
        <p>Elige una carpeta en el panel derecho.</p></div>
        <div class="tip"><strong><kbd>Ctrl+F</kbd></strong>
        <p>Busca palabras dentro del documento.</p></div></div>
      <p style="margin-top:32px;color:{c['muted']};font-size:12px">Clic derecho en una carpeta → Anclar en favoritas · Arrastra carpetas a Favoritas.</p>
      </div></div></body></html>'''


class LinkPage(QWebEnginePage):
    def __init__(self, parent: QWidget, on_link):
        super().__init__(parent)
        self.on_link = on_link

    def acceptNavigationRequest(self, url: QUrl, kind, is_main_frame: bool) -> bool:
        if is_main_frame and kind == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            if url.hasFragment() and url.path() == self.url().path():
                return True
            self.on_link(url)
            return False
        return True


class Preview(QWebEngineView):
    dropped = Signal(list)

    def __init__(self, filepath: Path | None, owner: QWidget):
        super().__init__(owner)
        self.filepath = filepath
        self.last_stamp: tuple | None = None
        self.source = ''
        self.outline: list[tuple[str,str,int]] = []
        self.pending_scroll = 0
        self.cache_file = Path(owner._tempdir.name) / f'{uuid.uuid4().hex}.html'
        self.setPage(LinkPage(self, owner.follow_link))
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, False)
        self.loadFinished.connect(self.restore_scroll)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        files = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            self.dropped.emit(files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def stamp(self) -> tuple | None:
        try:
            stats = self.filepath.stat()
            return (stats.st_mtime_ns, stats.st_size)
        except (OSError, AttributeError):
            return None

    def load_document(self, mode: str, save_scroll: bool = False):
        if self.filepath is None:
            self.outline = []
            self.setHtml(welcome_html(mode))
            return
        try:
            text = read_note(self.filepath)
            self.source = text
            page_html, self.outline = render_markdown(self.filepath, text, mode)
            self.last_stamp = self.stamp()
            # La URL base del archivo original permite imágenes y enlaces relativos.
            base = QUrl.fromLocalFile(str(self.filepath.resolve()))

            def commit(scroll=0):
                self.pending_scroll = scroll or 0
                # setHtml tiene límite aproximado de 2 MB (URL data:).
                # Un archivo temporal evita el límite en documentos extensos.
                if len(page_html.encode('utf-8')) > 1_300_000:
                    base_element = f'<base href="{html.escape(base.toString(), quote=True)}">'
                    doc = page_html.replace('<head>', f'<head>{base_element}', 1)
                    self.cache_file.write_text(doc, encoding='utf-8')
                    self.load(QUrl.fromLocalFile(str(self.cache_file)))
                else:
                    self.setHtml(page_html, base)

            if save_scroll:
                self.page().runJavaScript('window.scrollY', commit)
            else:
                commit(0)
        except Exception as error:
            msg = html.escape(str(error))
            self.setHtml(f'<body style="font:15px sans-serif;padding:48px;">'
                         f'<h2>No se pudo abrir el documento</h2><p>{msg}</p></body>')
            self.outline = []

    def restore_scroll(self, ok):
        if self.pending_scroll:
            pos = int(self.pending_scroll)
            QTimer.singleShot(60, lambda: self.page().runJavaScript(f'window.scrollTo(0,{pos})'))
            self.pending_scroll = 0


class MoveAwareTree(QTreeView):
    """Mantiene las pestañas sincronizadas tras arrastrar archivos a otra carpeta."""
    pathMoved = Signal(str, str)

    def dropEvent(self, event):
        sources = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        index = self.indexAt(event.position().toPoint())
        model = self.model()
        target = Path(model.filePath(index)) if index.isValid() else Path(model.filePath(self.rootIndex()))
        if target.is_file():
            target = target.parent
        super().dropEvent(event)

        if event.dropAction() != Qt.DropAction.MoveAction:
            return

        def update_paths():
            for old in sources:
                new = target / old.name
                if old != new and not old.exists() and new.exists():
                    self.pathMoved.emit(str(old), str(new))

        QTimer.singleShot(300, update_paths)


def folder_icon(color: str) -> QIcon:
    """Icono de carpeta tintado, dibujado con Qt; no requiere archivos externos."""
    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    base_color = QColor(color)
    if not base_color.isValid():
        base_color = QColor(DEFAULT_FAVORITE_COLOR)
    back = QPainterPath()
    back.addRoundedRect(QRectF(3, 8, 22, 16.5), 3.1, 3.1)
    painter.setPen(QPen(base_color.darker(155), 0.8))
    painter.fillPath(back, base_color.darker(143))
    painter.drawPath(back)
    tab = QPainterPath()
    tab.addRoundedRect(QRectF(3.2, 5, 11, 7.5), 2.2, 2.2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.fillPath(tab, base_color)
    front = QPainterPath()
    front.addRoundedRect(QRectF(3, 10.5, 22, 14), 2.6, 2.6)
    painter.fillPath(front, base_color)
    painter.setPen(QPen(base_color.lighter(128), 0.7))
    painter.drawPath(front)
    painter.end()
    return QIcon(pixmap)


class FavoriteTree(QTreeWidget):
    """Permite anclar carpetas arrastrándolas desde el explorador o el sistema."""
    folderDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('FavoriteTree')
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setDragDropMode(QTreeWidget.DragDropMode.DropOnly)
        self.setDropIndicatorShown(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    @staticmethod
    def dropped_folders(event) -> list[Path]:
        if not event.mimeData().hasUrls():
            return []
        return [Path(url.toLocalFile()) for url in event.mimeData().urls()
                if url.isLocalFile() and Path(url.toLocalFile()).is_dir()]

    def dragEnterEvent(self, event):
        if self.dropped_folders(event):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self.dropped_folders(event):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        folders = self.dropped_folders(event)
        if not folders:
            event.ignore()
            return
        for folder in folders:
            self.folderDropped.emit(str(folder))
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()


class MarkdownWindow(QMainWindow):
    def __init__(self, initial_files: list[Path]):
        super().__init__()
        self.settings_store = QSettings('AssiaFB', APP_NAME)
        self._tempdir = tempfile.TemporaryDirectory(prefix='markview_html_')
        self.mode = self.settings_store.value('theme', 'dark')
        if self.mode not in THEME:
            self.mode = 'dark'
        self.workspace = existing_dir(Path(self.settings_store.value('workspace', str(Path.home()))))
        self.favorites = self.load_favorites()
        # Historial de navegación independiente de las pestañas Markdown.
        self._folder_history: list[Path] = []
        self._folder_position = -1
        self.setWindowTitle('MarkView Code — Markdown Reader')
        self.resize(1420, 880)
        self.setMinimumSize(870, 570)
        self.setAcceptDrops(True)
        self.make_ui()
        self.make_shortcuts()
        self.apply_theme()
        if initial_files:
            for file in initial_files:
                if file.is_dir():
                    self.change_workspace(file)
                elif file.is_file() and is_markdown(file):
                    self.open_file(file)
            if len(initial_files) == 1 and initial_files[0].is_file():
                self.change_workspace(initial_files[0].parent)
        if self.tabs.count() == 0:
            self.show_welcome()
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_external_changes)
        self.check_timer.start(1800)
        self.statusBar().showMessage('Listo para leer  ·  Abre archivos con Ctrl+O')

    def button(self, title: str, method, primary: bool = False, tip: str = '') -> QPushButton:
        btn = QPushButton(title)
        if primary:
            btn.setObjectName('Primary')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(method)
        if tip:
            btn.setToolTip(tip)
        return btn

    def make_ui(self):
        root = QWidget(self)
        root.setObjectName('Root')
        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.setCentralWidget(root)

        top = QWidget()
        top.setObjectName('Topbar')
        top.setFixedHeight(63)
        toolbar = QHBoxLayout(top)
        toolbar.setContentsMargins(19, 9, 15, 9)
        toolbar.setSpacing(7)
        logo = QLabel('M/'); logo.setObjectName('BrandMark')
        brand = QLabel('MARKVIEW'); brand.setObjectName('Brand')
        edition = QLabel('CODE'); edition.setObjectName('Edition')
        toolbar.addWidget(logo)
        toolbar.addSpacing(7)
        toolbar.addWidget(brand)
        toolbar.addSpacing(3)
        toolbar.addWidget(edition)
        toolbar.addSpacing(16)
        toolbar.addWidget(self.button('＋  Abrir .md', self.choose_files, True, 'Abrir documentos Markdown (Ctrl+O)'))
        toolbar.addWidget(self.button('▤  Workspace', self.choose_folder, tip='Elegir carpeta (Ctrl+Shift+O)'))
        toolbar.addStretch()
        toolbar.addWidget(self.button('↻', self.reload_active, tip='Actualizar documento (Ctrl+R)'))
        toolbar.addWidget(self.button('⌕  Buscar', self.activate_search, tip='Buscar en el documento (Ctrl+F)'))
        toolbar.addWidget(self.button('A−', lambda: self.change_zoom(-0.1), tip='Alejar (Ctrl+-)'))
        toolbar.addWidget(self.button('A+', lambda: self.change_zoom(0.1), tip='Acercar (Ctrl++)'))
        self.theme_btn = self.button('☀  Claro', self.switch_theme)
        toolbar.addWidget(self.theme_btn)
        self.sidebar_btn = self.button('◧  Panel', self.toggle_sidebar, tip='Mostrar u ocultar el explorador')
        toolbar.addWidget(self.sidebar_btn)
        main.addWidget(top)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        main.addWidget(self.splitter, 1)

        reading = QWidget()
        reading.setObjectName('TabArea')
        read_layout = QVBoxLayout(reading)
        read_layout.setContentsMargins(0, 0, 0, 0)
        read_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setUsesScrollButtons(True)
        plus = QToolButton()
        plus.setText('＋')
        plus.setToolTip('Abrir un archivo Markdown')
        plus.clicked.connect(self.choose_files)
        self.tabs.setCornerWidget(plus, Qt.Corner.TopRightCorner)
        read_layout.addWidget(self.tabs, 1)

        self.searchbar = QWidget()
        self.searchbar.setObjectName('Searchbar')
        s_layout = QHBoxLayout(self.searchbar)
        s_layout.setContentsMargins(15, 7, 15, 7)
        s_layout.addWidget(QLabel('BUSCAR EN DOCUMENTO'))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Escribe una palabra o frase…')
        self.search_input.textChanged.connect(self.search_active)
        self.search_input.returnPressed.connect(self.search_next)
        s_layout.addWidget(self.search_input, 1)
        s_layout.addWidget(self.button('Anterior ↑', self.search_previous))
        s_layout.addWidget(self.button('Siguiente ↓', self.search_next))
        s_layout.addWidget(self.button('✕', self.hide_search))
        self.searchbar.hide()
        read_layout.addWidget(self.searchbar)
        self.splitter.addWidget(reading)

        self.side = QWidget()
        self.side.setObjectName('Side')
        self.side.setMinimumWidth(245)
        side_layout = QVBoxLayout(self.side)
        side_layout.setContentsMargins(13, 15, 13, 11)
        side_layout.setSpacing(9)
        title = QLabel('WORKSPACE / EXPLORADOR')
        title.setObjectName('Caption')
        side_layout.addWidget(title)
        # Navegación de carpetas tipo explorador/IDE: historial, padres, inicio y raíz.
        navigation = QHBoxLayout()
        navigation.setSpacing(2)
        self.back_btn = self.button('←', self.go_back, tip='Carpeta anterior  ·  Alt+←')
        self.forward_btn = self.button('→', self.go_forward, tip='Carpeta siguiente  ·  Alt+→')
        self.up_btn = self.button('↑', self.go_up, tip='Subir a la carpeta superior  ·  Alt+↑')
        self.home_btn = self.button('⌂', self.go_home, tip='Ir a tu carpeta personal  ·  Alt+Inicio')
        self.root_btn = self.button('/', self.go_root, tip='Ver la raíz del sistema de archivos (/)')
        for nav_btn in (self.back_btn, self.forward_btn, self.up_btn,
                        self.home_btn, self.root_btn):
            nav_btn.setMinimumWidth(34)
            nav_btn.setMaximumWidth(44)
            navigation.addWidget(nav_btn)
        navigation.addStretch()
        side_layout.addLayout(navigation)

        # Ruta editable: permite saltar a cualquier carpeta, incluso fuera del favorito.
        self.folder_path = QLineEdit()
        self.folder_path.setObjectName('LocationBar')
        self.folder_path.setPlaceholderText('Introduce una ruta, como ~/Documentos')
        self.folder_path.setToolTip('Escribe una ruta y presiona Enter para abrirla  ·  Ctrl+L')
        self.folder_path.returnPressed.connect(self.go_to_path_bar)
        side_layout.addWidget(self.folder_path)
        actions = QHBoxLayout()
        actions.setSpacing(0)
        actions.addWidget(self.button('＋ Nota', self.new_note))
        actions.addWidget(self.button('＋ Carpeta', self.new_folder))
        actions.addStretch()
        actions.addWidget(self.button('☆', self.pin_workspace, tip='Anclar la carpeta actual en Favoritas'))
        actions.addWidget(self.button('···', self.open_folder_menu))
        side_layout.addLayout(actions)

        # Acceso rápido persistente a carpetas; se mantiene visible al cambiar de workspace.
        fav_header = QHBoxLayout()
        fav_header.setContentsMargins(3, 6, 3, 0)
        fav_caption = QLabel('★  RUTAS FAVORITAS')
        fav_caption.setObjectName('SectionTitle')
        fav_header.addWidget(fav_caption)
        self.fav_count = QLabel('0')
        self.fav_count.setObjectName('CountBadge')
        fav_header.addWidget(self.fav_count)
        fav_header.addStretch()
        fav_header.addWidget(self.button('＋', self.choose_favorite_folder,
                                         tip='Elegir una carpeta para añadir a Favoritas'))
        side_layout.addLayout(fav_header)
        self.favorites_tree = FavoriteTree(self.side)
        self.favorites_tree.setIconSize(QPixmap(22, 22).size())
        self.favorites_tree.itemClicked.connect(self.favorite_activated)
        self.favorites_tree.customContextMenuRequested.connect(self.show_favorite_menu)
        self.favorites_tree.folderDropped.connect(lambda path: self.pin_favorite(Path(path)))
        side_layout.addWidget(self.favorites_tree)
        self.refresh_favorites()

        file_header = QLabel('NAVEGADOR')
        file_header.setObjectName('Caption')
        side_layout.addWidget(file_header)

        self.side_tabs = QTabWidget()
        self.side_tabs.setDocumentMode(True)
        self.side_tabs.setTabsClosable(False)
        self.fsmodel = QFileSystemModel(self)
        self.fsmodel.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self.fsmodel.setNameFilters(NAME_FILTERS)
        self.fsmodel.setNameFilterDisables(False)
        self.fsmodel.setReadOnly(False)
        self.fsmodel.fileRenamed.connect(self.on_file_renamed)
        self.tree = MoveAwareTree()
        self.tree.pathMoved.connect(lambda old, new: self.relink_tabs(Path(old), Path(new)))
        self.tree.setModel(self.fsmodel)
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setAnimated(True)
        self.tree.setIndentation(17)
        self.tree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree.doubleClicked.connect(self.tree_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_file_menu)
        for index in (1, 2, 3):
            self.tree.hideColumn(index)
        self.side_tabs.addTab(self.tree, 'Archivos')

        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.setIndentation(14)
        self.outline_tree.itemClicked.connect(self.scroll_to_heading)
        self.side_tabs.addTab(self.outline_tree, 'Índice')
        side_layout.addWidget(self.side_tabs, 1)
        footer = QLabel('Doble clic en carpeta → Entrar  ·  ↑ Subir\n'
                        '★ Favoritas  ·  / Raíz del sistema')
        footer.setObjectName('Meta')
        footer.setWordWrap(True)
        side_layout.addWidget(footer)
        self.splitter.addWidget(self.side)
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([1050, 350])
        self.change_workspace(self.workspace)

        status = self.statusBar()
        self.doc_info = QLabel('')
        self.doc_info.setObjectName('Meta')
        status.addPermanentWidget(self.doc_info)

    def make_shortcuts(self):
        shortcuts = [
            ('Ctrl+O', self.choose_files), ('Ctrl+Shift+O', self.choose_folder),
            ('Ctrl+Shift+P', self.pin_workspace),
            ('Alt+Left', self.go_back), ('Alt+Right', self.go_forward),
            ('Alt+Up', self.go_up), ('Alt+Home', self.go_home),
            ('Ctrl+L', self.focus_location_bar),
            ('Ctrl+W', self.close_active), ('Ctrl+F', self.activate_search),
            ('Ctrl+R', self.reload_active), ('F5', self.reload_active),
            ('Ctrl+Tab', lambda: self.next_tab(1)),
            ('Ctrl+Shift+Tab', lambda: self.next_tab(-1)),
            ('Ctrl++', lambda: self.change_zoom(0.1)),
            ('Ctrl+=', lambda: self.change_zoom(0.1)),
            ('Ctrl+-', lambda: self.change_zoom(-0.1)),
            ('Ctrl+0', self.reset_zoom),
            ('Escape', self.hide_search),
        ]
        self._shortcuts = []
        for seq, func in shortcuts:
            s = QShortcut(QKeySequence(seq), self)
            s.activated.connect(func)
            self._shortcuts.append(s)

    def load_favorites(self) -> list[dict]:
        """Lee las carpetas favoritas desde la configuración persistente del usuario."""
        raw = self.settings_store.value('favorite_folders', '[]')
        try:
            entries = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            entries = []
        if not isinstance(entries, list):
            return []
        favorites = []
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
                continue
            path = str(Path(entry['path']).expanduser().resolve())
            if path in seen:
                continue
            seen.add(path)
            color = QColor(str(entry.get('color', DEFAULT_FAVORITE_COLOR)))
            if not color.isValid():
                color = QColor(DEFAULT_FAVORITE_COLOR)
            name = entry.get('name', '')
            favorites.append({'path': path, 'color': color.name(),
                              'name': name if isinstance(name, str) else ''})
        return favorites

    def save_favorites(self):
        self.settings_store.setValue('favorite_folders', json.dumps(self.favorites, ensure_ascii=False))
        self.settings_store.sync()

    def favorite_index(self, directory: Path) -> int:
        path = str(directory.expanduser().resolve())
        for index, entry in enumerate(self.favorites):
            if entry['path'] == path:
                return index
        return -1

    def refresh_favorites(self, selected_path: str | None = None):
        """Actualiza iconos y nombres, incluidos los accesos a carpetas desconectadas."""
        self.favorites_tree.clear()
        self.fav_count.setText(str(len(self.favorites)))
        if not self.favorites:
            placeholder = QTreeWidgetItem(['☆  Ancla aquí tus carpetas'])
            placeholder.setToolTip(0, 'Clic derecho sobre una carpeta o arrástrala aquí')
            placeholder.setForeground(0, QColor(THEME[self.mode]['muted']))
            placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.favorites_tree.addTopLevelItem(placeholder)
            self.favorites_tree.setFixedHeight(63)
            return

        for entry in self.favorites:
            path = Path(entry['path'])
            exists = path.is_dir()
            label = entry['name'].strip() or path.name or str(path)
            if not exists:
                label += '  ·  no disponible'
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            item.setIcon(0, folder_icon(entry['color']))
            item.setToolTip(0, f'{path}\nClic: abrir carpeta  |  Clic derecho: color y opciones')
            if not exists:
                item.setForeground(0, QColor(THEME[self.mode]['muted']))
            self.favorites_tree.addTopLevelItem(item)
            if selected_path == str(path):
                self.favorites_tree.setCurrentItem(item)
        # Caben cuatro favoritos a simple vista; el resto aparece con scroll.
        self.favorites_tree.setFixedHeight(min(202, 22 + 34 * len(self.favorites)))

    def pin_favorite(self, directory: Path):
        directory = directory.expanduser().resolve()
        if directory.is_file():
            directory = directory.parent
        if not directory.is_dir():
            QMessageBox.warning(self, 'No se encontró la carpeta', str(directory))
            return
        idx = self.favorite_index(directory)
        if idx >= 0:
            self.refresh_favorites(str(directory))
            self.statusBar().showMessage('Esta carpeta ya está en tus favoritas', 2700)
            return
        color = FAVORITE_COLORS[len(self.favorites) % len(FAVORITE_COLORS)][1]
        self.favorites.append({'path': str(directory), 'color': color, 'name': ''})
        self.save_favorites()
        self.refresh_favorites(str(directory))
        self.statusBar().showMessage(f'★ Carpeta anclada: {directory.name}', 3000)

    def pin_workspace(self):
        self.pin_favorite(self.workspace)

    def choose_favorite_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Anclar carpeta favorita', str(self.workspace))
        if path:
            self.pin_favorite(Path(path))

    def unpin_favorite(self, directory: Path):
        idx = self.favorite_index(directory)
        if idx < 0:
            return
        entry = self.favorites.pop(idx)
        self.save_favorites()
        self.refresh_favorites()
        self.statusBar().showMessage(f'Favorito desanclado: {Path(entry["path"]).name}', 2800)

    def set_favorite_color(self, directory: Path, color: str):
        idx = self.favorite_index(directory)
        qcolor = QColor(color)
        if idx < 0 or not qcolor.isValid():
            return
        self.favorites[idx]['color'] = qcolor.name()
        self.save_favorites()
        self.refresh_favorites(str(directory))

    def choose_favorite_color(self, directory: Path):
        idx = self.favorite_index(directory)
        if idx < 0:
            return
        start = QColor(self.favorites[idx]['color'])
        color = QColorDialog.getColor(start, self, 'Color de esta carpeta favorita')
        if color.isValid():
            self.set_favorite_color(directory, color.name())

    def rename_favorite_label(self, directory: Path):
        idx = self.favorite_index(directory)
        if idx < 0:
            return
        original = self.favorites[idx]['name'] or directory.name
        value, ok = QInputDialog.getText(self, 'Nombre para el acceso directo',
                                        'Nombre visible (no renombra la carpeta real):',
                                        text=original)
        if ok:
            self.favorites[idx]['name'] = value.strip()
            self.save_favorites()
            self.refresh_favorites(str(directory))

    def favorite_activated(self, item: QTreeWidgetItem, column: int):
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if not value:
            self.choose_favorite_folder()
            return
        directory = Path(value)
        if not directory.is_dir():
            QMessageBox.warning(self, 'Ruta no disponible',
                                f'Esta carpeta ya no está disponible:\n{directory}\n\n'
                                'Puedes quitarla de favoritas con clic derecho.')
            return
        self.change_workspace(directory)
        self.side_tabs.setCurrentIndex(0)
        self.statusBar().showMessage(f'Workspace: {directory}', 2500)

    def show_favorite_menu(self, point):
        item = self.favorites_tree.itemAt(point)
        value = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        menu = QMenu(self)
        if not value:
            menu.addAction('＋ Anclar otra carpeta…', self.choose_favorite_folder)
        else:
            directory = Path(value)
            menu.addAction('▤  Abrir en el explorador',
                           lambda checked=False, p=directory: self.change_workspace(p) if p.is_dir() else
                           QMessageBox.warning(self, 'Carpeta no disponible', str(p)))
            menu.addAction('Abrir con gestor de archivos',
                           lambda checked=False, p=directory: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))))
            menu.addSeparator()
            color_menu = menu.addMenu('●  Cambiar color de carpeta')
            for label, color in FAVORITE_COLORS:
                action = color_menu.addAction(folder_icon(color), label)
                action.triggered.connect(lambda checked=False, p=directory, c=color:
                                         self.set_favorite_color(p, c))
            color_menu.addSeparator()
            color_menu.addAction('Elegir un color personalizado…',
                                 lambda checked=False, p=directory: self.choose_favorite_color(p))
            color_menu.addAction('Restaurar color original',
                                 lambda checked=False, p=directory: self.set_favorite_color(p, DEFAULT_FAVORITE_COLOR))
            menu.addAction('✎  Cambiar nombre visible…',
                           lambda checked=False, p=directory: self.rename_favorite_label(p))
            menu.addSeparator()
            menu.addAction('Copiar ruta', lambda checked=False, p=directory:
                           QApplication.clipboard().setText(str(p)))
            menu.addAction('✕  Desanclar de favoritas',
                           lambda checked=False, p=directory: self.unpin_favorite(p))
        menu.exec(self.favorites_tree.viewport().mapToGlobal(point))

    def relink_favorites(self, old: Path, new: Path):
        """Mantiene accesos rápidos correctos cuando se renombra o mueve un directorio."""
        old, new = old.resolve(), new.resolve()
        changed = False
        for entry in self.favorites:
            path = Path(entry['path'])
            if path == old:
                entry['path'] = str(new)
            elif old in path.parents:
                entry['path'] = str(new / path.relative_to(old))
            else:
                continue
            changed = True
        if changed:
            self.save_favorites()
            self.refresh_favorites()

    def remove_deleted_favorites(self, target: Path):
        target = target.resolve()
        old_count = len(self.favorites)
        self.favorites = [item for item in self.favorites
                          if Path(item['path']) != target and target not in Path(item['path']).parents]
        if len(self.favorites) != old_count:
            self.save_favorites()
            self.refresh_favorites()

    def apply_theme(self):
        QApplication.instance().setStyleSheet(app_styles(self.mode))
        self.theme_btn.setText('☀  Claro' if self.mode == 'dark' else '☾  Oscuro')
        self.refresh_favorites()
        for tab_index in range(self.tabs.count()):
            preview = self.tabs.widget(tab_index)
            if isinstance(preview, Preview):
                preview.load_document(self.mode, save_scroll=True)
        self.populate_outline()

    def switch_theme(self):
        self.mode = 'light' if self.mode == 'dark' else 'dark'
        self.settings_store.setValue('theme', self.mode)
        self.apply_theme()

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Abrir archivos Markdown', str(self.workspace),
            'Markdown (*.md *.markdown *.mdown *.mkd *.mdx);;Todos los archivos (*)',
        )
        for file in files:
            self.open_file(Path(file))

    def choose_folder(self):
        directory = QFileDialog.getExistingDirectory(self, 'Seleccionar carpeta', str(self.workspace))
        if directory:
            self.change_workspace(Path(directory))

    def change_workspace(self, directory: Path, record_history: bool = True) -> bool:
        """Abre una carpeta en el panel derecho y permite regresar después.

        Importante: QFileSystemModel.setRootPath devuelve el índice correcto
        para esa ruta. El QTreeView se limita a ella hasta que el usuario
        utilice Atrás, Arriba, Inicio, Raíz o escriba otra ruta.
        """
        try:
            directory = directory.expanduser().resolve()
        except (OSError, RuntimeError) as error:
            QMessageBox.warning(self, 'Ruta no válida', str(error))
            return False
        if not directory.is_dir():
            QMessageBox.warning(self, 'Carpeta no disponible', f'No existe esta carpeta:\n{directory}')
            return False

        if record_history and (self._folder_position < 0 or
                               self._folder_history[self._folder_position] != directory):
            # Volver y luego entrar en otra carpeta elimina el historial "hacia adelante".
            self._folder_history = self._folder_history[:self._folder_position + 1]
            self._folder_history.append(directory)
            self._folder_position = len(self._folder_history) - 1

        self.workspace = directory
        model_index = self.fsmodel.setRootPath(str(directory))
        self.tree.setRootIndex(model_index)
        # Evita que Nota/Carpeta utilicen una selección antigua de otra ruta.
        self.tree.setCurrentIndex(QModelIndex())
        self.tree.clearSelection()
        self.folder_path.setText(str(directory))
        self.folder_path.setToolTip(str(directory))
        self.side_tabs.setCurrentIndex(0)
        self._refresh_nav_buttons()
        self.settings_store.setValue('workspace', str(directory))
        return True

    def _refresh_nav_buttons(self):
        self.back_btn.setEnabled(self._folder_position > 0)
        self.forward_btn.setEnabled(self._folder_position < len(self._folder_history) - 1)
        self.up_btn.setEnabled(self.workspace.parent != self.workspace)
        self.home_btn.setEnabled(self.workspace != Path.home())
        self.root_btn.setEnabled(self.workspace != Path('/'))

    def _navigate_history(self, direction: int):
        candidate_pos = self._folder_position + direction
        while 0 <= candidate_pos < len(self._folder_history):
            target = self._folder_history[candidate_pos]
            if target.is_dir():
                self._folder_position = candidate_pos
                self.change_workspace(target, record_history=False)
                return
            candidate_pos += direction
        self.statusBar().showMessage('No hay más carpetas disponibles en esa dirección', 3000)
        self._refresh_nav_buttons()

    def go_back(self):
        self._navigate_history(-1)

    def go_forward(self):
        self._navigate_history(1)

    def go_up(self):
        if self.workspace.parent != self.workspace:
            self.change_workspace(self.workspace.parent)

    def go_home(self):
        self.change_workspace(Path.home())

    def go_root(self):
        self.change_workspace(Path('/'))

    def focus_location_bar(self):
        self.folder_path.setFocus()
        self.folder_path.selectAll()

    def go_to_path_bar(self):
        raw = self.folder_path.text().strip()
        if not raw:
            self.folder_path.setText(str(self.workspace))
            return
        expanded = os.path.expandvars(raw)
        selected = Path(expanded).expanduser()
        if not selected.is_absolute():
            selected = self.workspace / selected
        selected = selected.resolve()
        if selected.is_dir():
            self.change_workspace(selected)
        elif selected.is_file() and is_markdown(selected):
            self.open_file(selected)
            self.folder_path.setText(str(self.workspace))
        else:
            QMessageBox.warning(self, 'Ruta no disponible',
                                f'Introduce una carpeta existente o un archivo Markdown:\n{selected}')
            self.folder_path.setText(str(self.workspace))

    def show_welcome(self):
        if self.tabs.count() != 0:
            return
        view = Preview(None, self)
        view.dropped.connect(self.open_dropped)
        self.tabs.addTab(view, 'Inicio')
        view.load_document(self.mode)
        self.doc_info.setText('Bienvenido a MarkView')

    def active_preview(self) -> Preview | None:
        view = self.tabs.currentWidget()
        return view if isinstance(view, Preview) else None

    def find_open_tab(self, path: Path) -> int:
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if isinstance(view, Preview) and view.filepath == path:
                return i
        return -1

    def open_file(self, file: Path):
        file = file.expanduser().resolve()
        if not file.is_file():
            QMessageBox.warning(self, 'No se encontró', f'El archivo no existe:\n{file}')
            return
        if not is_markdown(file):
            QMessageBox.information(self, 'Formato no admitido',
                                    'Selecciona un archivo .md, .markdown, .mdown, .mkd o .mdx.')
            return
        current = self.find_open_tab(file)
        if current >= 0:
            self.tabs.setCurrentIndex(current)
            return
        if self.tabs.count() == 1 and self.tabs.widget(0).filepath is None:
            old_welcome = self.tabs.widget(0)
            self.tabs.removeTab(0)
            old_welcome.deleteLater()
        view = Preview(file, self)
        view.dropped.connect(self.open_dropped)
        index = self.tabs.addTab(view, '◇  ' + file.name)
        self.tabs.setTabToolTip(index, str(file))
        view.load_document(self.mode)
        self.tabs.setCurrentIndex(index)
        self.tab_changed(index)
        self.statusBar().showMessage(f'Abierto: {file}', 4000)

    def close_tab(self, index: int):
        view = self.tabs.widget(index)
        if view is None:
            return
        self.tabs.removeTab(index)
        view.deleteLater()
        if self.tabs.count() == 0:
            self.show_welcome()

    def close_active(self):
        if self.tabs.currentIndex() >= 0:
            self.close_tab(self.tabs.currentIndex())

    def next_tab(self, direction: int):
        if self.tabs.count() > 0:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + direction) % self.tabs.count())

    def tab_changed(self, index: int):
        self.populate_outline()
        view = self.active_preview()
        if view and view.filepath:
            self.doc_info.setText(f'{len(view.source.split()):,} palabras   ·   {view.zoomFactor()*100:.0f}%')
            self.setWindowTitle(f'{view.filepath.name} — MarkView Code')
        else:
            self.doc_info.setText('')
            self.setWindowTitle('MarkView Code — Markdown Reader')
        if self.search_input.text() and view:
            view.findText(self.search_input.text())

    def reload_active(self):
        view = self.active_preview()
        if view:
            view.load_document(self.mode, save_scroll=True)
            self.populate_outline()
            self.statusBar().showMessage('Documento actualizado', 2600)

    def check_external_changes(self):
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if not isinstance(view, Preview) or view.filepath is None:
                continue
            stamp = view.stamp()
            if stamp is not None and stamp != view.last_stamp:
                view.load_document(self.mode, save_scroll=True)
                if view == self.active_preview():
                    self.populate_outline()
                    self.doc_info.setText(f'{len(view.source.split()):,} palabras   ·   {view.zoomFactor()*100:.0f}%')
                self.statusBar().showMessage(f'Cambios externos detectados: {view.filepath.name}', 3000)

    def populate_outline(self):
        self.outline_tree.clear()
        view = self.active_preview()
        if not view:
            return
        stack: list[tuple[int, QTreeWidgetItem]] = []
        for text_label, anchor, level in view.outline:
            label = (text_label or 'Sección').strip()
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.ItemDataRole.UserRole, anchor)
            item.setToolTip(0, label)
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                stack[-1][1].addChild(item)
            else:
                self.outline_tree.addTopLevelItem(item)
            stack.append((level, item))
        self.outline_tree.expandAll()

    def scroll_to_heading(self, item: QTreeWidgetItem):
        anchor = item.data(0, Qt.ItemDataRole.UserRole)
        view = self.active_preview()
        if view and anchor:
            anchor_json = json.dumps(anchor)
            view.page().runJavaScript(f'let h=document.getElementById({anchor_json}); if(h) h.scrollIntoView({{behavior:"smooth"}});')

    def follow_link(self, url: QUrl):
        if url.isLocalFile():
            file = Path(url.toLocalFile()).resolve()
            active = self.active_preview()
            if active and active.filepath == file and url.hasFragment():
                key = json.dumps(url.fragment())
                active.page().runJavaScript(
                    f'const el=document.getElementById({key}); if(el) el.scrollIntoView({{behavior:"smooth"}});'
                )
            elif is_markdown(file):
                self.open_file(file)
            else:
                QDesktopServices.openUrl(url)
        elif url.scheme() in ('http', 'https', 'mailto'):
            QDesktopServices.openUrl(url)
        elif url.scheme() == '':
            # Si es un enlace relativo, el navegador normalmente ya lo resuelve contra baseUrl.
            if url.hasFragment():
                return

    def activate_search(self):
        self.searchbar.show()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def hide_search(self):
        self.searchbar.hide()
        view = self.active_preview()
        if view:
            view.findText('')
            view.setFocus()

    def search_active(self, text: str):
        view = self.active_preview()
        if view:
            view.findText(text)

    def search_next(self):
        view = self.active_preview()
        if view:
            view.findText(self.search_input.text())

    def search_previous(self):
        view = self.active_preview()
        if view:
            view.findText(self.search_input.text(), QWebEnginePage.FindFlag.FindBackward)

    def change_zoom(self, delta: float):
        view = self.active_preview()
        if view:
            zoom = max(0.5, min(2.5, view.zoomFactor() + delta))
            view.setZoomFactor(round(zoom, 2))
            self.tab_changed(self.tabs.currentIndex())

    def reset_zoom(self):
        view = self.active_preview()
        if view:
            view.setZoomFactor(1.0)
            self.tab_changed(self.tabs.currentIndex())

    def toggle_sidebar(self):
        is_visible = not self.side.isVisible()
        self.side.setVisible(is_visible)
        self.sidebar_btn.setText('◧  Panel' if is_visible else '▤  Mostrar panel')

    def tree_double_click(self, index):
        path = Path(self.fsmodel.filePath(index))
        if path.is_dir():
            self.change_workspace(path)
        elif path.is_file() and is_markdown(path):
            self.open_file(path)

    def selected_path(self) -> Path:
        index = self.tree.currentIndex()
        if index.isValid():
            return Path(self.fsmodel.filePath(index))
        return self.workspace

    def selected_folder(self) -> Path:
        selected = self.selected_path()
        return selected if selected.is_dir() else selected.parent

    def new_note(self):
        folder = self.selected_folder()
        name, ok = QInputDialog.getText(self, 'Nueva nota Markdown', 'Nombre del archivo:', text='Nueva nota.md')
        if not ok or not name.strip():
            return
        name = safe_name(name)
        if not name.lower().endswith(tuple(EXTS)):
            name += '.md'
        path = folder / name
        if path.exists():
            QMessageBox.warning(self, 'Ya existe', 'Ya hay un elemento con ese nombre.')
            return
        try:
            path.write_text(f'# {path.stem}\n\n', encoding='utf-8')
            self.open_file(path)
        except OSError as error:
            self.show_error(error)

    def new_folder(self):
        folder = self.selected_folder()
        name, ok = QInputDialog.getText(self, 'Nueva carpeta', 'Nombre de la carpeta:')
        if not ok or not name.strip():
            return
        name = safe_name(name)
        if not name:
            return
        try:
            (folder / name).mkdir()
        except OSError as error:
            self.show_error(error)

    def open_folder_menu(self):
        menu = QMenu(self)
        menu.addAction('Abrir otra carpeta…', self.choose_folder)
        menu.addAction('←  Carpeta anterior', self.go_back)
        menu.addAction('↑  Subir un nivel', self.go_up)
        menu.addAction('⌂  Carpeta personal', self.go_home)
        menu.addAction('/  Raíz del sistema', self.go_root)
        menu.addSeparator()
        menu.addAction('★ Anclar carpeta actual en favoritas', self.pin_workspace)
        menu.addAction('＋ Anclar otra carpeta…', self.choose_favorite_folder)
        menu.addSeparator()
        menu.addAction('Mostrar en gestor de archivos', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.workspace))))
        menu.exec(self.cursor().pos())

    def show_file_menu(self, point):
        index = self.tree.indexAt(point)
        if index.isValid():
            self.tree.setCurrentIndex(index)
            path = Path(self.fsmodel.filePath(index))
        else:
            path = self.workspace
        menu = QMenu(self)
        if path.is_file():
            menu.addAction('Abrir en pestaña', lambda checked=False, p=path: self.open_file(p))
            menu.addSeparator()
        if path.is_dir():
            menu.addAction('↳  Entrar en esta carpeta',
                           lambda checked=False, p=path: self.change_workspace(p))
        menu.addAction('↑  Subir un nivel', self.go_up)
        menu.addAction('/  Volver a la raíz', self.go_root)
        menu.addSeparator()
        folder_for_favorite = path if path.is_dir() else path.parent
        if self.favorite_index(folder_for_favorite) < 0:
            menu.addAction('★  Anclar carpeta en favoritas',
                           lambda checked=False, p=folder_for_favorite: self.pin_favorite(p))
        else:
            menu.addAction('☆  Desanclar carpeta de favoritas',
                           lambda checked=False, p=folder_for_favorite: self.unpin_favorite(p))
            menu.addAction('●  Cambiar color del favorito…',
                           lambda checked=False, p=folder_for_favorite: self.choose_favorite_color(p))
        menu.addSeparator()
        menu.addAction('Nueva nota Markdown', self.new_note)
        menu.addAction('Nueva carpeta', self.new_folder)
        if path != self.workspace and path.exists():
            menu.addSeparator()
            menu.addAction('Renombrar', lambda checked=False, p=path: self.rename_path(p))
            menu.addAction('Mover a otra carpeta…', lambda checked=False, p=path: self.move_path(p))
            if path.is_file():
                menu.addAction('Duplicar archivo', lambda checked=False, p=path: self.duplicate_path(p))
            menu.addAction('Eliminar…', lambda checked=False, p=path: self.delete_path(p))
        menu.addSeparator()
        menu.addAction('Abrir en gestor de archivos', lambda checked=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p if p.is_dir() else p.parent))))
        menu.addAction('Copiar ruta', lambda checked=False, p=path: QApplication.clipboard().setText(str(p)))
        menu.exec(self.tree.viewport().mapToGlobal(point))

    def rename_path(self, path: Path):
        name, ok = QInputDialog.getText(self, 'Renombrar', 'Nuevo nombre:', text=path.name)
        if not ok or not name.strip():
            return
        name = safe_name(name)
        if not name:
            return
        new_path = path.with_name(name)
        if new_path == path:
            return
        if new_path.exists():
            QMessageBox.warning(self, 'El nombre ya existe', 'Usa otro nombre.')
            return
        try:
            path.rename(new_path)
            self.relink_tabs(path, new_path)
        except OSError as error:
            self.show_error(error)

    def move_path(self, path: Path):
        dest = QFileDialog.getExistingDirectory(self, 'Mover a la carpeta…', str(path.parent))
        if not dest:
            return
        target = Path(dest) / path.name
        if target == path:
            return
        if target.exists():
            QMessageBox.warning(self, 'Conflicto de nombre', f'Ya existe:\n{target}')
            return
        if path.is_dir() and (Path(dest).resolve() == path.resolve() or path.resolve() in Path(dest).resolve().parents):
            QMessageBox.warning(self, 'Carpeta inválida', 'No puedes mover una carpeta dentro de sí misma.')
            return
        try:
            shutil.move(str(path), str(target))
            self.relink_tabs(path, target)
            self.statusBar().showMessage(f'Movido a {target.parent}', 4000)
        except OSError as error:
            self.show_error(error)

    def duplicate_path(self, path: Path):
        number = 1
        while True:
            suffix = ' - copia' if number == 1 else f' - copia {number}'
            new_path = path.with_name(path.stem + suffix + path.suffix)
            if not new_path.exists():
                break
            number += 1
        try:
            shutil.copy2(path, new_path)
            self.open_file(new_path)
        except OSError as error:
            self.show_error(error)

    def delete_path(self, path: Path):
        reply = QMessageBox.question(
            self, 'Confirmar eliminación',
            f'¿Eliminar definitivamente «{path.name}»?\n\nEsta acción NO envía el archivo a la papelera.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            self.remove_deleted_favorites(path)
            for i in range(self.tabs.count() - 1, -1, -1):
                view = self.tabs.widget(i)
                if isinstance(view, Preview) and view.filepath and (view.filepath == path or path in view.filepath.parents):
                    self.close_tab(i)
            if self.workspace == path or path in self.workspace.parents:
                self.change_workspace(existing_dir(path.parent))
        except OSError as error:
            self.show_error(error)

    def on_file_renamed(self, directory: str, old_name: str, new_name: str):
        self.relink_tabs(Path(directory) / old_name, Path(directory) / new_name)

    def relink_tabs(self, old: Path, new: Path):
        self.relink_favorites(old, new)
        if self.workspace == old or old in self.workspace.parents:
            self.change_workspace(new / self.workspace.relative_to(old))
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if not isinstance(view, Preview) or view.filepath is None:
                continue
            if view.filepath == old:
                view.filepath = new.resolve()
            elif old in view.filepath.parents:
                view.filepath = (new / view.filepath.relative_to(old)).resolve()
            else:
                continue
            self.tabs.setTabText(index, '◇  ' + view.filepath.name)
            self.tabs.setTabToolTip(index, str(view.filepath))
            view.load_document(self.mode, save_scroll=True)
        self.tab_changed(self.tabs.currentIndex())

    def show_error(self, error: Exception):
        QMessageBox.critical(self, 'No se pudo completar la operación', str(error))

    def open_dropped(self, paths: list[Path]):
        for path in paths:
            if path.is_dir():
                self.change_workspace(path)
            elif path.is_file() and is_markdown(path):
                self.open_file(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        self.open_dropped([Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()

    def closeEvent(self, event):
        self.settings_store.setValue('workspace', str(self.workspace))
        self.settings_store.setValue('theme', self.mode)
        self.save_favorites()
        super().closeEvent(event)
        # El caché se elimina tras cerrar la interfaz.
        QTimer.singleShot(0, self._tempdir.cleanup)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName('AssiaFB')
    app.setStyle('Fusion')
    initial = [Path(argument) for argument in sys.argv[1:] if not argument.startswith('--')]
    window = MarkdownWindow(initial)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()