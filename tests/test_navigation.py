"""Pruebas básicas de navegación sin inicializar la interfaz Qt."""
import ast
import os
import tempfile
from pathlib import Path

src = (Path(__file__).resolve().parents[1] / "MarkView.py").read_text(encoding="utf-8")
module = ast.parse(src)
window = next(x for x in module.body if isinstance(x, ast.ClassDef) and x.name == "MarkdownWindow")
method_names = {"change_workspace", "_refresh_nav_buttons", "_navigate_history",
                "go_back", "go_forward", "go_up", "go_home", "go_root",
                "focus_location_bar", "go_to_path_bar", "tree_double_click"}
methods = [x for x in window.body if isinstance(x, ast.FunctionDef) and x.name in method_names]
assert len(methods) == len(method_names)
module = ast.fix_missing_locations(ast.Module(body=[
    ast.ClassDef(name="Navigation", bases=[], keywords=[], body=methods, decorator_list=[])
], type_ignores=[]))

class FakeButton:
    def setEnabled(self, enabled): self.enabled = enabled
class FakeModel:
    def setRootPath(self, path): self.current = path; return path
    def filePath(self, index): return str(index)
class FakeTree:
    def setRootIndex(self, index): self.root = index
    def setCurrentIndex(self, index): self.current = index
    def clearSelection(self): pass
class FakeLine:
    def setText(self, v): self.value = v
    def text(self): return self.value
    def setToolTip(self, v): pass
    def setFocus(self): pass
    def selectAll(self): pass
class FakeTabs:
    def setCurrentIndex(self, v): self.active = v
class FakeSettings:
    def setValue(self, key, v): pass
class FakeStatus:
    def showMessage(self, *args): pass
class FakeMsg:
    @staticmethod
    def warning(*args): raise AssertionError("Unexpected QMessageBox " + str(args))

namespace = {"Path": Path, "os": os, "QMessageBox": FakeMsg,
             "QModelIndex": lambda: None,
             "is_markdown": lambda p: p.suffix == ".md"}
exec(compile(module, "test_navigation_ast", "exec"), namespace)
Navigation = namespace["Navigation"]
obj = Navigation()
obj.workspace = Path.home()
obj._folder_history = []
obj._folder_position = -1
obj.fsmodel = FakeModel()
obj.tree = FakeTree()
obj.folder_path = FakeLine()
obj.side_tabs = FakeTabs()
obj.settings_store = FakeSettings()
obj.back_btn = FakeButton()
obj.forward_btn = FakeButton()
obj.up_btn = FakeButton()
obj.home_btn = FakeButton()
obj.root_btn = FakeButton()
obj.statusBar = lambda: FakeStatus()
obj.opened = []
obj.open_file = lambda p: obj.opened.append(p)

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    fav = base / "fav"; fav.mkdir()
    child = fav / "child"; child.mkdir()
    note = child / "test.md"; note.write_text("# hello")
    assert obj.change_workspace(base)
    assert obj.change_workspace(fav)
    assert obj.workspace == fav and obj.back_btn.enabled
    obj.go_up()
    assert obj.workspace == base and obj._folder_history == [base, fav, base]
    obj.go_back()
    assert obj.workspace == fav
    obj.go_forward()
    assert obj.workspace == base
    obj.tree_double_click(child)
    assert obj.workspace == child
    obj.folder_path.setText(str(note)); obj.go_to_path_bar()
    assert obj.opened == [note]
    obj.go_root()
    assert obj.workspace == Path("/") and not obj.root_btn.enabled and not obj.up_btn.enabled
    obj.go_home()
    assert obj.workspace == Path.home()
    obj.folder_path.setText(str(fav)); obj.go_to_path_bar()
    assert obj.workspace == fav
    obj.folder_path.setText("child"); obj.go_to_path_bar()
    assert obj.workspace == child
    obj.go_back(); assert obj.workspace == fav
    obj.change_workspace(base)
    assert not obj.forward_btn.enabled

print("PASS: favoritos, arriba, atrás, adelante, raíz, inicio, barra, doble clic e historial")
