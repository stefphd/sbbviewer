import sys
from PySide6.QtWidgets import QApplication

from sbbviewer import SBBViewer

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SBBViewer()
    window.show()
    sys.exit(app.exec())
