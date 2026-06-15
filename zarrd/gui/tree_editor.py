from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QAction, QStandardItem
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

import zarr

from zarrd import ops
from zarrd.core import node_info
from zarrd.gui.dialogs import NewArrayDialog
from zarrd.gui.tree_model import KIND_ROLE, PATH_ROLE, build_model


class TreeEditorTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store_path: str | None = None
        self._writable = False
        self._sel_path = "/"
        self._sel_kind = "group"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._toolbar = QToolBar()
        self._build_actions()
        layout.addWidget(self._toolbar)

        self._banner = QLabel("")
        self._banner.setStyleSheet("color: #92400e; padding: 4px;")
        self._banner.setVisible(False)
        layout.addWidget(self._banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._tree = QTreeView()
        self._tree.setUniformRowHeights(True)
        self._tree.clicked.connect(self._on_clicked)
        splitter.addWidget(self._tree)
        splitter.addWidget(self._build_properties())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])
        layout.addWidget(splitter)
        self._update_enabled()

    def _build_actions(self) -> None:
        self._act_add_group = QAction("Add group", self)
        self._act_add_group.triggered.connect(self._add_group)
        self._act_add_array = QAction("Add array", self)
        self._act_add_array.triggered.connect(self._add_array)
        self._act_rename = QAction("Rename", self)
        self._act_rename.triggered.connect(self._rename)
        self._act_delete = QAction("Delete", self)
        self._act_delete.triggered.connect(self._delete)
        self._act_refresh = QAction("Refresh", self)
        self._act_refresh.triggered.connect(self.refresh)
        for a in (
            self._act_add_group,
            self._act_add_array,
            self._act_rename,
            self._act_delete,
        ):
            self._toolbar.addAction(a)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._act_refresh)

    def _build_properties(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(6, 6, 6, 6)

        self._node_label = QLabel("No node selected")
        self._node_label.setStyleSheet("font-weight: 600;")
        v.addWidget(self._node_label)

        v.addWidget(QLabel("Metadata"))
        self._meta = QTableWidget(0, 2)
        self._meta.setHorizontalHeaderLabels(["Property", "Value"])
        self._meta.verticalHeader().setVisible(False)
        self._meta.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._meta.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._meta.setMaximumHeight(220)
        v.addWidget(self._meta)

        v.addWidget(QLabel("Attributes (JSON)"))
        self._attrs = QPlainTextEdit()
        self._attrs.setPlaceholderText("{}")
        v.addWidget(self._attrs, 1)

        row = QHBoxLayout()
        self._attr_status = QLabel("")
        self._merge_btn = QPushButton("Merge")
        self._merge_btn.clicked.connect(lambda: self._save_attrs(replace=False))
        self._replace_btn = QPushButton("Replace")
        self._replace_btn.clicked.connect(lambda: self._save_attrs(replace=True))
        row.addWidget(self._attr_status, 1)
        row.addWidget(self._merge_btn)
        row.addWidget(self._replace_btn)
        v.addLayout(row)
        return panel

    def set_store(self, store_path: str | None, writable: bool) -> None:
        self._store_path = store_path
        self._writable = writable
        self.refresh()

    def refresh(self) -> None:
        self._meta.setRowCount(0)
        self._attrs.setPlainText("")
        self._attr_status.setText("")
        self._node_label.setText("No node selected")
        if self._store_path is None:
            self._tree.setModel(None)
            self._banner.setVisible(False)
            self._update_enabled()
            return
        model, _ = build_model(self._store_path)
        self._tree.setModel(model)
        self._tree.expandToDepth(2)
        self._restore_selection(model.invisibleRootItem())
        if not self._writable:
            self._banner.setText(
                "Store opened read-only. Use File > Open (writable) to edit."
            )
            self._banner.setVisible(True)
        else:
            self._banner.setVisible(False)
        self._update_enabled()

    def _restore_selection(self, root: QStandardItem) -> None:
        target = self._sel_path
        stack = [root.child(i) for i in range(root.rowCount())]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            if item.data(PATH_ROLE) == target:
                self._tree.setCurrentIndex(item.index())
                self._show_node(target, str(item.data(KIND_ROLE)))
                return
            stack.extend(item.child(i) for i in range(item.rowCount()))

    def _update_enabled(self) -> None:
        on = self._store_path is not None and self._writable
        for a in (
            self._act_add_group,
            self._act_add_array,
            self._act_rename,
            self._act_delete,
        ):
            a.setEnabled(on)
        self._merge_btn.setEnabled(on)
        self._replace_btn.setEnabled(on)
        self._attrs.setReadOnly(not on)

    def _on_clicked(self, index: QModelIndex) -> None:
        path = index.data(PATH_ROLE)
        kind = index.data(KIND_ROLE)
        if path is None:
            return
        self._show_node(str(path), str(kind))

    def _show_node(self, path: str, kind: str) -> None:
        self._sel_path = path
        self._sel_kind = kind
        if self._store_path is None:
            return
        full = self._full(path)
        node = zarr.open(store=full, mode="r")
        info = node_info(node, path)
        self._node_label.setText(f"{path}   ({info.kind}, zarr v{info.zarr_format})")
        self._fill_meta(info)
        self._attrs.setPlainText(json.dumps(info.attrs, indent=2, default=str))
        self._attr_status.setText("")

    def _fill_meta(self, info: Any) -> None:
        rows: list[tuple[str, str]] = [
            ("path", info.path),
            ("kind", info.kind),
            ("zarr_format", str(info.zarr_format)),
        ]
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
        if info.group is not None:
            rows.append(("members", str(info.group.n_members)))
        self._meta.setRowCount(len(rows))
        for i, (k, val) in enumerate(rows):
            ki = QTableWidgetItem(k)
            ki.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._meta.setItem(i, 0, ki)
            self._meta.setItem(i, 1, QTableWidgetItem(str(val)))

    def _full(self, path: str) -> str:
        assert self._store_path is not None
        key = path.strip("/")
        return self._store_path if not key else self._store_path.rstrip("/") + "/" + key

    def _parent_path(self) -> str:
        if self._sel_kind == "group":
            return self._sel_path
        if self._sel_path in ("", "/"):
            return "/"
        parent = self._sel_path.rsplit("/", 1)[0]
        return parent or "/"

    def _guard(self) -> bool:
        if self._store_path is None or not self._writable:
            QMessageBox.information(self, "zarrd", "Open a store writable to edit")
            return False
        return True

    def _add_group(self) -> None:
        if not self._guard():
            return
        name, ok = QInputDialog.getText(self, "Add group", "Group name:")
        if not ok or not name.strip():
            return
        self._run(lambda: ops.add_group(self._store_path or "", self._parent_path(), name))

    def _add_array(self) -> None:
        if not self._guard():
            return
        dlg = NewArrayDialog(self)
        if dlg.exec() != NewArrayDialog.DialogCode.Accepted:
            return
        v = dlg.values()

        def do() -> str:
            return ops.add_array(
                self._store_path or "",
                self._parent_path(),
                str(v["name"]),
                tuple(v["shape"]),  # type: ignore[arg-type]
                tuple(v["chunks"]) or None,  # type: ignore[arg-type]
                str(v["dtype"]),
                str(v["fill"]),
                str(v["init"]),
            )

        self._run(do)

    def _rename(self) -> None:
        if not self._guard() or self._sel_path in ("", "/"):
            QMessageBox.information(self, "zarrd", "Select a child node to rename")
            return
        current = self._sel_path.rsplit("/", 1)[-1]
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=current)
        if not ok or not name.strip():
            return
        self._run(lambda: ops.rename_node(self._store_path or "", self._sel_path, name))

    def _delete(self) -> None:
        if not self._guard() or self._sel_path in ("", "/"):
            QMessageBox.information(self, "zarrd", "Select a child node to delete")
            return
        confirm = QMessageBox.question(
            self, "Delete node", f"Delete {self._sel_path}? Removes data on disk."
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        def do() -> str:
            ops.delete_node(self._store_path or "", self._sel_path)
            return "/"

        self._sel_path = self._parent_path()
        self._run(do)

    def _save_attrs(self, replace: bool) -> None:
        if not self._guard():
            return
        text = self._attrs.toPlainText().strip() or "{}"
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            self._attr_status.setText(f"invalid JSON: {exc.msg}")
            return
        if not isinstance(parsed, dict):
            self._attr_status.setText("attributes must be a JSON object")
            return
        try:
            ops.set_attributes(
                self._store_path or "", self._sel_path, parsed, replace=replace
            )
        except Exception as exc:  # noqa: BLE001
            self._attr_status.setText(str(exc))
            return
        self._attr_status.setText("replaced" if replace else "merged")

    def _run(self, action: Any) -> None:
        try:
            new_path = action()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Operation failed", str(exc))
            return
        if isinstance(new_path, str) and new_path:
            self._sel_path = new_path
        self.refresh()
