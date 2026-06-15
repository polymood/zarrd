from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from zarrd import ops
from zarrd.ops import EditOp, StoreOpResult
from zarrd.gui.op_dialog import OpDialog


class _BulkWorker(QThread):
    message = Signal(str)
    done = Signal(object)

    def __init__(
        self,
        store_paths: list[str],
        edit_ops: list[EditOp],
        copy_to: str | None,
        overwrite: bool,
    ) -> None:
        super().__init__()
        self._store_paths = store_paths
        self._ops = edit_ops
        self._copy_to = copy_to
        self._overwrite = overwrite
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        results = ops.run_bulk(
            self._store_paths,
            self._ops,
            log=lambda m: self.message.emit(m),
            stop=lambda: self._stop,
            copy_to=self._copy_to,
            overwrite=self._overwrite,
        )
        self.done.emit(results)


class BulkTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: _BulkWorker | None = None
        self._ops: list[EditOp] = []
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        splitter.addWidget(self._build_stores())
        splitter.addWidget(self._build_ops())
        splitter.addWidget(self._build_runner())
        splitter.setSizes([200, 220, 260])
        layout.addWidget(splitter)

    def _build_stores(self) -> QWidget:
        box = QGroupBox("Target stores")
        h = QHBoxLayout(box)
        self._stores = QListWidget()
        self._stores.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        h.addWidget(self._stores, 1)

        col = QVBoxLayout()
        for label, slot in (
            ("Add stores...", self._add_stores),
            ("Add directory...", self._add_directory),
            ("Add glob...", self._add_glob),
            ("Remove selected", self._remove_stores),
            ("Clear", self._clear_stores),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            col.addWidget(btn)
        col.addStretch(1)
        self._store_count = QLabel("0 stores")
        col.addWidget(self._store_count)
        h.addLayout(col)
        return box

    def _build_ops(self) -> QWidget:
        box = QGroupBox("Operation queue (applied in order to every store)")
        h = QHBoxLayout(box)
        self._op_list = QListWidget()
        self._op_list.doubleClicked.connect(lambda: self._edit_op())
        h.addWidget(self._op_list, 1)

        col = QVBoxLayout()
        for label, slot in (
            ("Add...", self._add_op),
            ("Edit...", self._edit_op),
            ("Duplicate", self._duplicate_op),
            ("Remove", self._remove_op),
            ("Move up", lambda: self._move_op(-1)),
            ("Move down", lambda: self._move_op(1)),
            ("Clear", self._clear_ops),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            col.addWidget(btn)
        col.addStretch(1)
        h.addLayout(col)
        return box

    def _build_runner(self) -> QWidget:
        box = QGroupBox("Run")
        v = QVBoxLayout(box)

        out_row = QHBoxLayout()
        self._in_place = QRadioButton("Modify in place")
        self._in_place.setChecked(True)
        self._in_place.toggled.connect(self._sync_output_mode)
        self._to_copies = QRadioButton("Write modified copies to:")
        out_row.addWidget(self._in_place)
        out_row.addWidget(self._to_copies)
        self._out_dir = QLineEdit()
        self._out_dir.setPlaceholderText("output directory")
        self._out_dir.setEnabled(False)
        out_browse = QPushButton("...")
        out_browse.clicked.connect(self._browse_out)
        out_row.addWidget(self._out_dir, 1)
        out_row.addWidget(out_browse)
        self._overwrite = QCheckBox("overwrite")
        out_row.addWidget(self._overwrite)
        v.addLayout(out_row)

        row = QHBoxLayout()
        self._run_btn = QPushButton("Run on all stores")
        self._run_btn.setObjectName("primary")
        self._run_btn.clicked.connect(self._run)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        self._clear_log_btn = QPushButton("Clear log")
        self._clear_log_btn.clicked.connect(lambda: self._log.clear())
        row.addWidget(self._run_btn)
        row.addWidget(self._stop_btn)
        row.addStretch(1)
        row.addWidget(self._clear_log_btn)
        v.addLayout(row)

        self._progress = QProgressBar()
        v.addWidget(self._progress)
        v.addWidget(self._log, 1)
        return box

    def _sync_output_mode(self) -> None:
        copies = self._to_copies.isChecked()
        self._out_dir.setEnabled(copies)

    def _browse_out(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output directory")
        if path:
            self._out_dir.setText(path)
            self._to_copies.setChecked(True)

    def add_store_path(self, path: str) -> None:
        self._append_stores([path])

    def _store_paths(self) -> list[str]:
        return [self._stores.item(i).text() for i in range(self._stores.count())]

    def _append_stores(self, paths: list[str]) -> None:
        existing = set(self._store_paths())
        added = 0
        for p in paths:
            if p and p not in existing:
                self._stores.addItem(QListWidgetItem(p))
                existing.add(p)
                added += 1
        self._store_count.setText(f"{self._stores.count()} stores")
        if added:
            self._log.appendPlainText(f"added {added} store(s)")

    def _add_stores(self) -> None:
        paths = QFileDialog.getExistingDirectoryUrl(self, "Add store directory")
        if paths.isValid():
            self._append_stores(ops.resolve_stores([paths.toLocalFile()]))

    def _add_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Add directory of stores")
        if path:
            resolved = ops.resolve_stores([path])
            if not resolved:
                QMessageBox.information(self, "zarrd", "no stores found in directory")
            self._append_stores(resolved)

    def _add_glob(self) -> None:
        pattern, ok = QInputDialog.getText(
            self, "Add glob", "Glob pattern (e.g. /data/*.zarr):"
        )
        if ok and pattern.strip():
            resolved = ops.resolve_stores([pattern.strip()])
            if not resolved:
                QMessageBox.information(self, "zarrd", "no stores matched")
            self._append_stores(resolved)

    def _remove_stores(self) -> None:
        for item in self._stores.selectedItems():
            self._stores.takeItem(self._stores.row(item))
        self._store_count.setText(f"{self._stores.count()} stores")

    def _clear_stores(self) -> None:
        self._stores.clear()
        self._store_count.setText("0 stores")

    def _refresh_ops(self) -> None:
        self._op_list.clear()
        for i, op in enumerate(self._ops, start=1):
            self._op_list.addItem(QListWidgetItem(f"{i}. {op.describe()}"))

    def _selected_op_row(self) -> int:
        return self._op_list.currentRow()

    def _add_op(self) -> None:
        dlg = OpDialog(parent=self)
        if dlg.exec() == OpDialog.DialogCode.Accepted:
            self._ops.append(dlg.op())
            self._refresh_ops()
            self._op_list.setCurrentRow(len(self._ops) - 1)

    def _edit_op(self) -> None:
        row = self._selected_op_row()
        if row < 0:
            return
        dlg = OpDialog(op=self._ops[row], parent=self)
        if dlg.exec() == OpDialog.DialogCode.Accepted:
            self._ops[row] = dlg.op()
            self._refresh_ops()
            self._op_list.setCurrentRow(row)

    def _duplicate_op(self) -> None:
        row = self._selected_op_row()
        if row < 0:
            return
        import copy

        self._ops.insert(row + 1, copy.deepcopy(self._ops[row]))
        self._refresh_ops()
        self._op_list.setCurrentRow(row + 1)

    def _remove_op(self) -> None:
        row = self._selected_op_row()
        if row < 0:
            return
        del self._ops[row]
        self._refresh_ops()

    def _move_op(self, delta: int) -> None:
        row = self._selected_op_row()
        new = row + delta
        if row < 0 or new < 0 or new >= len(self._ops):
            return
        self._ops[row], self._ops[new] = self._ops[new], self._ops[row]
        self._refresh_ops()
        self._op_list.setCurrentRow(new)

    def _clear_ops(self) -> None:
        self._ops = []
        self._refresh_ops()

    def _run(self) -> None:
        stores = self._store_paths()
        if not stores:
            QMessageBox.information(self, "zarrd", "add at least one store")
            return
        if not self._ops:
            QMessageBox.information(self, "zarrd", "add at least one operation")
            return
        copy_to: str | None = None
        if self._to_copies.isChecked():
            copy_to = self._out_dir.text().strip()
            if not copy_to:
                QMessageBox.information(self, "zarrd", "choose an output directory")
                return
        if copy_to:
            target_desc = f"copies in {copy_to} (originals untouched)"
        else:
            target_desc = f"{len(stores)} store(s) in place"
        confirm = QMessageBox.question(
            self,
            "Run bulk edit",
            f"Apply {len(self._ops)} operation(s), writing to {target_desc}?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress.setRange(0, len(stores))
        self._progress.setValue(0)
        self._log.appendPlainText(
            f"running {len(self._ops)} op(s) on {len(stores)} store(s) "
            f"({'copies -> ' + copy_to if copy_to else 'in place'})..."
        )
        self._worker = _BulkWorker(
            stores, list(self._ops), copy_to, self._overwrite.isChecked()
        )
        self._worker.message.connect(self._on_message)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_message(self, text: str) -> None:
        self._log.appendPlainText(text)
        if not text.startswith(" "):
            self._progress.setValue(self._progress.value() + 1)

    def _on_done(self, results: list[StoreOpResult]) -> None:
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        ok = sum(1 for r in results if r.ok)
        failed = len(results) - ok
        applied = sum(r.applied for r in results)
        self._progress.setValue(self._progress.maximum())
        self._log.appendPlainText(
            f"done: {ok} ok, {failed} with errors, {applied} op(s) applied total"
        )

    def _stop(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()
            self._log.appendPlainText("stop requested...")
