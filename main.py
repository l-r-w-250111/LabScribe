import re # For regular expressions
import os # For path manipulation
import sys
import time
import json
import uuid
import tempfile
import base64
import subprocess
import hashlib
import matplotlib
import requests
from datetime import datetime
from urllib.parse import unquote
from PyQt6.QtCore import Qt, QMimeData, QPoint, QUrl, QEvent, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QDrag, QPainter, QPixmap, QKeySequence, QAction
from collections import defaultdict
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFrame, QLabel, QListWidget, QListWidgetItem, QTextEdit,
    QScrollArea, QTextBrowser, QPushButton, QLineEdit, QFormLayout, QSizePolicy,
    QStackedWidget, QFileDialog, QGroupBox, QToolBar, QComboBox, QDialog, QTabWidget,
    QInputDialog, QMessageBox, QAbstractItemView
)

# Local imports
from chart_widget import ChartWidget
from table_widget import TableWidget
from gantt_chart_widget import GanttChartWidget
from bar_chart_widget import BarChartWidget
from pie_chart_widget import PieChartWidget
from settings import Settings
from project_view import ProjectView
from sample_view import SampleView
from indexing_service import IndexingService
from search_service import SearchService
import config

# External imports
import markdown # For Markdown to HTML conversion

# --- Constants ---
ADD_MIME_TYPE = "application/x-eln-add-module"
MOVE_MIME_TYPE = "application/x-eln-move-module"
CHART_MODULE_TYPE = "Chart" # Renamed
TABLE_MODULE_TYPE = "Table"       # New
MARKDOWN_MODULE_TYPE = "Markdown/Mermaid" # New
GANTT_CHART_MODULE_TYPE = "Gantt Chart"
METADATA_MODULE_TYPE = "Experiment Metadata"

# --- Base Draggable Module ---
class BaseModuleWidget(QFrame):
    def __init__(self, module_id, module_type, window, parent=None):
        super().__init__(parent)
        self.main_window = window
        self.module_id = module_id
        self.module_type = module_type

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        self.setContentsMargins(5, 5, 5, 5)

        self.main_layout = QVBoxLayout(self)
        self.title_label = QLabel(f"<b>⠿ {self.module_type}</b>")
        self.title_label.setCursor(Qt.CursorShape.OpenHandCursor)
        self.title_label.installEventFilter(self)
        self.main_layout.addWidget(self.title_label)

    def eventFilter(self, source, event):
        if source is self.title_label:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.drag_start_position = event.globalPosition().toPoint()
                return True
            if event.type() == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                if (event.globalPosition().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
                    return True
                mime_data = QMimeData()
                mime_data.setData(MOVE_MIME_TYPE, self.module_id.encode('utf-8'))
                drag = QDrag(self)
                drag.setMimeData(mime_data)
                pixmap = self.grab()
                drag.setPixmap(pixmap)
                drag.setHotSpot(self.mapFromGlobal(event.globalPosition().toPoint()))
                drag.exec(Qt.DropAction.MoveAction)
                return True
        return super().eventFilter(source, event)

# --- Text Module ---
class TextModuleWidget(BaseModuleWidget):
    def __init__(self, module_id, module_type, content, window, parent=None):
        super().__init__(module_id, module_type, window, parent)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(content) # Explicitly set plain text
        self.main_layout.addWidget(self.text_edit)
        self.text_edit.textChanged.connect(self.on_text_changed)
        self.text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding) # Set size policy
        QTimer.singleShot(0, self.adjust_height) # Adjust height after event loop processes layout

    def on_text_changed(self):
        self.main_window.update_module_content(self.module_id, self.text_edit.toPlainText())
        self.adjust_height()

    def adjust_height(self):
        doc_height = self.text_edit.document().size().height()
        self.text_edit.setFixedHeight(int(doc_height + 20)) # Increased padding

# --- Chart Module ---
class ChartModuleWidget(BaseModuleWidget):
    def __init__(self, module_id, module_type, content, window, parent=None):
        super().__init__(module_id, module_type, window, parent)
        
        self.content = content or {}

        # --- Controls Widget ---
        controls_widget = QFrame()
        controls_layout = QHBoxLayout(controls_widget)
        self.paste_button = QPushButton("Paste Data from Clipboard")
        self.paste_button.clicked.connect(self.paste_data)
        controls_layout.addWidget(self.paste_button)

        # --- Chart Widget ---
        self.chart_widget = ChartWidget()
        
        # Restore height
        initial_height = self.content.get("height", 300)
        self.chart_widget.setMinimumHeight(initial_height)

        self.main_layout.addWidget(controls_widget)
        self.main_layout.addWidget(self.chart_widget, 1)

        # --- Resize Handle ---
        self.resize_handle = QFrame()
        self.resize_handle.setFixedHeight(10)
        self.resize_handle.setCursor(Qt.CursorShape.SizeVerCursor)
        self.resize_handle.setStyleSheet("background-color: #555;")
        self.main_layout.addWidget(self.resize_handle)
        self.resize_handle.installEventFilter(self)
        self.is_resizing = False

        # Plot data if it exists from a loaded note
        if self.content.get("x_data") and self.content.get("y_series"):
            self.chart_widget.update_plot(self.content["x_data"], self.content["y_series"])

    def eventFilter(self, source, event):
        if hasattr(self, 'resize_handle') and source is self.resize_handle:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.is_resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_height = self.chart_widget.height()
                return True
            elif event.type() == QEvent.Type.MouseMove and self.is_resizing:
                delta = event.globalPosition().toPoint() - self.resize_start_pos
                new_height = self.resize_start_height + delta.y()
                if new_height > 100: # Minimum height
                    self.chart_widget.setMinimumHeight(new_height)
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self.is_resizing:
                    self.is_resizing = False
                    self.content["height"] = self.chart_widget.height()
                    self.main_window.update_module_content(self.module_id, self.content)
                    return True
        
        # Pass event to parent class's eventFilter
        return super().eventFilter(source, event)

    def paste_data(self):
        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text: return
        x_data, y_series = [], []
        lines = clipboard_text.strip().split('\n')
        num_y_series = 0
        for i, line in enumerate(lines):
            try:
                parts = line.replace(',', '\t').split('\t')
                if not y_series:
                    num_y_series = len(parts) - 1
                    if num_y_series <= 0: continue
                    y_series = [[] for _ in range(num_y_series)]
                if len(parts) != num_y_series + 1: continue
                x_data.append(float(parts[0]))
                for j in range(num_y_series):
                    y_series[j].append(float(parts[j+1]))
            except (ValueError, IndexError): continue
        if x_data and any(y_series):
            self.content["x_data"] = x_data
            self.content["y_series"] = y_series
            self.chart_widget.update_plot(x_data, y_series)
            self.main_window.update_module_content(self.module_id, self.content)


# --- Gantt Chart Module ---
class GanttChartModuleWidget(BaseModuleWidget):
    def __init__(self, module_id, module_type, content, window, parent=None):
        super().__init__(module_id, module_type, window, parent)

        # content is now a dictionary
        if isinstance(content, str): # Handle legacy format
            self.content = {"data": content, "height": 300}
        else:
            self.content = content or {"data": "", "height": 300}

        # --- Controls ---
        controls_widget = QFrame()
        controls_layout = QVBoxLayout(controls_widget)

        # Data Editor
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.content.get("data", ""))
        self.text_edit.textChanged.connect(self.on_text_changed)
        self.text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        controls_layout.addWidget(self.text_edit)

        # Helper Text Label
        help_label = QLabel("Enter tasks: Task Name,YYYY-MM-DD,YYYY-MM-DD")
        help_label.setStyleSheet("font-size: 12px; color: #999;")
        controls_layout.addWidget(help_label)

        # Update Button
        self.update_button = QPushButton("Update Chart")
        self.update_button.clicked.connect(self.update_chart)
        controls_layout.addWidget(self.update_button)

        self.main_layout.addWidget(controls_widget)

        # --- Chart Widget ---
        self.gantt_chart_widget = GanttChartWidget()
        initial_height = self.content.get("height", 300)
        self.gantt_chart_widget.setMinimumHeight(initial_height)
        self.main_layout.addWidget(self.gantt_chart_widget, 1)

        # --- Resize Handle ---
        self.resize_handle = QFrame()
        self.resize_handle.setFixedHeight(10)
        self.resize_handle.setCursor(Qt.CursorShape.SizeVerCursor)
        self.resize_handle.setStyleSheet("background-color: #555;")
        self.main_layout.addWidget(self.resize_handle)
        self.resize_handle.installEventFilter(self)
        self.is_resizing = False

        # Initial plot
        self.update_chart()

        # Adjust height after layout is processed
        QTimer.singleShot(0, self.adjust_text_area_height)

    def eventFilter(self, source, event):
        # Handle the title bar drag event first
        if source is self.title_label:
            return super().eventFilter(source, event)

        if hasattr(self, 'resize_handle') and source is self.resize_handle:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.is_resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_height = self.gantt_chart_widget.height()
                return True
            elif event.type() == QEvent.Type.MouseMove and self.is_resizing:
                delta = event.globalPosition().toPoint() - self.resize_start_pos
                new_height = self.resize_start_height + delta.y()
                if new_height > 100: # Minimum height
                    self.gantt_chart_widget.setMinimumHeight(new_height)
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self.is_resizing:
                    self.is_resizing = False
                    self.content["height"] = self.gantt_chart_widget.height()
                    self.main_window.update_module_content(self.module_id, self.content)
                    return True

        return super().eventFilter(source, event)

    def on_text_changed(self):
        self.content["data"] = self.text_edit.toPlainText()
        self.main_window.update_module_content(self.module_id, self.content)
        self.adjust_text_area_height()

    def adjust_text_area_height(self):
        doc_height = self.text_edit.document().size().height()
        # Set height based on content, with a minimum for approx. 2 lines and padding
        font_metrics = self.text_edit.fontMetrics()
        min_height = font_metrics.lineSpacing() * 2 + 25 # 2 lines + padding
        self.text_edit.setFixedHeight(max(int(doc_height + 20), int(min_height)))

    def update_chart(self):
        data = self.content.get("data", "")
        lines = data.strip().split('\n')
        # Pass the raw lines to the widget; it will handle all parsing.
        self.gantt_chart_widget.update_plot(lines)


