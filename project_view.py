import json
import os
from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel
)

from gantt_chart_widget import GanttChartWidget

class ProjectView(QWidget):
    close_requested = pyqtSignal()

    def __init__(self, project_file_path, main_window, parent=None):
        super().__init__(parent)
        self.project_file_path = project_file_path
        self.main_window = main_window # Reference to the main window
        self.project_data = {}

        # --- Load Project Data ---
        self._load_project()

        # --- Main Layout ---
        main_layout = QHBoxLayout(self)

        # --- Left Panel (Controls & Notes) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Project Title and Close Button
        title_layout = QHBoxLayout()
        project_name = self.project_data.get('project_name', 'Unnamed Project')
        title_label = QLabel(f"<b>Project: {project_name}</b>")
        close_button = QPushButton("Close Project")
        close_button.clicked.connect(self.close_requested.emit)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_button)
        left_layout.addLayout(title_layout)

        # Gantt Editor
        gantt_label = QLabel("Master Gantt Chart Data:")
        self.gantt_data_editor = QTextEdit()
        self.gantt_data_editor.setPlainText(self.project_data.get("master_gantt_data", ""))

        update_button = QPushButton("Update Chart")
        update_button.clicked.connect(self._update_chart)

        save_button = QPushButton("Save Project")
        save_button.clicked.connect(self._save_project)

        left_layout.addWidget(gantt_label)
        left_layout.addWidget(self.gantt_data_editor, 1) # Give it stretch factor
        left_layout.addWidget(update_button)
        left_layout.addWidget(save_button)

        # Linked Notes List
        notes_label = QLabel("Linked Notes (Tickets):")
        self.notes_list_widget = QListWidget()
        self.notes_list_widget.itemDoubleClicked.connect(self._open_selected_note)

        left_layout.addWidget(notes_label)
        left_layout.addWidget(self.notes_list_widget, 1) # Give it stretch factor

        # --- Right Panel (Chart) ---
        self.gantt_chart_widget = GanttChartWidget()

        main_layout.addWidget(left_panel, 1) # 1/3 of the space
        main_layout.addWidget(self.gantt_chart_widget, 2) # 2/3 of the space

        # Initial data population
        self._update_chart()
        self._refresh_linked_notes()

    def _load_project(self):
        """Loads the project data from the .project.json file."""
        try:
            with open(self.project_file_path, 'r', encoding='utf-8') as f:
                self.project_data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading project file {self.project_file_path}: {e}")
            self.project_data = {}

    def _save_project(self):
        """Saves the current project data back to the file."""
        # Update the gantt data from the editor
        self.project_data['master_gantt_data'] = self.gantt_data_editor.toPlainText()

        try:
            with open(self.project_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.project_data, f, indent=4, ensure_ascii=False)
            print(f"Project '{self.project_data.get('project_name')}' saved successfully.")
        except IOError as e:
            print(f"Error saving project file: {e}")

    def _update_chart(self):
        """Updates the Gantt chart from the editor's content."""
        gantt_data = self.gantt_data_editor.toPlainText()
        lines = gantt_data.strip().split('\n')
        self.gantt_chart_widget.update_plot(lines)

    def _refresh_linked_notes(self):
        """Scans all notes and populates the list with notes linked to this project."""
        self.notes_list_widget.clear()
        current_project_name = self.project_data.get("project_name")
        if not current_project_name:
            return

        save_folder = self.main_window.settings.get('save_folder')
        if not os.path.isdir(save_folder):
            return

        for filename in os.listdir(save_folder):
            # We only care about note files, not project files
            if filename.endswith(".json") and not filename.endswith(".project.json"):
                file_path = os.path.join(save_folder, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        note_data = json.load(f)
                        for module in note_data.get("modules", []):
                            # Check for the specific metadata module
                            if module.get("type") == "Experiment Metadata":
                                content = module.get("content", {})
                                if content.get("project") == current_project_name:
                                    # Prioritize Experiment Name for display, fallback to note title
                                    item_text = content.get("experiment_name") or note_data.get('title', filename)
                                    list_item = QListWidgetItem(item_text)
                                    list_item.setData(Qt.ItemDataRole.UserRole, file_path)
                                    self.notes_list_widget.addItem(list_item)
                                    break # Move to the next file once a link is found
                except (IOError, json.JSONDecodeError):
                    continue # Skip files that can't be read or parsed

    def _open_selected_note(self):
        """Tells the main window to open the selected note."""
        selected_items = self.notes_list_widget.selectedItems()
        if not selected_items:
            return

        note_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if note_path:
            self.main_window.load_note(note_path)
            self.main_window.repopulate_modules()
            self.main_window.activateWindow() # Bring the main window to the front
