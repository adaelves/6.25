import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton

def main():
    app = QApplication(sys.argv)
    window = QMainWindow()
    button = QPushButton("Test Button")
    window.setCentralWidget(button)
    window.show()
    return app.exec() 