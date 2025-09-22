import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from datetime import datetime, timedelta
import holidays

class GanttChartWidget(QWidget):
    """A custom widget to display a Matplotlib Gantt chart."""
    def __init__(self, parent=None):
        super().__init__(parent)

        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.plot_sample_data()

    def plot_sample_data(self):
        """Plots a sample Gantt chart."""
        lines = [
            "Sample Task 1,2024-01-01,2024-01-10",
            "Sample Task 2,2024-01-05,2024-01-15",
        ]
        self.update_plot(lines)

    def _parse_date(self, date_string):
        """Tries to parse a date string with multiple formats."""
        for fmt in ('%Y/%m/%d', '%Y-%m-%d', '%y-%m-%d', '%y/%m/%d'):
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                pass
        raise ValueError(f"Date '{date_string}' could not be parsed.")

    def update_plot(self, lines, country_code='US'):
        """Updates the plot with new task data."""
        self.axes.clear()

        # Handle case where the input is just an empty string or whitespace
        if not lines or (len(lines) == 1 and not lines[0].strip()):
            self.axes.text(0.5, 0.5, "No data to display.\nEnter data in the format: Task Name,Start Date,End Date",
                           horizontalalignment='center',
                           verticalalignment='center',
                           transform=self.axes.transAxes,
                           wrap=True)
            self.axes.set_title("Gantt Chart")
            self.axes.set_xlabel("Date")
            self.axes.set_ylabel("Task")
            self.axes.get_xaxis().set_visible(False)
            self.axes.get_yaxis().set_visible(False)
            self.canvas.draw()
            return
        
        self.axes.get_xaxis().set_visible(True)
        self.axes.get_yaxis().set_visible(True)

        # --- Parse Tasks ---
        parsed_tasks = []
        for line in lines:
            if not line.strip():
                continue
            try:
                parts = line.split(',')
                if len(parts) < 3:
                    continue
                name = parts[0].strip()
                start_str = parts[1].strip()
                end_str = parts[2].strip()
                
                start_date = self._parse_date(start_str)
                end_date = self._parse_date(end_str)

                if start_date <= end_date:
                    parsed_tasks.append({'name': name, 'start': start_date, 'end': end_date})
            except (ValueError, IndexError):
                continue
        
        if not parsed_tasks:
            self.axes.text(0.5, 0.5, "No valid task data to display.",
                           horizontalalignment='center', verticalalignment='center',
                           transform=self.axes.transAxes, wrap=True)
            # Ensure axes are hidden for the error message case
            self.axes.get_xaxis().set_visible(False)
            self.axes.get_yaxis().set_visible(False)
            self.canvas.draw()
            return

        # --- Plotting ---
        task_names = [t['name'] for t in parsed_tasks]
        start_dates = [t['start'] for t in parsed_tasks]
        end_dates = [t['end'] for t in parsed_tasks]
        durations = [(t['end'] - t['start']).days + 1 for t in parsed_tasks] # Add 1 for inclusive duration

        y_pos = range(len(task_names))
        self.axes.barh(y_pos, durations, left=[mdates.date2num(sd) for sd in start_dates], align='center', height=0.5)

        # --- Holiday Setup ---
        try:
            # Dynamically get the holiday class for the given country code
            holiday_class = getattr(holidays, country_code)
        except AttributeError:
            print(f"Warning: Invalid holiday country code '{country_code}'. Defaulting to 'US'.")
            holiday_class = holidays.US
        
        # Create one holiday object for the required year range
        min_year = min(start_dates).year
        max_year = max(end_dates).year
        country_holidays = holiday_class(years=list(range(min_year, max_year + 2)))

        # --- Operating Day Calculation and Display ---
        for i, task in enumerate(parsed_tasks):
            operating_days = 0
            current_day = task['start']
            while current_day <= task['end']:
                if not (current_day.weekday() >= 5 or current_day in country_holidays):
                    operating_days += 1
                current_day += timedelta(days=1)
            
            # Display the text to the right of the bar
            self.axes.text(mdates.date2num(task['end']) + 0.5, y_pos[i], f'{operating_days} days', 
                           verticalalignment='center', fontsize=9)

        self.axes.set_yticks(y_pos)
        self.axes.set_yticklabels(task_names)
        self.axes.invert_yaxis()

        # --- Weekend and Holiday Shading ---
        min_date = min(start_dates)
        max_date = max(end_dates)
        
        current_date = min_date
        while current_date <= max_date:
            if current_date.weekday() >= 5 or current_date in country_holidays:
                self.axes.axvspan(mdates.date2num(current_date) - 0.5, 
                                  mdates.date2num(current_date) + 0.5, 
                                      facecolor='#fac8d2', alpha=0.5)
            current_date += timedelta(days=1)

        # --- Axis Formatting ---
        self.axes.xaxis_date()
        
        duration_days = (max_date - min_date).days

        if duration_days > 210:
            # Major ticks every month
            self.axes.xaxis.set_major_locator(mdates.MonthLocator())
            self.axes.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        else:
            # Custom week formatter for other durations
            def week_formatter(x, pos):
                dt = mdates.num2date(x).replace(tzinfo=None)
                sunday_of_week = dt - timedelta(days=(dt.weekday() + 1) % 7)
                jan_1st = datetime(dt.year, 1, 1)
                sunday_of_w01 = jan_1st - timedelta(days=(jan_1st.weekday() + 1) % 7)
                week_num = (sunday_of_week - sunday_of_w01).days // 7 + 1

                if duration_days < 70:
                    return f"W{week_num:02d}\n{sunday_of_week.strftime('%Y/%m/%d')}"
                elif duration_days < 140:
                    return f"W{week_num:02d}\n{sunday_of_week.strftime('%m/%d')}"
                else: # 140 to 210 days
                    return f"W{week_num:02d}\n{sunday_of_week.strftime('%b')}"

            self.axes.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.SU))
            self.axes.xaxis.set_major_formatter(mticker.FuncFormatter(week_formatter))

        self.axes.xaxis.set_minor_locator(mdates.DayLocator())
        self.figure.autofmt_xdate(rotation=0, ha='center')

        self.axes.set_xlabel("Date")
        self.axes.set_ylabel("Task")
        self.axes.set_title("Gantt Chart")
        self.axes.grid(True, which='major', axis='x', linestyle='-')
        self.axes.grid(True, which='minor', axis='x', linestyle='--', linewidth=0.5)

        self.figure.tight_layout()
        self.canvas.draw()
