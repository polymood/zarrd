from __future__ import annotations

import sys
from typing import Literal

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

import zarr

from zarrd import __version__, ops
from zarrd.gui.bulk_panel import BulkTab
from zarrd.gui.dialogs import ConvertDialog, NewStoreDialog
from zarrd.gui.explorer import ExplorerTab
from zarrd.gui.theme import DEFAULT_THEME, THEMES
from zarrd.gui.tree_editor import TreeEditorTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"zarrd {__version__}")
        self.resize(1280, 800)
        self._store_path: str | None = None
        self._writable = False

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._explorer = ExplorerTab()
        self._tree_editor = TreeEditorTab()
        self._bulk = BulkTab()
        self._tabs.addTab(self._explorer, "Explorer")
        self._tabs.addTab(self._tree_editor, "Tree Editor")
        self._tabs.addTab(self._bulk, "Bulk Edit")
        self.setCentralWidget(self._tabs)

        self._build_menu()
        self._store_label = QLabel("No store open")
        self._mode_label = QLabel("")
        self.statusBar().addWidget(self._store_label, 1)
        self.statusBar().addPermanentWidget(self._mode_label)

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        view_menu = menu.addMenu("&View")
        tools_menu = menu.addMenu("&Tools")
        help_menu = menu.addMenu("&Help")
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        def act(text: str, slot, shortcut: str | None = None) -> QAction:  # type: ignore[no-untyped-def]
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            return a

        self._act_new = act("New store...", self._new_store, "Ctrl+N")
        self._act_open = act("Open (read-only)...", lambda: self._open(False), "Ctrl+O")
        self._act_open_rw = act(
            "Open (writable)...", lambda: self._open(True), "Ctrl+Shift+O"
        )
        self._act_duplicate = act(
            "Duplicate && edit...", self._duplicate_edit, "Ctrl+Shift+D"
        )
        self._act_reload = act("Reload", self._reload, "F5")
        self._act_close = act("Close store", self._close_store)
        self._act_quit = act("Quit", self.close, "Ctrl+Q")
        for a in (
            self._act_new,
            self._act_open,
            self._act_open_rw,
            self._act_duplicate,
            self._act_reload,
            self._act_close,
        ):
            file_menu.addAction(a)
        file_menu.addSeparator()
        file_menu.addAction(self._act_quit)

        self._act_convert = act("Convert store...", self._convert)
        self._act_send_bulk = act("Add current store to Bulk Edit", self._send_to_bulk)
        tools_menu.addAction(self._act_convert)
        tools_menu.addAction(self._act_send_bulk)

        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        self._theme_actions: dict[str, QAction] = {}
        for name in ("dark", "light"):
            a = QAction(f"{name.capitalize()} theme", self)
            a.setCheckable(True)
            a.setChecked(name == DEFAULT_THEME)
            a.triggered.connect(lambda _checked=False, n=name: self.apply_theme(n))
            theme_group.addAction(a)
            view_menu.addAction(a)
            self._theme_actions[name] = a

        self._act_about = act("About zarrd", self._about)
        help_menu.addAction(self._act_about)

        for a in (
            self._act_new,
            self._act_open,
            self._act_open_rw,
            self._act_duplicate,
            self._act_reload,
        ):
            toolbar.addAction(a)
        toolbar.addSeparator()
        toolbar.addAction(self._act_convert)

    def open_path(self, path: str, writable: bool) -> None:
        try:
            zarr.open(store=path, mode="r")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._store_path = path
        self._writable = writable
        self._broadcast()
        self._store_label.setText(path)
        self._mode_label.setText("writable" if writable else "read-only")

    def _broadcast(self) -> None:
        self._explorer.set_store(self._store_path, self._writable)
        self._tree_editor.set_store(self._store_path, self._writable)

    def _new_store(self) -> None:
        dlg = NewStoreDialog(self)
        if dlg.exec() != NewStoreDialog.DialogCode.Accepted:
            return
        fmt: Literal[2, 3] = dlg.zarr_format
        try:
            zarr.open_group(store=dlg.path, mode="w", zarr_format=fmt)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Create failed", str(exc))
            return
        self.open_path(dlg.path, writable=True)

    def _open(self, writable: bool) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open zarr store")
        if path:
            self.open_path(path, writable)

    def _duplicate_edit(self) -> None:
        if self._store_path is None:
            QMessageBox.information(self, "zarrd", "open a store first")
            return
        suggested = self._store_path.rstrip("/")
        suggested = (
            suggested[: -len(".zarr")] if suggested.endswith(".zarr") else suggested
        ) + "_edit.zarr"
        dest, _ = QFileDialog.getSaveFileName(self, "Duplicate store as", suggested)
        if not dest:
            return
        try:
            new_path = ops.copy_store(self._store_path, dest, overwrite=False)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Duplicate failed", str(exc))
            return
        self.open_path(new_path, writable=True)
        self.statusBar().showMessage(f"editing copy: {new_path}", 5000)

    def _reload(self) -> None:
        if self._store_path is not None:
            self.open_path(self._store_path, self._writable)

    def _close_store(self) -> None:
        self._store_path = None
        self._writable = False
        self._broadcast()
        self._store_label.setText("No store open")
        self._mode_label.setText("")

    def _convert(self) -> None:
        dlg = ConvertDialog(source=self._store_path or "", parent=self)
        dlg.exec()

    def _send_to_bulk(self) -> None:
        if self._store_path is None:
            QMessageBox.information(self, "zarrd", "open a store first")
            return
        self._bulk.add_store_path(self._store_path)
        self._tabs.setCurrentWidget(self._bulk)

    def apply_theme(self, name: str) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(THEMES.get(name, THEMES[DEFAULT_THEME]))
        action = self._theme_actions.get(name)
        if action is not None and not action.isChecked():
            action.setChecked(True)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About zarrd",
            f"<h3>zarrd {__version__}</h3>"
            "<p>A desktop tool for inspecting, editing, and converting "
            "Zarr v2 and v3 stores.</p>"
            "<p>Explorer, structural tree editor, and bulk operations across "
            "many stores, plus a command line interface for batch conversion.</p>"
            "<p>Built with PySide6 and zarr-python.</p>",
        )


def run(initial: str | None = None) -> int:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    app.setApplicationName("zarrd")
    app.setApplicationVersion(__version__)
    app.setStyleSheet(THEMES[DEFAULT_THEME])
    window = MainWindow()
    if initial:
        window.open_path(initial, writable=False)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
