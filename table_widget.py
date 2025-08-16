import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QHBoxLayout, QHeaderView, QApplication, QLineEdit, QFormLayout, QAbstractItemView
)
from PyQt6.QtGui import QKeySequence

class TableWidget(QWidget):
    """A custom widget to display and edit data in a table."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_changed_callback = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        self.insert_row_btn = QPushButton("Insert Row")
        self.del_row_btn = QPushButton("Delete Row")
        self.insert_col_btn = QPushButton("Insert Column")
        self.del_col_btn = QPushButton("Delete Column")
        controls_layout.addWidget(self.insert_row_btn)
        controls_layout.addWidget(self.del_row_btn)
        controls_layout.addWidget(self.insert_col_btn)
        controls_layout.addWidget(self.del_col_btn)
        controls_layout.addStretch()

        self.table = QTableWidget()
        self.table.setRowCount(4)
        self.table.setColumnCount(4)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems) # Enable cell selection
        self.table.setSelectionMode(QTableWidget.SelectionMode.ContiguousSelection) # Allow contiguous selection

        layout.addWidget(controls_widget)
        layout.addWidget(self.table)

        self.insert_row_btn.clicked.connect(self.insert_row)
        self.del_row_btn.clicked.connect(self.delete_row)
        self.insert_col_btn.clicked.connect(self.insert_column)
        self.del_col_btn.clicked.connect(self.delete_column)
        self.table.cellChanged.connect(self.on_cell_changed)
        
        self.table.keyPressEvent = self.keyPressEvent # Override keyPressEvent

        self.update_table_height()

    def get_data(self):
        data = []
        for r in range(self.table.rowCount()):
            row_data = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row_data.append(item.text() if item else "")
            data.append(row_data)
        return data

    def set_data(self, data):
        self.table.blockSignals(True)
        
        if not data or not isinstance(data, list) or (len(data) > 0 and not isinstance(data[0], list)):
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.update_table_height()
            self.table.blockSignals(False)
            return
        
        rows = len(data)
        cols = len(data[0]) if rows > 0 else 0
        self.table.setRowCount(rows)
        self.table.setColumnCount(cols)

        for r, row_data in enumerate(data):
            for c, cell_text in enumerate(row_data):
                self.table.setItem(r, c, QTableWidgetItem(str(cell_text)))
        
        self.update_table_height()
        self.table.blockSignals(False)

    def set_data_changed_callback(self, callback):
        self.data_changed_callback = callback

    def on_cell_changed(self, row, column):
        self.update_table_height()
        if self.data_changed_callback:
            self.data_changed_callback()

    def update_table_height(self):
        default_row_height = self.table.fontMetrics().height() + 8 
        
        row_height = default_row_height
        if self.table.rowCount() > 0:
            row_height = self.table.rowHeight(0) 
        
        header_height = self.table.horizontalHeader().height()
        total_height = (self.table.rowCount() * row_height) + header_height + 5
        self.table.setFixedHeight(total_height)

    def insert_row(self):
        current_row = self.table.currentRow()
        if current_row == -1:
            current_row = self.table.rowCount()
        self.table.insertRow(current_row)
        self.update_table_height()
        self.on_cell_changed(0,0) # Trigger save

    def delete_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self.update_table_height()
            self.on_cell_changed(0,0)

    def insert_column(self):
        current_col = self.table.currentColumn()
        if current_col == -1:
            current_col = self.table.columnCount()
        self.table.insertColumn(current_col)
        self.on_cell_changed(0,0)

    def delete_column(self):
        current_col = self.table.currentColumn()
        if current_col >= 0:
            self.table.removeColumn(current_col)
            self.on_cell_changed(0,0)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.paste_selection()
        else:
            super().keyPressEvent(event)

    def copy_selection(self):
        selection = self.table.selectedRanges()
        if not selection: return

        # Assuming contiguous selection for simplicity
        r = selection[0]
        min_row, max_row = r.topRow(), r.bottomRow()
        min_col, max_col = r.leftColumn(), r.rightColumn()

        output = []
        for row in range(min_row, max_row + 1):
            row_data = []
            for col in range(min_col, max_col + 1):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            output.append("\t".join(row_data))
        
        QApplication.clipboard().setText("\n".join(output))

    def paste_selection(self):
        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text: return

        current_row = self.table.currentRow()
        current_col = self.table.currentColumn()
        if current_row == -1 or current_col == -1: # If no cell selected, paste at 0,0
            current_row = 0
            current_col = 0

        lines = clipboard_text.split('\n')
        
        self.table.blockSignals(True) # Block signals during paste

        for r_offset, line in enumerate(lines):
            parts = line.split('\t')
            for c_offset, text in enumerate(parts):
                target_row = current_row + r_offset
                target_col = current_col + c_offset

                # Expand table if necessary
                if target_row >= self.table.rowCount():
                    self.table.insertRow(self.table.rowCount())
                if target_col >= self.table.columnCount():
                    self.table.insertColumn(self.table.columnCount())
                
                self.table.setItem(target_row, target_col, QTableWidgetItem(text))
        
        self.table.blockSignals(False) # Unblock signals
        self.on_cell_changed(0,0) # Trigger save and height update