# --- Metadata Module ---
class MetadataModuleWidget(BaseModuleWidget):
    project_link_requested = pyqtSignal(str)

    def __init__(self, module_id, module_type, content, window, project_names=None, parent=None):
        super().__init__(module_id, module_type, window, parent)
        self.content = content or {}
        self.project_names = project_names or []

        layout = QFormLayout()

        self.experiment_name_edit = QLineEdit(self.content.get("experiment_name", ""))

        # --- Project Row Layout ---
        project_layout = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.setEditable(True)
        self.project_combo.addItems(self.project_names)
        self.project_combo.setCurrentText(self.content.get("project", ""))
        self.open_project_button = QPushButton("Open")
        self.open_project_button.setFixedWidth(60) # Set a smaller fixed width
        self.open_project_button.clicked.connect(self._on_open_project_clicked)
        project_layout.addWidget(self.project_combo)
        project_layout.addWidget(self.open_project_button)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["In Progress", "Success", "Fail"])
        self.status_combo.setCurrentText(self.content.get("status", "In Progress"))

        self.date_edit = QLineEdit(self.content.get("date", datetime.now().strftime("%Y-%m-%d")))
        self.date_edit.setPlaceholderText("YYYY-MM-DD")
        self.cost_edit = QLineEdit(self.content.get("cost", "0"))
        self.personnel_edit = QLineEdit(self.content.get("personnel", ""))
        self.personnel_edit.setPlaceholderText("e.g. Alice, Bob")

        layout.addRow("Experiment Name:", self.experiment_name_edit)
        layout.addRow("Project Name:", project_layout)
        layout.addRow("Personnel:", self.personnel_edit)
        layout.addRow("Status:", self.status_combo)
        layout.addRow("Date:", self.date_edit)
        layout.addRow("Cost:", self.cost_edit)

        self.main_layout.addLayout(layout)

        # Connect signals to update content
        self.experiment_name_edit.textChanged.connect(self.on_content_changed)
        self.project_combo.currentTextChanged.connect(self.on_content_changed)
        self.project_combo.currentTextChanged.connect(self._update_open_button_state)
        self.personnel_edit.textChanged.connect(self.on_content_changed)
        self.status_combo.currentTextChanged.connect(self.on_content_changed)
        self.date_edit.textChanged.connect(self.on_content_changed)
        self.cost_edit.textChanged.connect(self.on_content_changed)

        self._update_open_button_state() # Set initial state

    def on_content_changed(self):
        self.content["experiment_name"] = self.experiment_name_edit.text()
        self.content["project"] = self.project_combo.currentText()
        self.content["status"] = self.status_combo.currentText()
        self.content["date"] = self.date_edit.text()
        self.content["cost"] = self.cost_edit.text()
        self.content["personnel"] = self.personnel_edit.text()
        self.main_window.update_module_content(self.module_id, self.content)

    def _update_open_button_state(self):
        """Enable the 'Open' button only if the project exists."""
        current_project = self.project_combo.currentText()
        self.open_project_button.setEnabled(current_project in self.project_names)

    def _on_open_project_clicked(self):
        """Emits a signal to request opening the project view."""
        project_name = self.project_combo.currentText()
        if project_name in self.project_names:
            self.project_link_requested.emit(project_name)

# --- Table Module ---
class TableModuleWidget(BaseModuleWidget):
    def __init__(self, module_id, module_type, content, window, parent=None):
        super().__init__(module_id, module_type, window, parent)
        self.table_widget = TableWidget()
        self.main_layout.addWidget(self.table_widget)
        if isinstance(content, list):
            self.table_widget.set_data(content)
        self.table_widget.set_data_changed_callback(self.on_table_changed)

    def on_table_changed(self):
        table_data = self.table_widget.get_data()
        self.main_window.update_module_content(self.module_id, table_data)

