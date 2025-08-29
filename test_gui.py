import sys
from PyQt6.QtWidgets import QApplication, QWidget

if __name__ == '__main__':
    print("Attempting to launch PyQt6 application...")
    try:
        app = QApplication(sys.argv)
        window = QWidget()
        window.setWindowTitle('PyQt6 Test')
        window.setGeometry(100, 100, 200, 100)
        window.show()
        print("PyQt6 app window shown.")
        # In a non-blocking test, we can't call app.exec()
        # but the attempt to create QApplication is the key test.
        print("PyQt6 app launched successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

    sys.exit(0)
