import sys
import io
from datetime import datetime
import qrcode
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QFormLayout, QLineEdit, QMessageBox, QApplication, QLabel
)

from sample_service import SampleService

class QRCodeDialog(QDialog):
    """A dialog to display a QR code."""
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sample QR Code")
        layout = QVBoxLayout(self)
        label = QLabel()
        label.setPixmap(pixmap)
        layout.addWidget(label)

class SampleDialog(QDialog):
    """
    A dialog for creating and editing samples.
    """
    def __init__(self, sample_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sample Details")
        self.setMinimumWidth(400)

        self.sample_data = sample_data or {}

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit(self.sample_data.get("name", ""))
        self.type_edit = QLineEdit(self.sample_data.get("type", ""))
        self.source_edit = QLineEdit(self.sample_data.get("source", ""))
        self.storage_loc_edit = QLineEdit(self.sample_data.get("storage_location", ""))

        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Type:", self.type_edit)
        form_layout.addRow("Source:", self.source_edit)
        form_layout.addRow("Storage Location:", self.storage_loc_edit)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)

        # Connections
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_data(self):
        """Returns the data entered in the dialog."""
        return {
            "name": self.name_edit.text(),
            "type": self.type_edit.text(),
            "source": self.source_edit.text(),
            "storage_location": self.storage_loc_edit.text()
        }


class SampleView(QWidget):
    """
    A widget to display and manage samples.
    """
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sample_service = SampleService()
        self.headers = ["ID", "Name", "Type", "Source", "Creation Date", "Storage Location"]

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)

        # --- Title and Close Button ---
        title_layout = QHBoxLayout()
        title_label = QLabel("<b>Sample Management</b>")
        close_button = QPushButton("Close View")
        close_button.clicked.connect(self.close_requested.emit)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_button)
        main_layout.addLayout(title_layout)

        # --- Table Widget ---
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(len(self.headers))
        self.table_widget.setHorizontalHeaderLabels(self.headers)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.table_widget)

        # --- Button Layout ---
        button_layout = QHBoxLayout()
        self.new_button = QPushButton("New Sample")
        self.edit_button = QPushButton("Edit Selected")
        self.delete_button = QPushButton("Delete Selected")
        self.qr_button = QPushButton("Show QR Code")

        button_layout.addStretch()
        button_layout.addWidget(self.new_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.qr_button)
        main_layout.addLayout(button_layout)

        # --- Connections ---
        self.new_button.clicked.connect(self._handle_new_sample)
        self.edit_button.clicked.connect(self._handle_edit_sample)
        self.delete_button.clicked.connect(self._handle_delete_sample)
        self.qr_button.clicked.connect(self._handle_show_qr_code)

        # Initial data load
        self._populate_table()

    def _populate_table(self):
        """Clears and refills the table with the latest sample data."""
        self.table_widget.setRowCount(0)
        samples = self.sample_service.get_samples()

        for row, sample in enumerate(samples):
            self.table_widget.insertRow(row)
            self.table_widget.setItem(row, 0, QTableWidgetItem(sample.get("id", "")))
            self.table_widget.setItem(row, 1, QTableWidgetItem(sample.get("name", "")))
            self.table_widget.setItem(row, 2, QTableWidgetItem(sample.get("type", "")))
            self.table_widget.setItem(row, 3, QTableWidgetItem(sample.get("source", "")))
            self.table_widget.setItem(row, 4, QTableWidgetItem(sample.get("created_at", "")))
            self.table_widget.setItem(row, 5, QTableWidgetItem(sample.get("storage_location", "")))

    def _handle_new_sample(self):
        """Opens a dialog to create a new sample."""
        dialog = SampleDialog(parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            if not new_data.get("name"):
                QMessageBox.warning(self, "Input Error", "Sample name cannot be empty.")
                return

            new_data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.sample_service.add_sample(new_data)
            self._populate_table()

    def _handle_edit_sample(self):
        """Opens a dialog to edit the selected sample."""
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select a sample to edit.")
            return

        row_index = selected_rows[0].row()
        sample_id = self.table_widget.item(row_index, 0).text()

        # Find the full sample data
        sample_to_edit = next((s for s in self.sample_service.get_samples() if s['id'] == sample_id), None)
        if not sample_to_edit:
            QMessageBox.critical(self, "Error", "Could not find the selected sample.")
            return

        dialog = SampleDialog(sample_data=sample_to_edit, parent=self)
        if dialog.exec():
            updated_data = dialog.get_data()
            if not updated_data.get("name"):
                QMessageBox.warning(self, "Input Error", "Sample name cannot be empty.")
                return

            # Preserve original creation date
            updated_data['created_at'] = sample_to_edit.get('created_at')
            self.sample_service.update_sample(sample_id, updated_data)
            self._populate_table()

    def _handle_delete_sample(self):
        """Deletes the selected sample after confirmation."""
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select a sample to delete.")
            return

        row_index = selected_rows[0].row()
        sample_id = self.table_widget.item(row_index, 0).text()
        sample_name = self.table_widget.item(row_index, 1).text()

        reply = QMessageBox.question(
            self, 'Confirm Deletion',
            f"Are you sure you want to delete the sample '{sample_name}' (ID: {sample_id})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.sample_service.delete_sample(sample_id):
                self._populate_table()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete the sample.")

    def _handle_show_qr_code(self):
        """Generates and displays a QR code for the selected sample's ID."""
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select a sample to generate a QR code.")
            return

        row_index = selected_rows[0].row()
        sample_id = self.table_widget.item(row_index, 0).text()

        # Generate QR code
        qr_image = qrcode.make(sample_id)

        # Convert PIL image to QPixmap
        buffer = io.BytesIO()
        qr_image.save(buffer, "PNG")
        qt_image = QImage.fromData(buffer.getvalue())
        pixmap = QPixmap.fromImage(qt_image)

        # Show in dialog
        dialog = QRCodeDialog(pixmap, self)
        dialog.exec()

if __name__ == '__main__':
    # This part is for standalone testing of the SampleView
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget { background-color: #2d2d2d; color: #ccc; }
        QLabel { font-size: 14px; }
        QPushButton { background-color: #555; color: #ccc; padding: 5px; border: 1px solid #666; }
        QPushButton:hover { background-color: #666; }
        QTableWidget { background-color: #3c3c3c; color: #ccc; gridline-color: #555; }
        QLineEdit { background-color: #3c3c3c; color: #ccc; border: 1px solid #555; }
    """)
    view = SampleView()
    view.setWindowTitle("Sample Management View (Standalone Test)")
    view.resize(800, 600)
    view.show()
    sys.exit(app.exec())
