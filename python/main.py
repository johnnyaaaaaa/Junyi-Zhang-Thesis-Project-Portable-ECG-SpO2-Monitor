from PyQt5 import QtWidgets
import sys
import threading

# Import the UI setup from the gui module
from gui import Ui_MainWindow
# Import the data processing function from process_data module
from process_data import process_data

if __name__ == "__main__":
    # Initialize a Qt application
    app = QtWidgets.QApplication(sys.argv)
    # Create a main window object
    MainWindow = QtWidgets.QMainWindow()
    # Create a UI object from our defined class
    ui = Ui_MainWindow()
    # Set up the user interface
    ui.setupUi(MainWindow)
    # Display the main window
    MainWindow.show()
    # Start the event loop for the application
    sys.exit(app.exec_())