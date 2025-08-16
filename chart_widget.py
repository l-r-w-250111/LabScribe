import sys
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout

# Matplotlib imports
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

class ChartWidget(QWidget):
    """A custom widget to display a Matplotlib chart."""
    def __init__(self, parent=None):
        super().__init__(parent)

        # Create a figure and a set of subplots
        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.axes = self.figure.add_subplot(111)

        # Create the canvas widget that displays the figure
        self.canvas = FigureCanvas(self.figure)

        # Create the Matplotlib navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Set the layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.plot_sample_data()

    def plot_sample_data(self):
        """Plots a simple sine wave as sample data."""
        x = np.linspace(0, 2 * np.pi, 100)
        y = np.sin(x)
        
        self.axes.clear() # Clear previous plot
        self.axes.plot(x, y)
        self.axes.set_title("Sample Sine Wave")
        self.axes.set_xlabel("X-axis")
        self.axes.set_ylabel("Y-axis")
        self.axes.grid(True)
        self.figure.tight_layout() # Adjust plot to prevent labels overlapping
        self.canvas.draw() # Redraw the canvas

    def update_plot(self, x_data, y_series, title=None, xlabel=None, ylabel=None):
        """Updates the plot with new data. If labels are None, they are not updated."""
        # Store current labels before clearing
        current_title = self.axes.get_title()
        current_xlabel = self.axes.get_xlabel()
        current_ylabel = self.axes.get_ylabel()

        self.axes.clear()
        for i, y_data in enumerate(y_series):
            self.axes.plot(x_data, y_data, label=f'Series {i+1}')
        
        # Set labels - use new label if provided, otherwise restore old one
        self.axes.set_title(title if title is not None else current_title)
        self.axes.set_xlabel(xlabel if xlabel is not None else current_xlabel)
        self.axes.set_ylabel(ylabel if ylabel is not None else current_ylabel)
        
        self.axes.grid(True)
        if y_series:
            self.axes.legend()
        self.figure.tight_layout()
        self.canvas.draw()

    
