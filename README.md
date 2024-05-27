# Portable ECG and SpO2 Monitoring System

This repository contains the code and resources for Junyi Zhang's thesis project on developing a portable ECG and SpO2 monitoring system. The system is designed to provide real-time health monitoring capabilities, integrating both hardware and software components.

## Repository Structure

- **/python/** - Contains all Python files used for the GUI of the monitoring system. This includes:
  - `gui.py` - Main GUI application script.
  - `bluetooth.py` - Handles Bluetooth connectivity.
  - `heartrate_algorithm.py` - Algorithm for calculating heart rate.
  - `main.py` - Entry point for the GUI application.
  - `process_data.py` - Processes the data received from the hardware.
  - `serial_connect.py` - Manages serial connections.
  - `spo2_algorithm.py` - Algorithm for calculating blood oxygen saturation (SpO2).

- **/hardware/** - Contains the hardware design files:
  - `max86150.ino` - Arduino sketch for interfacing with the MAX86150 sensor used to capture ECG and SpO2 data.

- **main.zip** - An executable file containing the integrated GUI application. This is a standalone executable for Windows that encapsulates the entire GUI, making it easy to deploy and use without installing Python or other dependencies.

## How to Use

### Setting Up the Hardware

1. Navigate to the `/hardware/` folder.
2. Upload the `max86150.ino` file to your compatible Arduino device using the Arduino IDE or another AVR chip programming tool.
3. Ensure the hardware connections are set up as per the diagrams included in the thesis document.

### Running the GUI Application

- **Using Python Scripts:**
  1. Ensure Python 3.x is installed on your system. You can download it from [python.org](https://www.python.org/).
  2. Install required Python libraries by running `pip install -r requirements.txt` (a requirements file should be added if not already present).
  3. Run `main.py` from the `/python/` directory to start the GUI application.

- **Using the Standalone Executable:**
  1. Extract the `main.zip` file to a convenient location on your Windows computer.
  2. Double-click the extracted executable to run the application without the need for additional setup.

### Data Sharing and Connectivity

- The system is designed to support both USB and Bluetooth connectivity for data transmission. Ensure your device is properly paired and connected before starting the monitoring session.
- The GUI provides real-time data visualization and logging options for both ECG and SpO2, allowing users to monitor their health status effectively.