import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from collections import defaultdict

class BarChartWidget(QWidget):
    """A custom widget to display a Matplotlib bar chart."""
    def __init__(self, parent=None):
        super().__init__(parent)

        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.figure.patch.set_facecolor('#2d2d2d') # Match dark theme
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def update_plot(self, x_labels, y_values, title="", x_label="", y_label=""):
        """Updates the bar chart with new data."""
        self._configure_axes_style()
        self.axes.bar(x_labels, y_values)

        self.axes.set_title(title, color='white')
        self.axes.set_xlabel(x_label, color='white')
        self.axes.set_ylabel(y_label, color='white')

        self.figure.autofmt_xdate(rotation=45, ha='right')
        self.figure.tight_layout()
        self.canvas.draw()

    def update_plot_stacked(self, data, title="", y_label="", legend_title=""):
        """
        Updates the bar chart with a stacked view.
        Data format: { 'x_category': { 'stack_segment': value, ... }, ... }
        Example: { '2024-01': { 'Project A': 100, 'Project B': 150 }, ... }
        """
        self._configure_axes_style()

        # --- Data Preparation ---
        x_categories = sorted(data.keys())
        all_segments = sorted(list(set(seg for cat_data in data.values() for seg in cat_data.keys())))

        if not x_categories or not all_segments:
            self.axes.text(0.5, 0.5, 'No data to display', ha='center', va='center', color='white')
            self.canvas.draw()
            return

        # Use a consistent color map for each segment (project)
        color_map = {segment: plt.cm.get_cmap('tab20')(i) for i, segment in enumerate(all_segments)}

        # --- Plotting ---
        bottoms = defaultdict(float)
        for segment in all_segments: # segment is the project name
            values = [data[x_cat].get(segment, 0) for x_cat in x_categories]
            bars = self.axes.bar(x_categories, values, label=segment, bottom=[bottoms[x_cat] for x_cat in x_categories], color=color_map[segment])

            # Add text labels inside the bars
            y_axis_max = self.axes.get_ylim()[1]
            for i, bar in enumerate(bars):
                height = bar.get_height()
                if height > 0: # Only label bars with a value
                    y_center = bar.get_y() + height / 2
                    # A simple threshold to avoid tiny labels
                    # Check if height is more than 5% of the total axis height
                    if y_axis_max > 0 and (height / y_axis_max) > 0.05:
                         self.axes.text(bar.get_x() + bar.get_width() / 2.0, y_center,
                                       segment, ha='center', va='center', color='white', fontsize=8)

            # Update the bottom values for the next stack
            for i, x_cat in enumerate(x_categories):
                bottoms[x_cat] += values[i]

        # --- Styling ---
        self.axes.set_title(title, color='white')
        self.axes.set_ylabel(y_label, color='white')
        self.axes.legend(title=legend_title)

        self.figure.autofmt_xdate(rotation=45, ha='right')
        self.figure.tight_layout()
        self.canvas.draw()

    def _configure_axes_style(self):
        """Helper to set the dark theme style for the axes."""
        self.axes.clear()
        self.axes.set_facecolor('#3c3c3c')
        self.axes.tick_params(axis='x', colors='white')
        self.axes.tick_params(axis='y', colors='white')
        self.axes.spines['bottom'].set_color('white')
        self.axes.spines['top'].set_color('white')
        self.axes.spines['right'].set_color('white')
        self.axes.spines['left'].set_color('white')
        self.axes.grid(True, which='major', axis='y', linestyle='--', color='#666')