# --- Markdown/Mermaid Module ---
class MarkdownMermaidModuleWidget(BaseModuleWidget):
    def __init__(self, module_id, module_type, content, window, parent=None):
        super().__init__(module_id, module_type, window, parent)
        self.content = content if isinstance(content, str) else ""

        # Toggle button for edit/review mode
        self.toggle_button = QPushButton("Review Mode")
        self.toggle_button.clicked.connect(self.toggle_mode)
        self.main_layout.addWidget(self.toggle_button)

        # Stacked widget to switch between edit and review views
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Edit mode: QTextEdit
        self.edit_text_edit = QTextEdit()
        self.edit_text_edit.setPlainText(self.content) # Use setPlainText explicitly
        self.edit_text_edit.textChanged.connect(self.on_text_changed)
        self.edit_text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.stacked_widget.addWidget(self.edit_text_edit)

        # Review mode: QTextBrowser
        self.review_text_browser = QTextBrowser()
        self.review_text_browser.setOpenLinks(False) # Disable opening links
        self.review_text_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) # Ensure it expands
        self.stacked_widget.addWidget(self.review_text_browser)

        self.current_mode = "edit" # "edit" or "review"
        self.toggle_mode() # Set initial mode
        self.render_content()
        QTimer.singleShot(0, self.adjust_height)

    def on_text_changed(self):
        self.content = self.edit_text_edit.toPlainText()
        self.main_window.update_module_content(self.module_id, self.content)
        self.adjust_height()
        # Only render if in review mode, or if we just changed content in edit mode
        if self.current_mode == "review":
            self.render_content()

    def adjust_height(self):
        doc_height = 0
        if self.current_mode == "edit":
            doc_height = self.edit_text_edit.document().size().height()
        else: # review mode
            doc_height = self.review_text_browser.document().size().height()
        
        # Add some padding
        self.stacked_widget.setFixedHeight(int(doc_height + 20))

    def toggle_mode(self):
        if self.current_mode == "edit":
            self.current_mode = "review"
            self.stacked_widget.setCurrentWidget(self.review_text_browser)
            self.toggle_button.setText("Edit Mode")
            self.render_content() # Render when switching to review mode
        else:
            self.current_mode = "edit"
            self.stacked_widget.setCurrentWidget(self.edit_text_edit)
            self.toggle_button.setText("Review Mode")
            self.adjust_height()


    def render_content(self):
        # Normalize newlines to \n for consistent processing
        normalized_content = self.content.replace('\r\n', '\n').replace('\r', '\n')

        # Use a regex to find mermaid code blocks
        mermaid_blocks = re.findall(r'```mermaid(.*?)```', normalized_content, re.DOTALL)
        processed_content = normalized_content

        for i, mermaid_code in enumerate(mermaid_blocks):
            tmp_mmd_file_path = None
            tmp_png_file_path = None
            try:
                # Create a temporary file for the mermaid code
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.mmd', encoding='utf-8') as tmp_mmd_file:
                    tmp_mmd_file.write(mermaid_code)
                    tmp_mmd_file_path = tmp_mmd_file.name

                # Create a temporary file for the output PNG
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.png') as tmp_png_file:
                    tmp_png_file_path = tmp_png_file.name

                # Execute mmdc to convert mermaid to PNG
                command = ["mmdc", "-i", tmp_mmd_file_path, "-o", tmp_png_file_path]
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', shell=True)

                if result.returncode == 0 and os.path.exists(tmp_png_file_path):
                    with open(tmp_png_file_path, 'rb') as f:
                        png_data = f.read()
                    # Embed PNG directly into HTML (data URI)
                    encoded_png = base64.b64encode(png_data).decode('utf-8')
                    img_tag = f'<img src="data:image/png;base64,{encoded_png}" />'
                    processed_content = processed_content.replace(f'```mermaid{mermaid_code}```', img_tag, 1)
                else:
                    error_message = result.stderr or 'Unknown error'
                    processed_content = processed_content.replace(f'```mermaid{mermaid_code}```',
                                                                  f'<pre style="color:red;">Error rendering Mermaid: {error_message}</pre>', 1)

            except Exception as e:
                processed_content = processed_content.replace(f'```mermaid{mermaid_code}```',
                                                              f'<pre style="color:red;">Exception rendering Mermaid: {e}</pre>', 1)
            finally:
                if tmp_mmd_file_path and os.path.exists(tmp_mmd_file_path):
                    os.remove(tmp_mmd_file_path)
                if tmp_png_file_path and os.path.exists(tmp_png_file_path):
                    os.remove(tmp_png_file_path)

        # Render the final Markdown to HTML
        html_body = markdown.markdown(processed_content, extensions=['tables', 'fenced_code', 'nl2br'])

        # Prepend CSS for styling
        html_full = f"""
        <html>
        <head>
        <style>
            body {{
                color: #ccc;
                background-color: #2d2d2d;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 1em;
                margin-bottom: 1em;
            }}
            th, td {{
                border: 1px solid #555;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #444;
            }}
        </style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        self.review_text_browser.setHtml(html_full)
        self.adjust_height()

# --- Drop-enabled Editor Area ---
class EditorArea(QFrame):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.main_window = window
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAcceptDrops(True)
        self.editor_layout = QVBoxLayout(self)
        self.editor_layout.setContentsMargins(10, 20, 10, 10)
        self.editor_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.editor_layout.addStretch(1)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MOVE_MIME_TYPE) or event.mimeData().hasFormat(ADD_MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event):
        stretch_item = self.editor_layout.takeAt(self.editor_layout.count() - 1)
        if event.mimeData().hasFormat(MOVE_MIME_TYPE):
            module_id = str(event.mimeData().data(MOVE_MIME_TYPE), 'utf-8')
            self.main_window.reorder_module(module_id, event.position().toPoint())
        elif event.mimeData().hasFormat(ADD_MIME_TYPE):
            module_type = str(event.mimeData().data(ADD_MIME_TYPE), 'utf-8')
            self.main_window.add_module_widget(module_type, position=event.position().toPoint())
        
        self.editor_layout.addStretch(1)
        event.acceptProposedAction()

# --- Trash Area for Deletion ---
class TrashArea(QFrame):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        layout = QVBoxLayout(self)
        label = QLabel("🗑️ Trash")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.setStyleSheet("background-color: #444;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MOVE_MIME_TYPE):
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #ff6666;")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("background-color: #444;")

    def dropEvent(self, event):
        module_id = str(event.mimeData().data(MOVE_MIME_TYPE), 'utf-8')
        self.main_window.delete_module(module_id)
        self.setStyleSheet("background-color: #444;")
        event.acceptProposedAction()

# --- Draggable List of New Modules ---
class DraggableModuleList(QListWidget):
    def startDrag(self, supportedActions):
        item = self.currentItem()
        mime_data = QMimeData()
        mime_data.setData(ADD_MIME_TYPE, item.text().encode('utf-8'))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(supportedActions)

# --- AI Summary Worker ---
class SummaryWorker(QThread):
    summary_ready = pyqtSignal(str, str) # module_id, summary_text
    finished = pyqtSignal()

    def __init__(self, modules, parent=None):
        super().__init__(parent)
        self.modules = modules

    def run(self):
        """Generates summaries for all modules by calling the Ollama API."""
        for module in self.modules:
            module_id = module.get("module_id")
            content = module.get("content")

            if not content or not isinstance(content, (str, dict, list)):
                continue

            # Serialize content to a string for the prompt
            prompt_content = json.dumps(content) if not isinstance(content, str) else content

            prompt = f"Summarize the following lab note content in under 80 characters, focusing on the key information: {prompt_content}"

            try:
                payload = {
                    "model": config.SUMMARY_GENERATOR_MODEL,
                    "prompt": prompt,
                    "stream": True
                }

                api_url = config.OLLAMA_API_URL.rstrip('/') + "/api/generate"
                with requests.post(api_url, json=payload, stream=True) as response:
                    response.raise_for_status()

                    full_summary = ""
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                full_summary += chunk.get("response", "")
                                if chunk.get("done"):
                                    break
                            except json.JSONDecodeError:
                                print(f"Warning: Could not decode JSON line: {line}")
                                continue

                    self.summary_ready.emit(module_id, full_summary.strip())

            except requests.exceptions.RequestException as e:
                print(f"Error calling Ollama API: {e}")
                self.summary_ready.emit(module_id, f"Error: {e}")

        self.finished.emit()

# --- Indexing Worker ---
class IndexingWorker(QThread):
    """
    A dedicated worker thread to run the indexing process in the background.
    """
    finished = pyqtSignal(bool) # Emits success status

    def __init__(self, parent=None):
        super().__init__(parent)
        self.indexing_service = IndexingService()

    def run(self):
        """Runs the indexing process."""
        try:
            success = self.indexing_service.build_index()
            self.finished.emit(success)
        except Exception as e:
            print(f"An unhandled error occurred during indexing: {e}")
            self.finished.emit(False)

# --- Search Worker ---
class SearchWorker(QThread):
    """
    A worker thread to run a search query without freezing the UI.
    """
    results_ready = pyqtSignal(list)

    def __init__(self, query_text, parent=None):
        super().__init__(parent)
        self.query_text = query_text
        self.search_service = SearchService()

    def run(self):
        """Runs the search and emits the results."""
        if self.search_service.is_ready:
            results = self.search_service.search(self.query_text)
            self.results_ready.emit(results)
        else:
            self.results_ready.emit([]) # Emit empty list if index not ready

# --- Suggestion Dialog ---
class SuggestionDialog(QDialog):
    def __init__(self, suggestion_markdown, parent=None):
        super().__init__(parent)
        self.suggestion_markdown = suggestion_markdown
        self.setWindowTitle("AI Experiment Suggestion")
        self.setMinimumSize(600, 500)

        # Main layout
        layout = QVBoxLayout(self)

        # Text browser to display the rendered Markdown
        self.browser = QTextBrowser()
        self.browser.setMarkdown(self.suggestion_markdown)
        layout.addWidget(self.browser)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(self.copy_button)

        self.create_note_button = QPushButton("Create New Note from Suggestion")
        self.create_note_button.clicked.connect(self.accept) # Use accept() to signal success
        button_layout.addWidget(self.create_note_button)

        layout.addLayout(button_layout)

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.suggestion_markdown)
        # Optional: Show a confirmation
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Suggestion copied to clipboard!")
        msg.setWindowTitle("Copied")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()


# --- Generation Worker ---
class GenerationWorker(QThread):
    """
    A worker to generate an answer from a query and context chunks.
    """
    answer_chunk_ready = pyqtSignal(str)
    generation_finished = pyqtSignal()

    def __init__(self, query, search_results, parent=None):
        super().__init__(parent)
        self.query = query
        self.search_results = search_results

    def _construct_prompt(self):
        """Builds the prompt for the RAG model, including sources for citation."""
        context_blocks = []
        for res in self.search_results:
            title = res.get('source_note_title', 'Untitled Note')
            chunk = res.get('chunk_text', '')
            context_blocks.append(f"--- CONTEXT FROM NOTE: {title} ---\n{chunk}")

        context_str = "\n\n".join(context_blocks)

        prompt = (
            "You are a helpful assistant. Please answer the user's question based "
            "*only* on the following context provided from their lab notes. "
            "When you use information from a specific note, you **must** cite the source "
            "using the format `[Source: Note Title]`. "
            "If the answer is not contained within the context, say 'I could not "
            "find an answer in the provided notes.'\n\n"
            f"{context_str}\n\n"
            f"--- END CONTEXT ---\n\n"
            f"USER'S QUESTION: {self.query}\n\n"
            "ANSWER:"
        )
        return prompt

    def run(self):
        """Runs the generation process."""
        prompt = self._construct_prompt()
        payload = {
            "model": config.SUMMARY_GENERATOR_MODEL, # Reuse summarization model for generation
            "prompt": prompt,
            "stream": True
        }

        api_url = config.OLLAMA_API_URL.rstrip('/') + "/api/generate"

        try:
            with requests.post(api_url, json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            self.answer_chunk_ready.emit(chunk.get("response", ""))
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except requests.exceptions.RequestException as e:
            print(f"Error calling Ollama for generation: {e}")
        finally:
            self.generation_finished.emit()


# --- Suggestion Worker ---
class SuggestionWorker(QThread):
    """
    A worker to generate an experiment suggestion from a note's content.
    """
    suggestion_ready = pyqtSignal(str) # Emits the full suggestion text
    error_occurred = pyqtSignal(str)   # Emits an error message

    def __init__(self, note_content, parent=None):
        super().__init__(parent)
        self.note_content = note_content

    def _construct_prompt(self):
        """Builds the prompt for the suggestion model."""

        # Serialize the note content into a readable string
        context_str = json.dumps(self.note_content, indent=2)

        prompt = f"""You are an expert research scientist and lab manager with decades of experience in designing rigorous experiments. Your task is to propose a logical next experiment based on the provided lab note data. Your proposal must be actionable, scientifically sound, and follow a clear, structured format.

--- CONTEXT FROM CURRENT LAB NOTE ---
{context_str}

--- END CONTEXT ---

Based *only* on the context provided, please generate a proposal for the next experiment. The proposal **must** include the following sections formatted in Markdown:
### Proposed Experiment Title
A concise, descriptive title for the new experiment.

