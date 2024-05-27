"""
serial_connect.py

This script is used to manage serial communication in a Python application. It uses the PySerial library to handle
the communication.

The script defines a class, SerialManager, which is responsible for managing the serial communication. The class has
several methods:

- __init__(self, port, baud_rate, ui): This is the constructor method. It initializes the SerialManager with the
given port, baud rate, and user interface.

- start(self): This method starts the serial communication. It creates and starts a new thread to run the serial
communication.

- run(self): This method runs the serial communication. It reads and processes incoming data from the serial port.

- stop(self): This method stops the serial communication. It stops the running thread and closes the serial port.

- update_port(self, new_port): This method updates the port for the serial communication. If the new port is
different from the current port, it stops the current serial communication and starts a new one with the new port.

To use this script, you need to create an instance of the SerialManager class, passing the port, baud rate,
and user interface to the constructor. Then, you can use the start method to start the serial communication,
the stop method to stop it, and the update_port method to change the port."""
# Import necessary libraries
import serial
import threading
import time

# Define a global variable 'running' to control the running state of the serial communication
running = False


# Define a class 'SerialManager' to manage serial communication
class SerialManager:
    """
        Class to manage serial communication.
    """

    def __init__(self, port, baud_rate, ui):
        """
                Initialize the SerialManager with the given port, baud rate, and user interface.

                Parameters:
                - port: The port for serial communication.
                - baud_rate: The baud rate for serial communication.
                - ui: The user interface.
        """
        super().__init__()
        self.port = port  # The port for serial communication
        self.baud_rate = baud_rate  # The baud rate for serial communication
        self.ui = ui  # The user interface
        self.thread = None  # The thread for serial communication
        self.ser = None  # The serial communication object

    def start(self):
        """
                Start the serial communication. It creates and starts a new thread to run the serial communication.
        """
        global running
        if not running:
            running = True
            # Create and start a new thread for serial communication
            self.thread = threading.Thread(target=self.run, name="SerialCommunicationThread")
            self.thread.daemon = True
            self.thread.start()

    # Run the serial communication
    def run(self):
        """
                Run the serial communication. It reads and processes incoming data from the serial port.
        """
        from process_data import process_data
        while running:
            try:
                # Create a new serial communication object with the given port and baud rate
                with serial.Serial(self.port, self.baud_rate, timeout=1) as self.ser:
                    # Emit a signal indicating that the serial communication is connected
                    self.ui.serial_status_signal.emit(f"Serial connected on {self.port}", "green")
                    while running:
                        # If there is data waiting, read and process the data
                        if self.ser.in_waiting:
                            incoming_data = self.ser.read(self.ser.in_waiting)
                            for byte in incoming_data:
                                if self.ui.is_receiving_data:
                                    if not self.ui.is_ble_connected:
                                        process_data(byte, self.ui)
                                    elif self.ui.is_ble_connected and not self.ui.using_ble:
                                        process_data(byte, self.ui)
                            if not running:
                                self.ser.close()
                        time.sleep(0.01)

            except serial.SerialException:
                # If unable to connect to the serial communication, emit a signal
                self.ui.serial_status_signal.emit("Serial not connected", "red")
                time.sleep(5)
            except Exception as e:
                # If an error occurs during serial communication, print the error and emit a signal
                print("Error during serial communication:", e)
                self.ui.serial_status_signal.emit("Serial error", "red")

            finally:
                # Ensure the serial communication object is closed after ending
                if self.ser:
                    self.ser.close()

    def stop(self):
        """
                Stop the serial communication. It stops the running thread and closes the serial port.
        """
        global running
        running = False
        # Wait for the serial communication thread to end
        if self.thread and self.thread.is_alive():
            self.thread.join()
        # Ensure the serial communication object is closed
        if self.ser and self.ser.is_open:
            self.ser.close()

        # Print the names of all currently active threads
        for thread in threading.enumerate():
            print(thread.name)

    def update_port(self, new_port):
        """
                Update the port for the serial communication.

                Parameters:
                - new_port: The new port for serial communication.
        """
        # Print the names of all currently active threads
        for thread in threading.enumerate():
            print(thread.name)
        # If the new port is different from the current port, stop the current serial communication and start a new
        # one with the new port
        if new_port != self.port:
            self.stop()
            self.port = new_port
            self.start()
