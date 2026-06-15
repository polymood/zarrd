from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from zarr import Array

MAX_VIEW = 4096

Index = QModelIndex | QPersistentModelIndex


class ArrayTableModel(QAbstractTableModel):
    def __init__(self, arr: Array[Any], editable: bool = False) -> None:
        super().__init__()
        self._arr = arr
        self._editable = editable
        self._prefix: tuple[int, ...] = tuple(0 for _ in range(max(arr.ndim - 2, 0)))
        self._block: np.ndarray[Any, Any] = np.empty((0, 0))
        self._row_off = 0
        self._col_off = 0
        self._refresh()

    def set_prefix(self, prefix: tuple[int, ...]) -> None:
        self.beginResetModel()
        self._prefix = prefix
        self._refresh()
        self.endResetModel()

    def _refresh(self) -> None:
        arr = self._arr
        if arr.ndim == 0:
            self._n_rows, self._n_cols = 1, 1
            self._block = np.asarray(arr[...]).reshape(1, 1)
        elif arr.ndim == 1:
            self._n_rows = int(arr.shape[0])
            self._n_cols = 1
            self._load_window(0, 0)
        else:
            self._n_rows = int(arr.shape[-2])
            self._n_cols = int(arr.shape[-1])
            self._load_window(0, 0)

    def _load_window(self, row_off: int, col_off: int) -> None:
        arr = self._arr
        self._row_off = row_off
        self._col_off = col_off
        if arr.ndim == 0:
            self._block = np.asarray(arr[...]).reshape(1, 1)
            return
        r0 = row_off
        r1 = min(row_off + MAX_VIEW, self._n_rows)
        if arr.ndim == 1:
            self._block = np.asarray(arr[r0:r1]).reshape(-1, 1)
            return
        c0 = col_off
        c1 = min(col_off + MAX_VIEW, self._n_cols)
        sel: tuple[Any, ...] = self._prefix + (slice(r0, r1), slice(c0, c1))
        self._block = np.asarray(arr[sel])

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return min(self._n_rows, MAX_VIEW)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return min(self._n_cols, MAX_VIEW)

    def data(self, index: Index, role: int = int(Qt.ItemDataRole.DisplayRole)) -> Any:
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            try:
                value = self._block[index.row(), index.column()]
            except IndexError:
                return None
            return str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(section)
        return str(section)

    def flags(self, index: Index) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._editable:
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def setData(
        self, index: Index, value: Any, role: int = int(Qt.ItemDataRole.EditRole)
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or not self._editable:
            return False
        arr = self._arr
        try:
            cast = np.array(value, dtype=arr.dtype).reshape(())
        except (ValueError, TypeError):
            return False
        r = index.row()
        c = index.column()
        if arr.ndim == 0:
            arr[...] = cast
        elif arr.ndim == 1:
            arr[r] = cast
        else:
            sel = self._prefix + (r, c)
            arr[sel] = cast
        self._block[r, c] = cast
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
        return True


class ArrayView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._arr: Array[Any] | None = None
        self._spins: list[QSpinBox] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._axis_bar = QWidget()
        self._axis_layout = QHBoxLayout(self._axis_bar)
        self._axis_layout.setContentsMargins(2, 2, 2, 2)
        self._axis_layout.addStretch(1)
        layout.addWidget(self._axis_bar)

        self._table = QTableView()
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        self._info = QLabel("")
        self._info.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._info)

    def set_array(self, arr: Array[Any], editable: bool) -> None:
        self._arr = arr
        self._clear_axes()
        model = ArrayTableModel(arr, editable=editable)
        self._table.setModel(model)
        if arr.ndim > 2:
            for axis in range(arr.ndim - 2):
                self._add_axis_spin(axis, int(arr.shape[axis]))
        shown = f"{min(arr.shape[-2] if arr.ndim >= 2 else (arr.shape[0] if arr.ndim == 1 else 1), MAX_VIEW)}"
        note = "" if max(arr.shape or (1,)) <= MAX_VIEW else f" (showing first {MAX_VIEW} per axis)"
        self._info.setText(
            f"dtype={arr.dtype}  shape={tuple(arr.shape)}  "
            f"{'editable' if editable else 'read-only'}{note}"
        )

    def _clear_axes(self) -> None:
        for spin in self._spins:
            spin.deleteLater()
        self._spins = []
        while self._axis_layout.count() > 1:
            item = self._axis_layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_axis_spin(self, axis: int, size: int) -> None:
        label = QLabel(f"axis {axis}:")
        spin = QSpinBox()
        spin.setRange(0, max(size - 1, 0))
        spin.valueChanged.connect(self._on_axis_changed)
        idx = self._axis_layout.count() - 1
        self._axis_layout.insertWidget(idx, label)
        self._axis_layout.insertWidget(idx + 1, spin)
        self._spins.append(spin)

    def _on_axis_changed(self) -> None:
        model = self._table.model()
        if isinstance(model, ArrayTableModel):
            model.set_prefix(tuple(s.value() for s in self._spins))
