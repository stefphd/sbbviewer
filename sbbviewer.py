import json
import numpy as np
from scipy.signal import butter, filtfilt
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout, QGroupBox, QCheckBox, QPushButton, QListWidget, QFileDialog, QAbstractItemView, QHBoxLayout
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector


def sbbimport(file_path, n_max, signals):
    data = {}

    try:
        # Open file
        with open(file_path, 'rb') as file:
            # Read file
            datavec = np.fromfile(file, dtype=np.float32)
        
        # Check if the length of datavec is a multiple of n_max
        if len(datavec) % n_max != 0:
            return None

        # Reshape data
        datamat = datavec.reshape((len(datavec) // n_max, n_max)).T

        # Create sample vector
        sample = np.arange(1, datamat.shape[1] + 1)

        # Add sample to data dictionary
        data['sample'] = sample.tolist()

        # Add signals to data dictionary
        for i, signal_name in enumerate(signals):
            data[signal_name] = datamat[i, :].tolist()
        return data

    except Exception as e:
        print(f"Error loading SBB file: {str(e)}")
        return None

def autoscale_y(ax,margin=0.1):

    def get_bottom_top(line):
        xd = line.get_xdata()
        yd = line.get_ydata()
        lo,hi = ax.get_xlim()
        y_displayed = yd[((xd>lo) & (xd<hi))]
        h = np.max(y_displayed) - np.min(y_displayed)
        bot = np.min(y_displayed)-margin*h
        top = np.max(y_displayed)+margin*h
        return bot,top

    lines = ax.get_lines()
    bot,top = np.inf, -np.inf

    for line in lines:
        new_bot, new_top = get_bottom_top(line)
        if new_bot < bot: bot = new_bot
        if new_top > top: top = new_top

    if bot == np.inf: bot = 0
    if top == -np.inf: top = 1
    
    ax.set_ylim(bot,top)


class SBBViewer(QMainWindow):
    def __init__(self):
        super(SBBViewer, self).__init__()

        # Set the window title
        self.setWindowTitle("SBBViewer")  # Replace with your desired title

        # Load signals from JSON
        with open('settings.json') as f:
            config = json.load(f)
            self.signals = config["signals"]
            self.n = config["n"]
            self.decim = config["decim"]
            self.Fs = config["Fs"]
            self.Fcut = config["Fcut"]

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.listbox1 = QListWidget()
        self.listbox2 = QListWidget()
        self.load_button = QPushButton("Load .sbb file")
        self.filter_checkbox = QCheckBox("Filter signals")

        button_checkbox_layout = QHBoxLayout()
        button_checkbox_layout.addWidget(self.load_button)
        button_checkbox_layout.addWidget(self.filter_checkbox)
        
        left_layout.addLayout(button_checkbox_layout)
        left_layout.addWidget(self.listbox1)
        left_layout.addWidget(self.listbox2)

        # Set maximum width for the left panel
        left_panel.setMaximumWidth(190)  # Adjust the width as needed

        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.figure, (self.ax1, self.ax2) = plt.subplots(2, 1, sharex=True)
        self.canvas = FigureCanvas(self.figure)
        # Set xlabel and ylabel for the bottom axes
        self.set_axlabels()

        # Enable zooming
        zoom_handler = FigureCanvas(self.figure)
        zoom_handler.mpl_connect("scroll_event", self.on_scroll)
        
        # Enable zooming by box selection for both axes
        self.rs1 = RectangleSelector(self.ax1, lambda eclick, erelease: self.on_select(eclick, erelease, self.ax1),
                                     useblit=True, button=[1], minspanx=5, minspany=5,
                                     spancoords='pixels', interactive=True)

        self.rs2 = RectangleSelector(self.ax2, lambda eclick, erelease: self.on_select(eclick, erelease, self.ax2),
                                     useblit=True, button=[1], minspanx=5, minspany=5,
                                     spancoords='pixels', interactive=True)

        # Connect double-click event to reset axis limits for both axes
        self.canvas.mpl_connect('button_press_event', self.on_double_click)
        right_layout.addWidget(self.canvas)
        self.figure.subplots_adjust(left=0.1, right=.97, top=.97, bottom=0.1, hspace=0.2)

        # Main layout
        main_layout = QGridLayout()
        main_layout.addWidget(left_panel, 0, 0)
        main_layout.addWidget(right_panel, 0, 1)

        main_widget = QWidget()
        main_widget.setLayout(main_layout)

        self.setCentralWidget(main_widget)

        # Connect signals
        self.load_button.clicked.connect(self.load_sbb_file)
        self.listbox1.itemSelectionChanged.connect(lambda : self.update_plot(self.listbox1, self.ax1))
        self.listbox2.itemSelectionChanged.connect(lambda : self.update_plot(self.listbox2, self.ax2))
        self.filter_checkbox.stateChanged.connect(self.update_allplot)

        self.data = None

        # Update Listboxes
        self.update_listboxes()

        # Set a specific style for the application (e.g., "Fusion", "Windows", "Macintosh")
        self.setStyle("Fusion")  # Replace "Fusion" with the desired style name

        # Create the digital filter
        self.filterb, self.filtera = butter(2,self.Fcut,btype="lowpass",fs=self.Fs)

    def setStyle(self, style):
        # Set a specific style for the application
        app = QApplication.instance()
        app.setStyle(style)
        # Force light palette
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, Qt.black)
        palette.setColor(QPalette.Base, Qt.white)
        palette.setColor(QPalette.AlternateBase, QColor(225, 225, 225))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.black)
        palette.setColor(QPalette.Text, Qt.black)
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, Qt.black)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        app.setPalette(palette)

    def set_axlabels(self):
        self.ax2.set_xlabel("Sample")
        self.ax1.set_ylabel("Signal(s)")
        self.ax2.set_ylabel("Signal(s)")

    def on_double_click(self, event):
        # Handle double-click event to reset axis limits
        if event.dblclick and event.button == 3:  # Check if right mouse button is double-clicked

            if self.data:
                self.reset_axlim(self.ax1, (0, self.data['sample'][-1]))
            else:
                self.reset_axlim(self.ax1, (0,1))

            if self.data:
                autoscale_y(self.ax1)
                autoscale_y(self.ax2)
            else:
                self.ax1.set_ylim(0,1)
                self.ax1.set_ylim(0,1)

            # Redraw the canvas
            self.canvas.draw()

    def on_select(self, eclick, erelease, ax):
        # Handle box selection for zooming for the specified axis
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata

        # Apply zoom to the specified axis
        ax.set_xlim(min(x1, x2), max(x1, x2))
        ax.set_ylim(min(y1, y2), max(y1, y2))

        # Redraw the canvas
        self.canvas.draw()

    def on_scroll(self, event):
        # Handle the scroll event for zooming
        if event.inaxes is not None and event.name == "scroll_event":
            if event.button == "up":
                self.ax1.set_xlim(self.ax1.get_xlim()[0] + 1000, self.ax1.get_xlim()[1] + 1000)
            elif event.button == "down":
                self.ax1.set_xlim(self.ax1.get_xlim()[0] - 1000, self.ax1.get_xlim()[1] - 1000)

        # Redraw the canvas
        self.canvas.draw()

    def update_listboxes(self):
        self.listbox1.clear()
        self.listbox2.clear()
        self.listbox1.addItems(self.signals)
        self.listbox2.addItems(self.signals)
        self.listbox1.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listbox2.setSelectionMode(QAbstractItemView.ExtendedSelection)


    def load_sbb_file(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Open .sbb File", "", "SBB Files (*.sbb)")

        if file_path:
            data = sbbimport(file_path, self.n, self.signals)

            if data:
                self.data = data
                self.update_allplot()
                self.reset_axlim(self.ax1, (0, self.data['sample'][-1]))
                
                
    def reset_axlim(self, ax, xlim):
        ax.set_xlim(xlim)
        self.canvas.draw()

    def update_allplot(self):
        self.update_plot(self.listbox1, self.ax1)
        self.update_plot(self.listbox2, self.ax2)

    def update_plot(self, listbox, ax):
        if self.data:
            selected_signals = [item.text() for item in listbox.selectedItems()]
            filter_enabled = self.filter_checkbox.isChecked()

            # Current xlim
            old_xlim = ax.get_xlim()
            
            # Clear the axes before plotting new data
            ax.clear()
            sample = self.data['sample']

            for signal_name, signal_data in self.data.items():
                # Plot signals based on selection and filter status
                if signal_name in selected_signals and not filter_enabled:
                    ax.plot(sample, signal_data, label=signal_name,linewidth=1)
                elif signal_name in selected_signals and filter_enabled:
                    signal_data = filtfilt(self.filterb, self.filtera, signal_data)
                    ax.plot(sample[::self.decim], signal_data[::self.decim], label=signal_name,linewidth=1)
            # Reset old limits
            self.reset_axlim(ax, old_xlim)

            # Set labels
            self.set_axlabels()

            # Show legend
            if self.data.items():
                ax.legend()

            # Redraw the canvas
            self.canvas.draw()