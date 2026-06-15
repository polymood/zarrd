from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QSplitter, QTreeView, QVBoxLayout, QWidget

from zarrd.gui.detail_view import DetailPanel
from zarrd.gui.tree_model import KIND_ROLE, PATH_ROLE, build_model


class ExplorerTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store_path: str | None = None
        self._writable = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeView()
        self._tree.setHeaderHidden(False)
        self._tree.setUniformRowHeights(True)
        self._tree.clicked.connect(self._on_clicked)
        splitter.addWidget(self._tree)

        self._detail = DetailPanel()
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 820])
        layout.addWidget(splitter)

    def set_store(self, store_path: str | None, writable: bool) -> None:
        self._store_path = store_path
        self._writable = writable
        self.refresh()

    def refresh(self) -> None:
        self._detail.clear()
        if self._store_path is None:
            self._tree.setModel(None)
            return
        model, _ = build_model(self._store_path)
        self._tree.setModel(model)
        self._tree.expandToDepth(1)

    def _on_clicked(self, index: QModelIndex) -> None:
        if self._store_path is None:
            return
        path = index.data(PATH_ROLE)
        if path is None:
            return
        self._detail.show_node(self._store_path, str(path), self._writable)
