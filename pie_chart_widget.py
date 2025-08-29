import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class PieChartWidget(QWidget):
    """A custom widget to display a Matplotlib pie chart."""
    def __init__(self, parent=None):
        super().__init__(parent)

        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def update_plot(self, labels, values, title=""):
        """Updates the pie chart with new data."""
        self.axes.clear()

        # Explode the first slice slightly for emphasis if there are slices
        explode = [0.1] * len(labels) if labels else None

        self.axes.pie(values, labels=labels, autopct='%1.1f%%',
                      startangle=90, explode=explode, shadow=True)

        self.axes.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        self.axes.set_title(title)

        self.figure.tight_layout()
        self.canvas.draw()