### Hypothesis
A clear, testable statement about what you expect the outcome to be.

### Key Objectives
A bulleted list of the primary goals of this experiment.

### Materials & Conditions
A summary of the necessary materials, equipment, and environmental conditions.

### Expected Outcomes & Success Criteria
Describe what results would support or refute the hypothesis and what constitutes a successful experiment.
"""
        return prompt

    def run(self):
        """Runs the suggestion generation process."""
        prompt = self._construct_prompt()
        payload = {
            "model": config.SUMMARY_GENERATOR_MODEL, # Reuse the same model for now
            "prompt": prompt,
            "stream": True # Use streaming
        }

        api_url = config.OLLAMA_API_URL.rstrip('/') + "/api/generate"

        try:
            full_response = ""
            with requests.post(api_url, json=payload, stream=True, timeout=60) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            full_response += chunk.get("response", "")
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
            self.suggestion_ready.emit(full_response.strip())

        except requests.exceptions.RequestException as e:
            error_message = f"Failed to connect to the AI model: {e}"
            print(error_message)
            self.error_occurred.emit(error_message)
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(error_message)
            self.error_occurred.emit(error_message)


# --- Main Application ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.module_widgets = {}
        self.current_note_path = None
        
        self.load_note() # Load initial blank/cached note

        self.setWindowTitle("ELN")
        self.setGeometry(100, 100, 1280, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)

        self.setup_status_bar()
        self.setup_left_frame()
        self.setup_right_frame()
        self.repopulate_modules()
        self.update_outline()
        self.update_window_title()
        self.summary_worker = None
        self.indexing_worker = None
        self.search_worker = None
        self.generation_worker = None
        self.suggestion_worker = None
        self.last_search_query = None
        self.last_search_results = None

    def setup_status_bar(self):
        """Sets up the widgets for the status bar."""
        self.status_indicator_widget = QWidget()
        status_layout = QHBoxLayout(self.status_indicator_widget)
        status_layout.setContentsMargins(5, 0, 5, 0)

        self.signal_label = QLabel()
        self.signal_label.setFixedSize(12, 12)

        self.finalization_status_label = QLabel("Status: Not Finalized")

        status_layout.addWidget(self.signal_label)
        status_layout.addWidget(self.finalization_status_label)

        self.statusBar().addPermanentWidget(self.status_indicator_widget)

    def start_search(self):
        """Starts the background thread to perform a search."""
        query = self.search_query_input.text()
        if not query:
            return

        self.search_button.setEnabled(False)
        self.search_button.setText("Searching...")
        self.search_results_list.clear()
        self.answer_browser.setVisible(False)
        self.answer_display_label.setVisible(False)
        self.generate_answer_button.setEnabled(False)
        self.open_search_result_button.setEnabled(False)

        self.search_worker = SearchWorker(query)
        self.search_worker.results_ready.connect(self.display_search_results)
        self.search_worker.start()

    def display_search_results(self, results):
        """Populates the QListWidget with search results."""
        self.search_results_list.clear()
        self.open_search_result_button.setEnabled(False)

        if not results:
            self.search_results_list.addItem(QListWidgetItem("No relevant results found."))
            self.search_button.setEnabled(True)
            self.search_button.setText("Search")
            return

        for res in results:
            title = res.get('source_note_title', 'Untitled Note')
            path = res.get('source_note_path', '')
            chunk = res.get('chunk_text', '')

            # Display title and score, store path and chunk in data/tooltip
            item_text = f"{title} (Score: {res.get('distance', 0):.2f})"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, path)
            list_item.setToolTip(f"Context: ...{chunk}...")
            self.search_results_list.addItem(list_item)

        self.search_button.setEnabled(True)
        self.search_button.setText("Search")

        # Store context for the generation step and enable the button
        self.last_search_query = self.search_query_input.text()
        self.last_search_results = results
        self.generate_answer_button.setEnabled(True)

        self.search_worker = None

    def _open_selected_search_result(self):
        """Loads the note from the selected item in the search results list."""
        selected_items = self.search_results_list.selectedItems()
        if not selected_items:
            return

        note_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if note_path and os.path.exists(note_path):
            self.load_note(note_path)
            self.repopulate_modules()
        else:
            print(f"Error: Note path not found or invalid: {note_path}")

    def start_answer_generation(self):
        """Starts the background thread for answer generation."""
        if not self.last_search_query or not self.last_search_results:
            return

        self.generate_answer_button.setEnabled(False)
        self.generate_answer_button.setText("Generating Answer...")
        self.answer_browser.clear()
        self.answer_browser.setVisible(True)
        self.answer_display_label.setVisible(True)

        # Pass the full search results to the worker, not just the text
        self.generation_worker = GenerationWorker(self.last_search_query, self.last_search_results)
        self.generation_worker.answer_chunk_ready.connect(self.on_answer_chunk_ready)
        self.generation_worker.generation_finished.connect(self.on_generation_finished)
        self.generation_worker.start()

    def on_answer_chunk_ready(self, text):
        """Appends a chunk of the generated answer to the display."""
        self.answer_browser.insertPlainText(text)

    def on_generation_finished(self):
        """Called when the generation worker is finished."""
        self.generate_answer_button.setEnabled(True)
        self.generate_answer_button.setText("Generate Answer from Results")
        self.generation_worker = None

    def start_suggestion_generation(self):
        """Starts the background thread for experiment suggestion."""
        self.suggest_experiment_button.setEnabled(False)
        self.suggest_experiment_button.setText("Generating...")

        # Pass a copy of the note data to the worker
        self.suggestion_worker = SuggestionWorker(dict(self.note_data))
        self.suggestion_worker.suggestion_ready.connect(self.on_suggestion_ready)
        self.suggestion_worker.error_occurred.connect(self.on_suggestion_error)
        self.suggestion_worker.finished.connect(self.on_suggestion_finished) # To re-enable button
        self.suggestion_worker.start()

    def on_suggestion_ready(self, suggestion_text):
        """Handles the successful generation of a suggestion by showing a dialog."""
        dialog = SuggestionDialog(suggestion_text, self)
        # The exec() call is modal (blocking)
        if dialog.exec():
            # This block runs if the user clicked "Create New Note from Suggestion"
            self.new_note() # Create a blank new note
            # Add a new markdown module with the suggestion content
            self.add_module_widget(
                module_type=MARKDOWN_MODULE_TYPE,
                content=suggestion_text,
                position=QPoint(0, 0) # Add to the top
            )
            # Try to extract the title from the markdown
            title_match = re.search(r"### Proposed Experiment Title\n(.*)", suggestion_text)
            new_title = title_match.group(1).strip() if title_match else "AI Suggested Experiment"
            self.note_data["title"] = new_title
            self.update_window_title()


    def on_suggestion_error(self, error_message):
        """Handles errors during suggestion generation by showing a message box."""
        QMessageBox.critical(
            self,
            "Suggestion Error",
            f"An error occurred while generating the suggestion:\n\n{error_message}"
        )

    def on_suggestion_finished(self):
        """Called when the suggestion worker is finished, regardless of outcome."""
        self.suggest_experiment_button.setEnabled(True)
        self.suggest_experiment_button.setText("Suggest Next Experiment")
        self.suggestion_worker = None # Clean up


    def start_indexing_process(self):
        """Starts the background thread to build the search index."""
        self.build_index_button.setEnabled(False)
        self.build_index_button.setText("Indexing...")
        self.indexing_status_label.setText("Status: Indexing in progress...")

        self.indexing_worker = IndexingWorker()
        self.indexing_worker.finished.connect(self.on_indexing_finished)
        self.indexing_worker.start()

    def on_indexing_finished(self, success):
        """Called when the indexing worker thread has finished."""
        self.build_index_button.setEnabled(True)
        self.build_index_button.setText("Build/Update Search Index")
        if success:
            last_indexed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.settings.set('last_indexed', last_indexed)
            self.indexing_status_label.setText(f"Status: Last indexed on {last_indexed}")
        else:
            self.indexing_status_label.setText("Status: Indexing failed. See console for errors.")
        self.indexing_worker = None # Clean up

    def _open_project_view(self, project_path):
        """Creates and displays the ProjectView for a given project path."""
        if os.path.exists(project_path):
            project_view = ProjectView(project_path, self)
            project_view.close_requested.connect(self.show_note_view)

            # Remove the old project view if it exists
            old_view = self.main_view_stack.widget(1)
            if old_view:
                self.main_view_stack.removeWidget(old_view)
                old_view.deleteLater()

            self.main_view_stack.insertWidget(1, project_view)
            self.main_view_stack.setCurrentIndex(1)
        else:
            print(f"Error: Could not find project file at {project_path}")

    def _open_project_from_link(self, project_name):
        """Finds a project by name and opens its view."""
        project_filename = f"{project_name}.project.json"
        project_path = os.path.join(self.settings.get('save_folder'), project_filename)
        self._open_project_view(project_path)

    def _get_all_project_names(self):
        """Scans the save folder and returns a list of all unique project names."""
        save_folder = self.settings.get('save_folder')
        project_names = set()
        if not os.path.isdir(save_folder):
            return []

        for filename in os.listdir(save_folder):
            if filename.endswith(".project.json"):
                try:
                    with open(os.path.join(save_folder, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'project_name' in data:
                            project_names.add(data['project_name'])
                except (IOError, json.JSONDecodeError):
                    continue
        return sorted(list(project_names))

    def _aggregate_metadata(self):
        """Scans all notes in the save folder and aggregates metadata, with caching."""
        save_folder = self.settings.get('save_folder')
        cache_path = os.path.join(os.path.expanduser("~"), ".labscribe_cache.json")

        # 1. Check if cache is valid
        if os.path.exists(cache_path):
            cache_mtime = os.path.getmtime(cache_path)
            is_stale = False
            for filename in os.listdir(save_folder):
                if filename.endswith(".json"):
                    file_path = os.path.join(save_folder, filename)
                    if os.path.getmtime(file_path) > cache_mtime:
                        is_stale = True
                        break
            if not is_stale:
                print("Loading metadata from cache.")
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)

        # 2. If cache is stale or doesn't exist, re-aggregate
        print("Re-aggregating metadata from source files...")
        all_metadata = []
        if not os.path.isdir(save_folder):
            print(f"Warning: Save folder '{save_folder}' does not exist.")
            return all_metadata

        for filename in os.listdir(save_folder):
            if filename.endswith(".json"):
                file_path = os.path.join(save_folder, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        note_data = json.load(f)
                        for module in note_data.get("modules", []):
                            if module.get("type") == METADATA_MODULE_TYPE:
                                all_metadata.append(module.get("content", {}))
                except (IOError, json.JSONDecodeError) as e:
                    print(f"Warning: Could not read or parse {filename}: {e}")
                    continue

        # 3. Save new data to cache
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(all_metadata, f)
            print(f"Metadata cache saved to {cache_path}")
        except IOError as e:
            print(f"Warning: Could not write to cache file {cache_path}: {e}")

        return all_metadata

    def show_dashboard(self):
        """Shows the KPI dashboard window with a tabbed interface."""
        raw_data = self._aggregate_metadata()

        # Pre-parse dates and filter out invalid entries
        aggregated_data = []
        for item in raw_data:
            try:
                # Add a new key 'parsed_date' to each item
                item['parsed_date'] = datetime.strptime(item.get("date", ""), '%Y-%m-%d')
                aggregated_data.append(item)
            except (ValueError, TypeError):
                # Skip items with invalid or missing date format
                continue

        dialog = QDialog(self)
        dialog.setWindowTitle("KPI Dashboard")
        main_layout = QVBoxLayout(dialog)
        dialog.resize(1000, 700) # Increased height for tabs

        if not aggregated_data:
            label = QLabel("No metadata found in any notes.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(label)
            dialog.exec()
            return

        # --- Create Main Tab Widget ---
        main_tabs = QTabWidget()
        main_layout.addWidget(main_tabs)

        # --- Tab 1: Experiments Per Month ---
        exp_per_month_widget = QWidget()
        exp_per_month_layout = QVBoxLayout(exp_per_month_widget)

        experiments_per_month = defaultdict(int)
        for item in aggregated_data:
            month_key = item['parsed_date'].strftime("%Y-%m")
            experiments_per_month[month_key] += 1

        if experiments_per_month:
            sorted_months = sorted(experiments_per_month.keys())
            bar_labels = sorted_months
            bar_values = [experiments_per_month[key] for key in sorted_months]
            exp_per_month_chart = BarChartWidget()
            exp_per_month_chart.update_plot(
                x_labels=bar_labels, y_values=bar_values,
                title="Experiments per Month"
            )
            exp_per_month_layout.addWidget(exp_per_month_chart)
        else:
            exp_per_month_layout.addWidget(QLabel("No data for 'Experiments per Month' chart."))

        main_tabs.addTab(exp_per_month_widget, "Experiments per Month")

        # --- Tab 2: Experiment Status ---
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        status_tabs = QTabWidget() # Nested tabs
        status_layout.addWidget(status_tabs)

        # Helper function to create a pie chart
        def create_status_pie_chart(data, title):
            if not data:
                # Return a widget with a message for the "no data" case
                msg_widget = QWidget()
                msg_layout = QVBoxLayout(msg_widget)
                label = QLabel(f"No data for '{title}'")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                msg_layout.addWidget(label)
                return msg_widget

            status_counts = defaultdict(int)
            for item in data:
                status = item.get("status", "Unknown")
                status_counts[status] += 1

            pie_labels = list(status_counts.keys())
            pie_values = list(status_counts.values())
            chart = PieChartWidget()
            chart.update_plot(
                labels=pie_labels, values=pie_values,
                title=title
            )
            return chart

        # Filter data for each time period
        now = datetime.now()

        # This Month
        monthly_data = [
            item for item in aggregated_data
            if item['parsed_date'].year == now.year and item['parsed_date'].month == now.month
        ]
        month_chart = create_status_pie_chart(monthly_data, "Status (This Month)")
        status_tabs.addTab(month_chart, "This Month")

        # This Quarter
        current_quarter = (now.month - 1) // 3 + 1
        quarterly_data = [
            item for item in aggregated_data
            if item['parsed_date'].year == now.year and \
               (item['parsed_date'].month - 1) // 3 + 1 == current_quarter
        ]
        quarter_chart = create_status_pie_chart(quarterly_data, "Status (This Quarter)")
        status_tabs.addTab(quarter_chart, "This Quarter")

        # This Year
        yearly_data = [
            item for item in aggregated_data
            if item['parsed_date'].year == now.year
        ]
        year_chart = create_status_pie_chart(yearly_data, "Status (This Year)")
        status_tabs.addTab(year_chart, "This Year")

        # All Time
        all_time_chart = create_status_pie_chart(aggregated_data, "Status (All Time)")
        status_tabs.addTab(all_time_chart, "All Time")

        main_tabs.addTab(status_widget, "Experiment Status")

        # --- Tab 3: Cost by Project (Monthly Stacked) ---
        cost_widget = QWidget()
        cost_layout = QVBoxLayout(cost_widget)

        # New data structure: { 'YYYY-MM': { 'ProjectA': cost, 'ProjectB': cost } }
        costs_by_month_project = defaultdict(lambda: defaultdict(float))
        for item in aggregated_data:
            project_name = item.get("project") or "Unknown Project"
            month_key = item['parsed_date'].strftime("%Y-%m")
            try:
                cost = float(item.get("cost", "0"))
                if cost > 0:
                    costs_by_month_project[month_key][project_name] += cost
            except (ValueError, TypeError):
                continue

        if costs_by_month_project:
            cost_chart = BarChartWidget()
            # Pass the new, complex data structure to the chart widget
            cost_chart.update_plot_stacked(
                data=costs_by_month_project,
                title="Monthly Cost by Project",
                y_label="Cost",
                legend_title="Projects"
            )
            cost_layout.addWidget(cost_chart)
        else:
            cost_layout.addWidget(QLabel("No cost data available."))

        main_tabs.addTab(cost_widget, "Cost by Project (Monthly)")

        # --- Tab 4: Cost Breakdown by Project ---
        cost_breakdown_widget = QWidget()
        cost_breakdown_layout = QVBoxLayout(cost_breakdown_widget)

        costs_by_project_exp = defaultdict(lambda: defaultdict(float))
        for item in aggregated_data:
            project_name = item.get("project") or "Unknown Project"
            exp_name = item.get("experiment_name") or "Unnamed Experiment"
            try:
                cost = float(item.get("cost", "0"))
                if cost > 0:
                    # To avoid overly long labels, we might want to use a unique ID if available
                    # For now, we combine project and experiment name for uniqueness
                    costs_by_project_exp[project_name][exp_name] += cost
            except (ValueError, TypeError):
                continue

        if costs_by_project_exp:
            breakdown_chart = BarChartWidget()
            breakdown_chart.update_plot_stacked(
                data=costs_by_project_exp,
                title="Cost Breakdown by Project",
                y_label="Cost",
                legend_title="Experiments"
            )
            cost_breakdown_layout.addWidget(breakdown_chart)
        else:
            cost_breakdown_layout.addWidget(QLabel("No cost data for breakdown view."))

        main_tabs.addTab(cost_breakdown_widget, "Cost Breakdown by Project")

        # --- Tab 5: Workload Analysis ---
        workload_widget = QWidget()
        workload_layout = QVBoxLayout(workload_widget)

        # New data structure: { 'PersonA': { 'Success': count, 'Fail': count }, 'PersonB': ... }
        workload_data = defaultdict(lambda: defaultdict(int))
        for item in aggregated_data:
            personnel_str = item.get("personnel", "")
            status = item.get("status", "Unknown")
            if personnel_str:
                # Split by comma and strip whitespace
                names = [name.strip() for name in personnel_str.split(',') if name.strip()]
                for name in names:
                    workload_data[name][status] += 1

        if workload_data:
            workload_chart = BarChartWidget()
            workload_chart.update_plot_stacked(
                data=workload_data,
                title="Workload Analysis by Status",
                y_label="Number of Experiments",
                legend_title="Status"
            )
            workload_layout.addWidget(workload_chart)
        else:
            workload_layout.addWidget(QLabel("No personnel data available."))

        main_tabs.addTab(workload_widget, "Workload Analysis")

        dialog.exec()

    def show_project_browser(self):
        """Shows the Project Browser dialog to open or create projects."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Project Browser")
        dialog.setMinimumSize(400, 300)

        layout = QVBoxLayout(dialog)

        # --- Project List ---
        list_label = QLabel("Projects:")
        layout.addWidget(list_label)

        project_list_widget = QListWidget()
        layout.addWidget(project_list_widget)

        # --- Buttons ---
        button_layout = QHBoxLayout()
        new_project_button = QPushButton("New Project...")
        open_project_button = QPushButton("Open Project")
        open_project_button.setEnabled(False) # Disabled until an item is selected

        button_layout.addStretch()
        button_layout.addWidget(new_project_button)
        button_layout.addWidget(open_project_button)
        layout.addLayout(button_layout)

        # --- Functions ---
        def refresh_project_list():
            """Scans for .project.json files and populates the list."""
            project_list_widget.clear()
            save_folder = self.settings.get('save_folder')
            if not os.path.isdir(save_folder):
                return
            for filename in os.listdir(save_folder):
                if filename.endswith(".project.json"):
                    # Add the project name, not the full filename
                    project_name = filename.replace(".project.json", "")
                    project_list_widget.addItem(project_name)

        def create_new_project():
            """Opens a dialog to get a new project name and creates the file."""
            project_name, ok = QInputDialog.getText(dialog, "New Project", "Enter project name:")
            if ok and project_name:
                # Sanitize project name to be a valid filename
                filename = f"{project_name}.project.json"
                file_path = os.path.join(self.settings.get('save_folder'), filename)

                if os.path.exists(file_path):
                    # In a real app, you'd show an error message here
                    print(f"Error: Project '{project_name}' already exists.")
                    return

                new_project_data = {
                    "project_id": str(uuid.uuid4()),
                    "project_name": project_name,
                    "created_at": datetime.now().isoformat(),
                    "master_gantt_data": f"Initial Task, {datetime.now().strftime('%Y-%m-%d')}, {datetime.now().strftime('%Y-%m-%d')}"
                }

                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(new_project_data, f, indent=4, ensure_ascii=False)
                    print(f"Project '{project_name}' created at {file_path}")
                    refresh_project_list()
                except IOError as e:
                    print(f"Error creating project file: {e}")

        def open_project():
            """Opens the selected project in the ProjectView."""
            selected_items = project_list_widget.selectedItems()
            if not selected_items:
                return

            project_name = selected_items[0].text()
            project_filename = f"{project_name}.project.json"
            project_path = os.path.join(self.settings.get('save_folder'), project_filename)
            self._open_project_view(project_path)
            dialog.accept() # Close the browser dialog


        # --- Connections ---
        new_project_button.clicked.connect(create_new_project)
        project_list_widget.itemSelectionChanged.connect(lambda: open_project_button.setEnabled(bool(project_list_widget.selectedItems())))
        project_list_widget.itemDoubleClicked.connect(open_project)
        open_project_button.clicked.connect(open_project)


        # Initial population
        refresh_project_list()

        dialog.exec()

    def setup_left_frame(self):
        self.left_frame = QFrame()
        self.left_frame.setFixedWidth(250)
        self.left_layout = QVBoxLayout(self.left_frame)

        # Header for the left frame with label and toggle button
        header_layout = QHBoxLayout()
        self.left_layout.addLayout(header_layout)
        header_layout.addStretch()
        self.toggle_left_panel_button = QPushButton("<<")
        self.toggle_left_panel_button.setFixedWidth(30)
        self.toggle_left_panel_button.clicked.connect(self.toggle_left_panel)
        header_layout.addWidget(self.toggle_left_panel_button)

        # --- Settings --- 
        self.setup_settings_ui(self.left_layout)

        # --- Available Modules --- 
        self.modules_group = QGroupBox("Available Modules")
        modules_layout = QVBoxLayout(self.modules_group)
        self.module_list_widget = DraggableModuleList()
        self.module_list_widget.setDragEnabled(True)
        self.available_modules = ["Purpose", "Conditions", "Results", "Conclusion", "Discussion", CHART_MODULE_TYPE, TABLE_MODULE_TYPE, GANTT_CHART_MODULE_TYPE, MARKDOWN_MODULE_TYPE, METADATA_MODULE_TYPE]
        self.module_list_widget.addItems(self.available_modules)
        modules_layout.addWidget(self.module_list_widget)
        self.left_layout.addWidget(self.modules_group)

        self.left_layout.addStretch()
        self.trash_area = TrashArea(self)
        self.left_layout.addWidget(self.trash_area)
        self.main_layout.addWidget(self.left_frame)

    def setup_settings_ui(self, parent_layout):
        self.settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout(self.settings_group)
        
        # Username
        self.username_edit = QLineEdit(self.settings.get('username'))
        self.username_edit.textChanged.connect(self.update_username)
        settings_layout.addRow("Username:", self.username_edit)

        # Save Folder
        save_folder_layout = QHBoxLayout()
        self.save_folder_edit = QLineEdit(self.settings.get('save_folder'))
        self.save_folder_edit.setReadOnly(True)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_save_folder)
        save_folder_layout.addWidget(self.save_folder_edit)
        save_folder_layout.addWidget(browse_button)
        settings_layout.addRow("Save Folder:", save_folder_layout)

        # --- AI Search Indexing ---
        settings_layout.addRow(QLabel("<b>AI Search Index</b>"))
        self.build_index_button = QPushButton("Build/Update Search Index")
        self.build_index_button.clicked.connect(self.start_indexing_process)
        settings_layout.addRow(self.build_index_button)

        last_indexed_time = self.settings.get('last_indexed') or "Never"
        self.indexing_status_label = QLabel(f"Status: Last indexed on {last_indexed_time}")
        settings_layout.addRow(self.indexing_status_label)


        parent_layout.addWidget(self.settings_group)

        # --- AI Search ---
        self.search_group = QGroupBox("AI Search")
        search_layout = QVBoxLayout(self.search_group)

        self.search_query_input = QLineEdit()
        self.search_query_input.setPlaceholderText("Enter your question...")
        self.search_query_input.returnPressed.connect(self.start_search) # Allow pressing Enter
        search_layout.addWidget(self.search_query_input)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.start_search)
        search_layout.addWidget(self.search_button)

        # --- Answer Display ---
        self.answer_display_label = QLabel("<b>AI Generated Answer:</b>")
        search_layout.addWidget(self.answer_display_label)
        self.answer_browser = QTextBrowser()
        self.answer_browser.setMinimumHeight(150)
        self.answer_browser.setVisible(False) # Initially hidden
        self.answer_display_label.setVisible(False)
        search_layout.addWidget(self.answer_browser)

        # --- Generate Answer Button ---
        self.generate_answer_button = QPushButton("Generate Answer from Results")
        self.generate_answer_button.setEnabled(False)
        self.generate_answer_button.clicked.connect(self.start_answer_generation)
        search_layout.addWidget(self.generate_answer_button)

        # --- Search Results ---
        self.results_display_label = QLabel("<b>Retrieved Notes (Sources):</b>")
        search_layout.addWidget(self.results_display_label)

        self.search_results_list = QListWidget()
        self.search_results_list.setMinimumHeight(200)
        self.search_results_list.itemSelectionChanged.connect(
            lambda: self.open_search_result_button.setEnabled(True)
        )
        self.search_results_list.itemDoubleClicked.connect(self._open_selected_search_result)
        search_layout.addWidget(self.search_results_list)

        self.open_search_result_button = QPushButton("Open Selected Note")
        self.open_search_result_button.setEnabled(False)
        self.open_search_result_button.clicked.connect(self._open_selected_search_result)
        search_layout.addWidget(self.open_search_result_button)

        parent_layout.addWidget(self.search_group)


    def update_username(self, new_username):
        self.settings.set('username', new_username)

    def browse_save_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Folder", self.settings.get('save_folder'))
        if folder:
            self.settings.set('save_folder', folder)
            self.save_folder_edit.setText(folder)

    def toggle_left_panel(self):
        if self.left_frame.width() > 50:
            self.left_frame.setFixedWidth(50)
            self.settings_group.hide()
            self.modules_group.hide()
            self.trash_area.hide()
            self.toggle_left_panel_button.setText(">>")
        else:
            self.left_frame.setFixedWidth(250)
            self.settings_group.show()
            self.modules_group.show()
            self.trash_area.show()
            self.toggle_left_panel_button.setText("<<")

    def setup_right_frame(self):
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0,0,0,0)

        # --- Toolbar ---
        toolbar = QToolBar("Main Toolbar")
        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_note)
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_note)
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_note)
        self.finalize_action = QAction("Finalize", self)
        self.finalize_action.triggered.connect(self.finalize_note)
        dashboard_action = QAction("Dashboard", self)
        dashboard_action.triggered.connect(self.show_dashboard)
        toolbar.addAction(new_action)
        toolbar.addAction(open_action)
        toolbar.addAction(save_action)
        toolbar.addAction(self.finalize_action)

        toolbar.addSeparator()
        projects_action = QAction("Projects", self)
        projects_action.triggered.connect(self.show_project_browser)
        toolbar.addAction(projects_action)
        dashboard_action = QAction("Dashboard", self)
        dashboard_action.triggered.connect(self.show_dashboard)
        toolbar.addAction(dashboard_action)

        toolbar.addSeparator()
        samples_action = QAction("Samples", self)
        samples_action.triggered.connect(self.show_sample_view)
        toolbar.addAction(samples_action)

        right_layout.addWidget(toolbar)

        # --- Outline ---
        # Create a header for the outline panel
        outline_header_layout = QHBoxLayout()
        outline_header_layout.addWidget(QLabel("<b>Outline</b>"))
        outline_header_layout.addStretch()
        self.generate_summary_button = QPushButton("Generate Summary")
        self.generate_summary_button.clicked.connect(self.generate_summaries)
        outline_header_layout.addWidget(self.generate_summary_button)

        self.suggest_experiment_button = QPushButton("Suggest Next Experiment")
        self.suggest_experiment_button.clicked.connect(self.start_suggestion_generation)
        outline_header_layout.addWidget(self.suggest_experiment_button)
        right_layout.addLayout(outline_header_layout)

        # Create the outline groupbox (without a title)
        self.outline_group = QGroupBox()
        outline_layout = QVBoxLayout(self.outline_group)
        self.outline_browser = QTextBrowser()
        self.outline_browser.setOpenLinks(False)
        self.outline_browser.anchorClicked.connect(self.scroll_to_module)
        outline_layout.addWidget(self.outline_browser)
        right_layout.addWidget(self.outline_group)

        # --- Main View Stack ---
        self.main_view_stack = QStackedWidget()

        # View 0: Note Editor
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.editor_area = EditorArea(self)
        self.scroll_area.setWidget(self.editor_area)
        self.main_view_stack.addWidget(self.scroll_area)

        # View 1: Project View (placeholder)
        self.project_view_container = QWidget()
        self.main_view_stack.addWidget(self.project_view_container)

        # View 2: Sample View (placeholder)
        self.sample_view_container = QWidget()
        self.main_view_stack.addWidget(self.sample_view_container)

        right_layout.addWidget(self.main_view_stack)
        self.main_layout.addWidget(right_widget, 1)

    def show_note_view(self):
        """Switches the main view to the note editor."""
        self.main_view_stack.setCurrentIndex(0)

    def show_sample_view(self):
        """Creates and displays the SampleView."""
        sample_view = SampleView(self)
        sample_view.close_requested.connect(self.show_note_view)

        # Remove the old view at index 2
        old_view = self.main_view_stack.widget(2)
        if old_view:
            self.main_view_stack.removeWidget(old_view)
            old_view.deleteLater()

        self.main_view_stack.insertWidget(2, sample_view)
        self.main_view_stack.setCurrentIndex(2)

    def get_drop_index(self, position: QPoint):
        for i in range(self.editor_area.editor_layout.count() - 1):
            widget = self.editor_area.editor_layout.itemAt(i).widget()
            if position.y() < widget.y() + widget.height() // 2:
                return i
        return self.editor_area.editor_layout.count() - 1

    def add_module_widget(self, module_type, content=None, module_id=None, position=None):
        is_new_module = module_id is None
        if is_new_module:
            module_id = str(uuid.uuid4())
        
        if module_type == CHART_MODULE_TYPE:
            chart_content = content if isinstance(content, dict) else {}
            widget = ChartModuleWidget(module_id, module_type, chart_content, self)
        elif module_type == GANTT_CHART_MODULE_TYPE:
            gantt_content = content if isinstance(content, dict) else {}
            widget = GanttChartModuleWidget(module_id, module_type, gantt_content, self)
        elif module_type == METADATA_MODULE_TYPE:
            metadata_content = content if isinstance(content, dict) else {}
            project_names = self._get_all_project_names()
            widget = MetadataModuleWidget(module_id, module_type, metadata_content, self, project_names=project_names)
            widget.project_link_requested.connect(self._open_project_from_link)
        elif module_type == TABLE_MODULE_TYPE:
            table_content = content if isinstance(content, list) else [["" for _ in range(4)] for _ in range(4)]
            widget = TableModuleWidget(module_id, module_type, table_content, self)
        elif module_type == MARKDOWN_MODULE_TYPE:
            markdown_content = content if isinstance(content, str) else ""
            widget = MarkdownMermaidModuleWidget(module_id, module_type, markdown_content, self)
        else:
            text_content = content if isinstance(content, str) else ""
            widget = TextModuleWidget(module_id, module_type, text_content, self)
        
        self.module_widgets[module_id] = widget

        if is_new_module:
            if module_type == CHART_MODULE_TYPE:
                content = {"x_data": [], "y_series": [], "height": 300}
            elif module_type == GANTT_CHART_MODULE_TYPE:
                content = {"data": "Task A,2024-01-01,2024-01-05\nTask B,2024-01-03,2024-01-08", "height": 300}
            elif module_type == METADATA_MODULE_TYPE:
                content = {
                    "project": "", "status": "In Progress",
                    "date": datetime.now().strftime("%Y-%m-%d"), "cost": "0",
                    "personnel": "", "experiment_name": ""
                }
            elif module_type == TABLE_MODULE_TYPE:
                content = self.module_widgets[module_id].table_widget.get_data()
            else: # For text modules
                content = ""
            
            new_module_data = {
                "module_id": module_id, "type": module_type, "content": content,
                "creator": self.settings.get('username'), "created_at": datetime.now().isoformat()
            }
            index = self.get_drop_index(position)
            self.note_data["modules"].insert(index, new_module_data)
            self.editor_area.editor_layout.insertWidget(index, widget)
        else: # Repopulating
            self.editor_area.editor_layout.insertWidget(self.editor_area.editor_layout.count() - 1, widget)
        self.update_outline()

    def reorder_module(self, module_id, position):
        widget = self.module_widgets[module_id]
        old_index = self.editor_area.editor_layout.indexOf(widget)
        module_data = self.note_data["modules"].pop(old_index)
        new_index = self.get_drop_index(position)
        if old_index < new_index:
            new_index -= 1
        self.note_data["modules"].insert(new_index, module_data)
        self.editor_area.editor_layout.insertWidget(new_index, widget)
        self.update_outline()

    def delete_module(self, module_id):
        if module_id in self.module_widgets:
            widget = self.module_widgets.pop(module_id)
            self.editor_area.editor_layout.removeWidget(widget)
            widget.deleteLater()
            self.note_data["modules"] = [m for m in self.note_data["modules"] if m["module_id"] != module_id]
            self.update_outline()

    def generate_summaries(self):
        """Starts the background thread to generate summaries for all modules."""
        self.generate_summary_button.setEnabled(False)
        self.generate_summary_button.setText("Generating...")

        # Pass a copy of the modules list to the worker
        self.summary_worker = SummaryWorker(modules=list(self.note_data["modules"]))
        self.summary_worker.summary_ready.connect(self.on_summary_ready)
        self.summary_worker.finished.connect(self.on_summary_finished)
        self.summary_worker.start()

    def on_summary_ready(self, module_id, summary):
        """Updates the note_data with the received summary."""
        for module in self.note_data["modules"]:
            if module["module_id"] == module_id:
                module["summary"] = summary
                # We can update the outline incrementally here if we want
                # self.update_outline()
                break

    def on_summary_finished(self):
        """Called when the summary worker thread has finished."""
        self.generate_summary_button.setEnabled(True)
        self.generate_summary_button.setText("Generate Summary")
        self.update_outline() # Refresh the outline with all new summaries
        self.summary_worker = None # Clean up the worker

    def update_module_content(self, module_id, new_content):
        for module in self.note_data["modules"]:
            if module["module_id"] == module_id:
                module["content"] = new_content
                # When content changes, the summary is no longer valid
                if "summary" in module:
                    del module["summary"]
        self.update_outline()

    def adjust_outline_height(self):
        doc_height = self.outline_browser.document().size().height()
        font_metrics = self.outline_browser.fontMetrics()
        min_height = font_metrics.lineSpacing() + 25 # Min height for approx 1 line + padding
        # Add extra padding to the group box itself
        self.outline_group.setFixedHeight(max(int(doc_height + 40), int(min_height)))

    def update_outline(self):
        self.outline_browser.clear()
        html = ""
        for module in self.note_data["modules"]:
            summary_text = module.get("summary", "")
            display_text = f" - <i>{summary_text}</i>" if summary_text else ""
            html += f'<a href="#{module["module_id"]}" style="text-decoration:none; color: #ccc;">{module["type"]}</a>{display_text}<br>'
        self.outline_browser.setHtml(html)
        QTimer.singleShot(0, self.adjust_outline_height)

    def scroll_to_module(self, url: QUrl):
        module_id = url.fragment()
        if module_id in self.module_widgets:
            widget = self.module_widgets[module_id]
            self.scroll_area.verticalScrollBar().setValue(widget.y())

    def clear_editor(self):
        for widget in self.module_widgets.values():
            self.editor_area.editor_layout.removeWidget(widget)
            widget.deleteLater()
        self.module_widgets.clear()

    def repopulate_modules(self):
        self.clear_editor()
        for module_data in self.note_data.get("modules", []):
            self.add_module_widget(module_data["type"], module_data.get("content"), module_data["module_id"])
        self.show_note_view()

        # After repopulating, always update the UI state
        is_finalized = False
        if self.current_note_path:
            is_finalized = os.path.exists(f"{self.current_note_path}.sig")

        self.set_read_only(is_finalized)
        self.verify_note_integrity()


    def new_note(self):
        self.current_note_path = None
        self.load_note(file_path=None)
        self.repopulate_modules()
        self.update_window_title()
        # Ensure new notes are editable and status is updated
        self.set_read_only(False)
        self.verify_note_integrity()

    def open_note(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Note", self.settings.get('save_folder'), "JSON Files (*.json)")
        if file_path:
            self.load_note(file_path)
            self.repopulate_modules()

    def save_note(self):
        if self.current_note_path:
            file_path = self.current_note_path
        else:
            title = self.note_data.get("title", "Untitled").replace(" ", "_")
            filename = f"{title}.json"
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Note", os.path.join(self.settings.get('save_folder'), filename), "JSON Files (*.json)")
            if not file_path:
                return

        self.note_data['updated_at'] = datetime.now().isoformat()
        self.note_data['author'] = self.settings.get('username')

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.note_data, f, indent=4, ensure_ascii=False)
        
        self.current_note_path = file_path
        self.update_window_title()
        print(f"Note saved to {file_path}")
        return file_path

    def finalize_note(self):
        """Finalizes the note by creating a separate signature file."""
        # First, ensure the note is saved and we have a valid path.
        note_path = self.save_note()
        if not note_path:
            QMessageBox.warning(self, "Save Required", "Please save the note before finalizing.")
            return

        sig_path = f"{note_path}.sig"
        if os.path.exists(sig_path):
            QMessageBox.information(self, "Already Finalized", "This note has already been finalized.")
            return

        reply = QMessageBox.question(self, "Finalize Note",
                                     "Are you sure you want to finalize this note? This action cannot be undone and will make the note read-only.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            return

        # self.note_data should be clean, as it's just been saved.
        # We hash the data that was just written to the file.
        try:
            serialized_data = json.dumps(self.note_data, sort_keys=True, ensure_ascii=False, indent=None).encode('utf-8')
            content_hash = hashlib.sha256(serialized_data).hexdigest()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to serialize note data for hashing: {e}")
            return

        # Create signature file
        signature_data = {
            'finalized_timestamp': datetime.now().isoformat(),
            'content_hash': content_hash
        }

        try:
            with open(sig_path, "w", encoding="utf-8") as f:
                json.dump(signature_data, f, indent=4)
            print(f"Signature file created at {sig_path} with hash {content_hash}")
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Failed to write signature file: {e}")
            return

        # Update UI
        self.set_read_only(True)
        self.verify_note_integrity()

    def verify_note_integrity(self):
        """Verifies the integrity of a note by checking for a .sig file."""
        if not self.current_note_path:
            self.signal_label.setStyleSheet("background-color: #888; border-radius: 6px;")
            self.finalization_status_label.setText("Status: Not Finalized")
            self.finalization_status_label.setStyleSheet("color: #ccc;")
            return

        sig_path = f"{self.current_note_path}.sig"
        if not os.path.exists(sig_path):
            self.signal_label.setStyleSheet("background-color: #888; border-radius: 6px;")
            self.finalization_status_label.setText("Status: Not Finalized")
            self.finalization_status_label.setStyleSheet("color: #ccc;")
            return

        # .sig file exists, so proceed with verification
        try:
            with open(sig_path, 'r', encoding='utf-8') as f:
                signature_data = json.load(f)
            stored_hash = signature_data.get('content_hash')
            timestamp_iso = signature_data.get('finalized_timestamp')
            dt_object = datetime.fromisoformat(timestamp_iso)
            display_timestamp = dt_object.strftime('%Y-%m-%d %H:%M:%S')
        except (IOError, json.JSONDecodeError, ValueError, TypeError) as e:
            self.signal_label.setStyleSheet("background-color: #ffaa00; border-radius: 6px;") # Orange
            self.finalization_status_label.setText("Status: Error reading signature file")
            self.finalization_status_label.setStyleSheet("color: #ffaa00;")
            print(f"Error reading or parsing signature file: {e}")
            return

        # Calculate hash of the current note data
        try:
            serialized_data = json.dumps(self.note_data, sort_keys=True, ensure_ascii=False, indent=None).encode('utf-8')
            current_hash = hashlib.sha256(serialized_data).hexdigest()
        except Exception as e:
            self.signal_label.setStyleSheet("background-color: #ffaa00; border-radius: 6px;") # Orange
            self.finalization_status_label.setText(f"Status: Verification Error | Finalized: {display_timestamp}")
            self.finalization_status_label.setStyleSheet("color: #ffaa00;")
            print(f"Error during verification serialization: {e}")
            return

        if current_hash == stored_hash:
            self.signal_label.setStyleSheet("background-color: #aaffaa; border-radius: 6px;") # Green
            self.finalization_status_label.setText(f"Status: Verified | Finalized: {display_timestamp}")
            self.finalization_status_label.setStyleSheet("color: #aaffaa;")
        else:
            self.signal_label.setStyleSheet("background-color: #ff5555; border-radius: 6px;") # Red
            self.finalization_status_label.setText(f"Status: Verification FAILED | Finalized: {display_timestamp}")
            self.finalization_status_label.setStyleSheet("color: #ff5555;")

    def set_read_only(self, read_only):
        """Sets the entire note UI to be read-only or editable."""
        # Disable/enable all module widgets
        for widget in self.module_widgets.values():
            # General input widgets
            for child in widget.findChildren(QTextEdit):
                child.setReadOnly(read_only)
            for child in widget.findChildren(QLineEdit):
                child.setReadOnly(read_only)
            for child in widget.findChildren(QComboBox):
                child.setEnabled(not read_only)
            for child in widget.findChildren(QPushButton):
                # Don't disable the "Open Project" button in the metadata module
                if isinstance(widget, MetadataModuleWidget) and child is widget.open_project_button:
                    continue
                child.setEnabled(not read_only)

            # Specific handling for TableWidget edit triggers
            if isinstance(widget, TableModuleWidget):
                if read_only:
                    widget.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                else:
                    widget.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)

        # Disable/enable main interaction elements
        self.finalize_action.setEnabled(not read_only)
        self.module_list_widget.setEnabled(not read_only)
        self.trash_area.setAcceptDrops(not read_only)
        self.trash_area.setStyleSheet("background-color: #444;" if not read_only else "background-color: #2d2d2d;")

        # Also disable drag-and-drop on module titles
        for widget in self.module_widgets.values():
            widget.title_label.setCursor(Qt.CursorShape.ArrowCursor if read_only else Qt.CursorShape.OpenHandCursor)
            widget.title_label.setEnabled(not read_only)

    def load_note(self, file_path=None):
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.note_data = json.load(f)
                self.current_note_path = file_path
            except (FileNotFoundError, json.JSONDecodeError):
                self.new_note()
        else:
            self.note_data = {
                "note_id": str(uuid.uuid4()), "title": "Untitled", "tags": [],
                "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
                "author": self.settings.get('username'),
                "modules": []
            }
            self.current_note_path = None
        self.update_window_title()

    def update_window_title(self):
        title = "ELN"
        if self.current_note_path:
            title += f" - {os.path.basename(self.current_note_path)}"
        else:
            title += " - New Note"
        self.setWindowTitle(title)

    def closeEvent(self, event):
        self.save_note()
        super().closeEvent(event)

