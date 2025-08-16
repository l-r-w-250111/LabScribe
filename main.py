import re # For regular expressions
import os # For path manipulation
import sys
import json
import uuid
import tempfile
import base64
import subprocess
import matplotlib
from datetime import datetime
from PyQt6.QtCore import Qt, QMimeData, QPoint, QUrl, QEvent, QTimer
from PyQt6.QtGui import QDrag, QPainter, QPixmap, QKeySequence, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFrame, QLabel, QListWidget, QListWidgetItem, QTextEdit,
    QScrollArea, QTextBrowser, QPushButton, QLineEdit, QFormLayout, QSizePolicy,
    QStackedWidget, QFileDialog, QGroupBox, QToolBar
)

# Local imports
from chart_widget import ChartWidget
from table_widget import TableWidget
from settings import Settings

# External imports
import markdown # For Markdown to HTML conversion

# --- Constants ---
ADD_MIME_TYPE = "application/x-eln-add-module"
MOVE_MIME_TYPE = "application/x-eln-move-module"
CHART_MODULE_TYPE = "Chart" # Renamed
TABLE_MODULE_TYPE = "Table"       # New
MARKDOWN_MODULE_TYPE = "Markdown/Mermaid" # New

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

        self.setup_left_frame()
        self.setup_right_frame()
        self.repopulate_modules()
        self.update_outline()
        self.update_window_title()

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
        self.available_modules = ["Purpose", "Conditions", "Results", "Conclusion", "Discussion", CHART_MODULE_TYPE, TABLE_MODULE_TYPE, MARKDOWN_MODULE_TYPE]
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

        parent_layout.addWidget(self.settings_group)

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
        toolbar.addAction(new_action)
        toolbar.addAction(open_action)
        toolbar.addAction(save_action)
        right_layout.addWidget(toolbar)

        # --- Outline ---
        outline_group = QGroupBox("Outline")
        outline_layout = QVBoxLayout(outline_group)
        self.outline_browser = QTextBrowser()
        self.outline_browser.setOpenLinks(False)
        self.outline_browser.anchorClicked.connect(self.scroll_to_module)
        outline_layout.addWidget(self.outline_browser)
        outline_group.setFixedHeight(150)
        right_layout.addWidget(outline_group)

        # --- Editor Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.editor_area = EditorArea(self)
        self.scroll_area.setWidget(self.editor_area)
        
        right_layout.addWidget(self.scroll_area)
        self.main_layout.addWidget(right_widget, 1)

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
                content = {"x_data": [], "y_series": []}
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

    def update_module_content(self, module_id, new_content):
        for module in self.note_data["modules"]:
            if module["module_id"] == module_id:
                module["content"] = new_content
                break

    def update_outline(self):
        self.outline_browser.clear()
        html = ""
        for module in self.note_data["modules"]:
            html += f'<a href="#{module["module_id"]}" style="text-decoration:none; color: #ccc;">{module["type"]}</a><br>'
        self.outline_browser.setHtml(html)

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

    def new_note(self):
        self.current_note_path = None
        self.load_note(file_path=None)
        self.repopulate_modules()
        self.update_window_title()

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
