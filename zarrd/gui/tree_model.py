from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

import zarr
from zarr import Array, Group

PATH_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 1
KIND_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 2


def _make_item(name: str, path: str, kind: str, fmt: int) -> QStandardItem:
    item = QStandardItem(name)
    item.setEditable(False)
    item.setData(path, PATH_ROLE)
    item.setData(kind, KIND_ROLE)
    item.setToolTip(f"{path}  (zarr v{fmt})")
    return item


def _populate(parent_item: QStandardItem, group: Group, path: str) -> None:
    for name, obj in sorted(group.members(), key=lambda kv: kv[0]):
        child_path = (path.rstrip("/") + "/" + name) if path != "/" else "/" + name
        fmt = int(obj.metadata.zarr_format)
        if isinstance(obj, Group):
            item = _make_item(name, child_path, "group", fmt)
            _populate(item, obj, child_path)
        else:
            item = _make_item(name, child_path, "array", fmt)
        parent_item.appendRow(item)


def build_model(store_path: str) -> tuple[QStandardItemModel, str]:
    node = zarr.open(store=store_path, mode="r")
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Hierarchy"])
    fmt = int(node.metadata.zarr_format)
    root_name = store_path.rstrip("/").rsplit("/", 1)[-1] or "/"
    if isinstance(node, Array):
        root = _make_item(root_name, "/", "array", fmt)
        model.appendRow(root)
    else:
        root = _make_item(root_name, "/", "group", fmt)
        _populate(root, node, "/")
        model.appendRow(root)
    return model, root_name
