from __future__ import annotations

import json
from typing import Any, Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import zarr
from zarr import Array, Group

from zarrd.core import node_info
from zarrd.gui.array_table import ArrayView


class DetailPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store_path: str | None = None
        self._node_path: str | None = None
        self._writable = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._array_view = ArrayView()
        self._meta_table = QTableWidget(0, 2)
        self._meta_table.setHorizontalHeaderLabels(["Property", "Value"])
        self._meta_table.verticalHeader().setVisible(False)
        self._meta_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._meta_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self._attrs_widget = QWidget()
        attrs_layout = QVBoxLayout(self._attrs_widget)
        attrs_layout.setContentsMargins(4, 4, 4, 4)
        self._attrs_edit = QPlainTextEdit()
        self._attrs_edit.setPlaceholderText("{}")
        attrs_layout.addWidget(self._attrs_edit, 1)
        btn_row = QHBoxLayout()
        self._attrs_status = QLabel("")
        self._save_attrs_btn = QPushButton("Save attributes")
        self._save_attrs_btn.clicked.connect(self._save_attrs)
        btn_row.addWidget(self._attrs_status, 1)
        btn_row.addWidget(self._save_attrs_btn)
        attrs_layout.addLayout(btn_row)

        self._tabs.addTab(self._array_view, "Data")
        self._tabs.addTab(self._meta_table, "Metadata")
        self._tabs.addTab(self._attrs_widget, "Attributes")

    def clear(self) -> None:
        self._store_path = None
        self._node_path = None
        self._meta_table.setRowCount(0)
        self._attrs_edit.setPlainText("")
        self._attrs_status.setText("")

    def show_node(self, store_path: str, node_path: str, writable: bool) -> None:
        self._store_path = store_path
        self._node_path = node_path
        self._writable = writable
        mode: Literal["r", "r+"] = "r+" if writable else "r"
        node = self._open(node_path, mode)
        info = node_info(node, node_path)

        self._fill_metadata(info)
        self._attrs_edit.setReadOnly(not writable)
        self._save_attrs_btn.setEnabled(writable)
        self._attrs_edit.setPlainText(json.dumps(info.attrs, indent=2, default=str))
        self._attrs_status.setText("")

        if isinstance(node, Array):
            self._tabs.setTabEnabled(0, True)
            self._array_view.set_array(node, editable=writable)
            self._tabs.setCurrentIndex(0)
        else:
            self._tabs.setTabEnabled(0, False)
            if self._tabs.currentIndex() == 0:
                self._tabs.setCurrentIndex(1)

    def _open(
        self, node_path: str, mode: Literal["r", "r+"]
    ) -> Array[Any] | Group:
        assert self._store_path is not None
        full = self._store_path
        if node_path not in ("", "/"):
            full = self._store_path.rstrip("/") + "/" + node_path.lstrip("/")
        return zarr.open(store=full, mode=mode)

    def _fill_metadata(self, info: Any) -> None:
        rows: list[tuple[str, str]] = [("path", info.path), ("kind", info.kind)]
        rows.append(("zarr_format", str(info.zarr_format)))
        if info.array is not None:
            a = info.array
            rows += [
                ("shape", str(a.shape)),
                ("chunks", str(a.chunks)),
                ("dtype", a.dtype),
                ("order", a.order),
                ("fill_value", str(a.fill_value)),
                ("compressors", ", ".join(a.compressors) or "none"),
                ("filters", ", ".join(a.filters) or "none"),
                ("nbytes", str(a.nbytes)),
            ]
            if a.dimension_names is not None:
                rows.append(("dimension_names", str(a.dimension_names)))
        if info.group is not None:
            rows.append(("members", str(info.group.n_members)))
        self._meta_table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            key_item = QTableWidgetItem(k)
            key_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._meta_table.setItem(i, 0, key_item)
            self._meta_table.setItem(i, 1, QTableWidgetItem(str(v)))

    def _save_attrs(self) -> None:
        if not self._writable or self._node_path is None:
            return
        text = self._attrs_edit.toPlainText().strip() or "{}"
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            self._attrs_status.setText(f"invalid JSON: {exc.msg}")
            return
        if not isinstance(parsed, dict):
            self._attrs_status.setText("attributes must be a JSON object")
            return
        node = self._open(self._node_path, "r+")
        node.update_attributes(parsed)
        self._attrs_status.setText("saved")