if __name__ == '__main__':
    try:
        matplotlib.rcParams['font.family'] = 'Yu Gothic'
    except Exception as e:
        print(f"Warning: Could not set Japanese font. {e}")

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QFrame { background-color: #2d2d2d; }
        QLabel { color: #ccc; font-size: 14px; }
        QTextEdit { background-color: #3c3c3c; color: #ccc; border: 1px solid #555; font-size: 14px; }
        QLineEdit { background-color: #3c3c3c; color: #ccc; border: 1px solid #555; font-size: 14px; }
        QPushButton { background-color: #555; color: #ccc; padding: 5px; border: 1px solid #666; }
        QPushButton:hover { background-color: #666; }
        QListWidget { background-color: #3c3c3c; color: #ccc; border: 1px solid #555; font-size: 14px; }
        QTextBrowser { background-color: #2d2d2d; color: #ccc; border: none; }
        QTableWidget { background-color: #3c3c3c; color: #ccc; gridline-color: #555; }
        QGroupBox { color: #ccc; }
        QToolBar { background-color: #3c3c3c; border: none; }
        QToolButton { color: #fff; }
        /* Table styles for Markdown preview */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1em;
            margin-bottom: 1em;
            color: #ccc;
        }
        th, td {
            border: 1px solid #555; /* Darker border for dark theme */
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #444;
        }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
