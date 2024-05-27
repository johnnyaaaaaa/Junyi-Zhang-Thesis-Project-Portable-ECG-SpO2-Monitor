
# -*- coding: utf-8 -*-
import csv
import os
import threading
import time
from datetime import datetime

import serial.tools.list_ports
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import QMessageBox, QComboBox
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from bluetooth import BluetoothManager
from serial_connect import SerialManager


# Function to get the list of available serial ports
def get_serial_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]


class Ui_MainWindow(QtWidgets.QMainWindow):
    """
    Main window class for the GUI application.
    """
    # Define signals
    serial_status_signal = pyqtSignal(str, str)
    ble_end_status_signal = pyqtSignal(str)
    spo2_update_signal = pyqtSignal(str)
    ble_status_signal = QtCore.pyqtSignal(str, str)
    heart_rate_signal = QtCore.pyqtSignal(str)  # Signal to update heart rate in the GUI

    def __init__(self, parent=None):
        """
        Initialize the main window.
        """
        super(Ui_MainWindow, self).__init__(parent)
        # Initialize variables
        self.ble_thread = None
        self.ble_manager = None
        self.dialog = None
        self.using_ble = False
        self.is_ble_connected = False
        self.is_serial_connected = False
        self.radio_bluetooth = None
        self.serial_manager = None
        self.recording = False  # Recording status
        self.spo2_update_signal.connect(self.update_spo2_display)
        self.heart_rate_signal.connect(self.update_heart_rate_display)
        self.spo2_timer = QTimer(self)  # Ensure self is passed to manage the timer's lifecycle
        self.spo2_timer.timeout.connect(self.on_spo2_timer_timeout)
        self.last_valid_spo2 = "N/A"
        self.file_path = "ecg_ppg_log.csv"
        self.port = "COM11"
        self.plot_timer = QTimer(self)
        self.plot_timer.timeout.connect(self.reset_plot)
        self.plot_timer.start(6000)  # Reset the plot every 6 seconds
        self.ecg_data = []
        self.ir_data = []
        self.ecg_time_stamps = []
        self.ir_time_stamps = []
        self.start_time = time.time()
        self.count = 0
        self.is_receiving_data = False
        self.is_recording_data = False
        self.resolution_bits = 18
        self.setupUi(self)  # Pass self as MainWindow

        # Initialize the serial manager
        self.serial_manager = SerialManager(self.port, 57600, self)
        self.serial_manager.start()

    def setupUi(self, MainWindow):
        """
        Set up the user interface for the main window.
        """
        # Set up the main window
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.centralwidget.setStyleSheet("QWidget {"
                                         "    background-color: #dff3f7;"  # Set light blue background
                                         "}")

        # Set up the IR data plot
        self.ir_data_plot = QtWidgets.QWidget(self.centralwidget)
        self.ir_data_plot.setGeometry(QtCore.QRect(30, 20, 430, 220))
        self.ir_data_plot.setObjectName("data")
        self.ir_data_plot.setStyleSheet("QWidget {"
                                        "    border: 2px solid black;"  # Add black border
                                        "    border-radius: 10px;"  # Border radius
                                        "}")
        self.ir_figure = Figure()
        self.ir_canvas = FigureCanvas(self.ir_figure)
        self.ir_canvas.setParent(self.ir_data_plot)

        # Fill the ir_data widget with the canvas
        ir_layout = QtWidgets.QVBoxLayout(self.ir_data_plot)
        ir_layout.addWidget(self.ir_canvas)

        self.ir_ax = self.ir_figure.add_subplot(111)
        self.ir_ax.set_xlim(0, 6)  # Fixed 6-second window
        self.ir_ax.grid(True)
        self.ir_line, = self.ir_ax.plot([], [], 'b-')

        # Set up the ECG data plot
        self.ecg_data_plot = QtWidgets.QWidget(self.centralwidget)
        self.ecg_data_plot.setGeometry(QtCore.QRect(30, 300, 430, 220))
        self.ecg_data_plot.setObjectName("ecg_data")
        self.ecg_data_plot.setStyleSheet("QWidget {"
                                         "    border: 2px solid black;"  # Add black border
                                         "    border-radius: 10px;"  # Border radius
                                         "}")

        # Setup the matplotlib Figure and FigureCanvas
        self.ecg_figure = Figure()
        self.ecg_canvas = FigureCanvas(self.ecg_figure)
        self.ecg_canvas.setParent(self.ecg_data_plot)

        # Fill the ecg_data widget with the canvas
        ecg_layout = QtWidgets.QVBoxLayout(self.ecg_data_plot)
        ecg_layout.addWidget(self.ecg_canvas)

        self.ecg_ax = self.ecg_figure.add_subplot(111)
        self.ecg_ax.set_xlim(0, 6)  # Fixed 6-second window
        self.ecg_ax.grid(True)
        self.ecg_ax.set_xlabel('Time (s)')  # Set x-axis label
        self.ecg_ax.set_ylabel('Voltage (mV)')
        self.ecg_line, = self.ecg_ax.plot([], [], 'r-')

        # Set up the IR data label
        self.ir_label = QtWidgets.QLabel("IR Data", self.centralwidget)
        self.ir_label.setGeometry(QtCore.QRect(30, 245, 430, 20))  # Adjust position and size
        self.ir_label.setAlignment(QtCore.Qt.AlignCenter)  # Set text to align center
        self.ir_label.setStyleSheet("QLabel {"
                                    "  font-size: 16px; "  # Font size
                                    "  color: black; "  # Text color
                                    "  font-family: 'Arial'; "  # Set font to Arial
                                    "  font-weight: bold; "
                                    "}")

        # Set up the ECG data label
        self.ecg_label = QtWidgets.QLabel("ECG Data", self.centralwidget)
        self.ecg_label.setGeometry(QtCore.QRect(30, 525, 430, 20))  # Adjust position and size
        self.ecg_label.setAlignment(QtCore.Qt.AlignCenter)  # Set text to align center
        self.ecg_label.setStyleSheet("QLabel {"
                                     "  font-size: 16px; "  # Font size
                                     "  color: black; "  # Text color
                                     "  font-family: 'Arial'; "  # Set font to Arial
                                     "  font-weight: bold; "
                                     "}")

        # Set up the heart rate QTextBrowser
        self.heartrate = QtWidgets.QTextBrowser(self.centralwidget)
        self.heartrate.setGeometry(QtCore.QRect(480, 70, 271, 81))
        self.heartrate.setStyleSheet("QTextBrowser {\n"
                                     "  background-color: #ff9496;\n"
                                     "  color: #120108; \n"
                                     "  font-weight: bold; \n"
                                     "  font-family: \'Arial\'; \n"
                                     "  font-size: 20px; \n"
                                     "  text-align: center; \n"
                                     "border-radius: 15px;\n"
                                     "}")
        self.heartrate.setObjectName("heartrate")

        # Set up the SpO2 QTextBrowser
        self.spO2 = QtWidgets.QTextBrowser(self.centralwidget)
        self.spO2.setGeometry(QtCore.QRect(480, 170, 271, 81))
        self.spO2.setStyleSheet("QTextBrowser {\n"
                                "  background-color: rgb(143, 0, 2);\n"
                                "  color:#ffe6e9; /* Text color is white */\n"
                                "  font-weight: bold; /* Font is bold */\n"
                                "  font-family: \'Arial\'; \n"
                                "  text-align: center; \n"
                                "  border-radius: 15px;\n"
                                "}")
        self.spO2.setObjectName("spO2")

        # Set up the start QPushButton
        self.start_pb = QtWidgets.QPushButton(self.centralwidget)
        self.start_pb.setGeometry(QtCore.QRect(470, 20, 91, 31))
        self.start_pb.setStyleSheet("QPushButton {\n"
                                    "    background-color: green;\n"
                                    "    color: black;\n"
                                    "border-radius: 10px;          \n"
                                    "}\n"
                                    "QPushButton:hover {\n"
                                    "    background-color: #02ad66;  \n"
                                    "    color: black;              \n"
                                    "}")
        self.start_pb.setObjectName("start_pb")
        self.start_pb.clicked.connect(self.toggle_data_receiving)

        self.record_pb = QtWidgets.QPushButton(self.centralwidget)
        self.record_pb.setGeometry(QtCore.QRect(570, 20, 91, 31))
        self.record_pb.setStyleSheet("QPushButton {\n"
                                     "    background-color: rgb(0, 0, 127);\n"
                                     "    color: white;      \n"
                                     "border-radius: 10px;    \n"
                                     "}\n"
                                     "QPushButton:hover {\n"
                                     "    background-color: #0253a3;  \n"
                                     "    color: white;              \n"
                                     "}")
        self.record_pb.setObjectName("record_pb")
        self.record_pb.clicked.connect(self.toggle_recording)

        label_style = """
                        QLabel {
                            background-color: #f7f7f7;
                            color: #333;
                            font-family: 'Arial';
                            font-size: 14px;
                            border: 1px solid #ccc;
                            border-radius: 8px;
                            padding: 4px;
                            text-align: center;
                        }
                        """
        self.radio_bluetooth = QtWidgets.QRadioButton("Use Bluetooth Data", self.centralwidget)
        self.radio_serial = QtWidgets.QRadioButton("Use Serial Data", self.centralwidget)

        self.radio_bluetooth.setGeometry(QtCore.QRect(310, 530, 200, 20))
        self.radio_serial.setGeometry(QtCore.QRect(310, 560, 180, 20))
        self.hide_data_source_options()
        # 默认选择串口
        self.radio_serial.setChecked(True)
        self.button_group_data_source = QtWidgets.QButtonGroup(self.centralwidget)
        self.button_group_data_source.addButton(self.radio_bluetooth, 1)  # 1 for Bluetooth
        self.button_group_data_source.addButton(self.radio_serial, 2)  # 2 for Serial

        self.button_group_data_source.buttonClicked[int].connect(self.change_data_source)

        # 设置 ble_connection QLabel
        self.ble_connection = QtWidgets.QLabel(self.centralwidget)
        self.ble_connection.setGeometry(QtCore.QRect(510, 520, 271, 30))
        self.ble_connection.setObjectName("ble_connection")
        self.ble_connection.setStyleSheet(label_style)
        self.ble_status_signal.connect(self.update_ble_status)
        # 设置 serial_connection QLabel
        self.serial_connection = QtWidgets.QLabel(self.centralwidget)
        self.serial_connection.setGeometry(QtCore.QRect(510, 560, 271, 30))
        self.serial_connection.setObjectName("serial_connection")
        self.serial_connection.setStyleSheet(label_style)
        # 连接信号到一个槽，用于更新串口状态
        self.serial_status_signal.connect(self.update_serial_status)

        self.connect_BLE = QtWidgets.QPushButton(self.centralwidget)
        self.connect_BLE.setGeometry(QtCore.QRect(480, 350, 200, 40))  # 调整位置和大小
        self.connect_BLE.setStyleSheet("QPushButton {\n"
                                       "    background-color: #0307ff; \n"  # 默认背景颜色
                                       "    color: white; \n"  # 字体颜色
                                       "    font-weight: bold; \n"  # 字体加粗
                                       "    border-radius: 10px; \n"  # 边框圆角
                                       "}\n"
                                       "QPushButton:hover {\n"
                                       "    background-color: #3fa9f5; \n"  # 悬停时变为亮蓝色
                                       "    border: 2px solid #ffffff; \n"  # 添加白色边框
                                       "    box-shadow: 0 0 8px 0 rgba(255, 255, 255, 0.5); \n"  # 添加白色半透明阴影
                                       "}")
        self.connect_BLE.setObjectName("connect_BLE")
        self.connect_BLE.clicked.connect(lambda: self.open_ble_dialog(MainWindow))

        self.comboBox = QComboBox(self.centralwidget)
        self.comboBox.setGeometry(480, 270, 300, 50)
        ports = get_serial_ports()
        self.comboBox.addItem("Select port: ↓")  # 添加提示选项
        self.comboBox.addItems(ports)  # 添加串口列表
        self.comboBox.setCurrentIndex(0)  # 设置默认选项为选中状态
        self.comboBox.setStyleSheet("""
            QComboBox {
                font-family: 'Arial'; /* 设置字体 */
                font-size: 16px; /* 字体大小 */
                background-color: white; /* 背景色 */
                border: 1px solid #ccc; /* 边框样式 */
                border-radius: 5px; /* 边框圆角 */
                padding: 5px 10px 5px 5px; /* 内边距 */
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: right center; /* 下拉箭头的位置 */
                width: 30px; /* 下拉箭头的宽度 */
                border-left: 1px solid darkgray; /* 分隔线 */
            }
            
            QComboBox QAbstractItemView {
                background-color: #f0f0f0; /* 下拉列表的背景颜色 */
                selection-background-color: #a0a0a0; /* 选中项的背景颜色 */
            }
        """)

        # 显示当前选中的端口
        self.statusBar().showMessage(f"Selected Port: {self.comboBox.currentText()}")
        self.comboBox.currentIndexChanged.connect(self.port_update_status)
        self.serial_manager = SerialManager(self.port, 57600, self)
        self.serial_manager.start()

        # Styling for the radio buttons
        radio_button_style = """
                QRadioButton {
                    font-family: 'Arial';
                    font-size: 16px;
                    color: #333333;
                    padding: 5px;
                }
                QRadioButton::indicator {
                    width: 20px;
                    height: 20px;
                }
                QRadioButton::indicator::unchecked {
                    background-color: #ffffff;
                    border: 1px solid #cccccc;
                    border-radius: 10px;
                }
                QRadioButton::indicator::checked {
                    background-color: #4CAF50;
                    border: 1px solid #cccccc;
                    border-radius: 10px;
                }
                """

        # Adding radio buttons for measurement choice
        self.radio_finger = QtWidgets.QRadioButton("Fingerprint measure", self.centralwidget)
        self.radio_finger.setGeometry(QtCore.QRect(510, 430, 180, 40))
        self.radio_finger.setStyleSheet(radio_button_style)
        self.radio_finger.setObjectName("radio_finger")
        self.radio_finger.setChecked(True)  # Set as default selection

        self.radio_electrode = QtWidgets.QRadioButton("Electrode measure", self.centralwidget)
        self.radio_electrode.setGeometry(QtCore.QRect(510, 470, 180, 40))
        self.radio_electrode.setStyleSheet(radio_button_style)
        self.radio_electrode.setObjectName("radio_electrode")

        # Grouping radio buttons
        self.button_group = QtWidgets.QButtonGroup(self.centralwidget)
        self.button_group.addButton(self.radio_finger, 18)  # finger corresponds to 18-bit
        self.button_group.addButton(self.radio_electrode, 19)  # electrode corresponds to 19-bit

        # Connect signal
        self.button_group.buttonClicked[int].connect(self.change_adc_bits)
        self.ble_end_status_signal.connect(self.show_end_ble_message)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def show_end_ble_message(self, message):
        QtWidgets.QMessageBox.information(self, "Connection Status", message)
    def open_ble_dialog(self,MainWindow):
        if self.is_ble_connected:
            self.ble_manager.stop()
        else:
            self.dialog = BLEConnectionDialog(parent=MainWindow, ui=self)
            self.dialog.exec_()

    def update_ble_button(self):

        if self.is_ble_connected:
            # 蓝牙已连接时的按钮样式
            self.connect_BLE.setText("Disconnect BLE")
            self.connect_BLE.setStyleSheet("QPushButton {\n"
                                           "    background-color: #7d0000; \n"  # 默认背景颜色
                                           "    color: white; \n"  # 字体颜色
                                           "    font-weight: bold; \n"  # 字体加粗
                                           "    border-radius: 10px; \n"  # 边框圆角
                                           "}\n"
                                           "QPushButton:hover {\n"
                                           "    background-color: #c43e3e; \n"  # 悬停时变为亮蓝色
                                           "    border: 2px solid #ffffff; \n"  # 添加白色边框
                                           "    box-shadow: 0 0 8px 0 rgba(255, 255, 255, 0.5); \n"  # 添加白色半透明阴影
                                           "}")
        else:
            # 蓝牙未连接时的按钮样式
            self.connect_BLE.setText("Connect to BLE")
            self.connect_BLE.setStyleSheet("QPushButton {\n"
                                           "    background-color: #0307ff; \n"  # 默认背景颜色
                                           "    color: white; \n"  # 字体颜色
                                           "    font-weight: bold; \n"  # 字体加粗
                                           "    border-radius: 10px; \n"  # 边框圆角
                                           "}\n"
                                           "QPushButton:hover {\n"
                                           "    background-color: #3fa9f5; \n"  # 悬停时变为亮蓝色
                                           "    border: 2px solid #ffffff; \n"  # 添加白色边框
                                           "    box-shadow: 0 0 8px 0 rgba(255, 255, 255, 0.5); \n"  # 添加白色半透明阴影
                                           "}")


    def port_update_status(self):
        selected_port = self.comboBox.currentText()
        self.port = selected_port
        self.serial_manager.update_port(self.port)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.heartrate.setHtml(_translate("MainWindow",
                                          "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
                                          "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
                                          "p, li { white-space: pre-wrap; }\n"
                                          "</style></head><body style=\" font-family:\'Arial\'; font-size:8px; font-weight:600; font-style:normal;\">\n"
                                          "<p align=\"center\" style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'SimSun\'; font-size:12pt;\">heart rate: N\A</span></p></body></html>"))
        self.spO2.setHtml(_translate("MainWindow",
                                     "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
                                     "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
                                     "p, li { white-space: pre-wrap; }\n"
                                     "</style></head><body style=\" font-family:\'Arial\'; font-size:7pt; font-weight:600; font-style:normal;\">\n"
                                     "<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'SimSun\'; font-size:18pt;\">SpO2: N/A </span></p></body></html>"))
        self.start_pb.setText(_translate("MainWindow", "start"))
        self.record_pb.setText(_translate("MainWindow", "record"))
        self.ble_connection.setText(_translate("MainWindow", "bluetooth not connected"))
        self.serial_connection.setText(_translate("MainWindow", "serial not connected"))
        self.connect_BLE.setText(_translate("MainWindow", "connect to BLE"))

    def update_serial_status(self, text, color):
        # 更新 QLabel 文本和颜色
        if color == "red":
            self.is_serial_connected = False
        else:
            self.is_serial_connected = True
        if self.is_serial_connected and self.is_ble_connected:
            self.show_data_source_options()
        else:
            self.hide_data_source_options()
        self.serial_connection.setText(text)
        # 更新 QLabel 文本和颜色，并确保样式一致
        self.serial_connection.setText(text)
        self.serial_connection.setStyleSheet(f"""
                    QLabel {{
                        background-color: #f7f7f7;
                        color: {color};
                        font-family: 'Arial';
                        font-size: 14px;
                        border: 1px solid #ccc;
                        border-radius: 8px;
                        padding: 4px;
                        text-align: center;
                    }}
                """)

    def update_ble_status(self, text, color):
        if color == "red":
            self.is_ble_connected = False
        else:
            self.is_ble_connected = True
        if self.is_serial_connected and self.is_ble_connected:
            self.show_data_source_options()
        else:
            self.hide_data_source_options()

        self.update_ble_button()

        # 更新 QLabel 文本和颜色
        self.ble_connection.setText(text)
        # 更新 QLabel 文本和颜色，并确保样式一致
        self.ble_connection.setText(text)
        self.ble_connection.setStyleSheet(f"""
                    QLabel {{
                        background-color: #f7f7f7;
                        color: {color};
                        font-family: 'Arial';
                        font-size: 14px;
                        border: 1px solid #ccc;
                        border-radius: 8px;
                        padding: 4px;
                        text-align: center;
                    }}
                """)

    def toggle_data_receiving(self):
        self.is_receiving_data = not self.is_receiving_data  # 切换状态
        if self.is_receiving_data:
            self.start_pb.setText("Stop")
            self.start_pb.setStyleSheet("QPushButton {"
                                        "    background-color: #8c1b07;"  # 设置背景为红色
                                        "    color: white;"  # 设置文字颜色为白色
                                        "    border-radius: 10px;"  # 保持圆角样式
                                        "}"
                                        "QPushButton:hover {\n"
                                        "    background-color: #af4747;  \n"
                                        "    color: black;              \n"
                                        "}"
                                        )
        else:
            self.start_pb.setText("Start")
            self.start_pb.setStyleSheet("QPushButton {"
                                        "    background-color: green;"  # 设置背景为绿色
                                        "    color: black;"  # 设置文字颜色为黑色
                                        "    border-radius: 10px;"  # 保持圆角样式
                                        "}"
                                        "QPushButton:hover {\n"
                                        "    background-color: #02ad66;  \n"
                                        "    color: black;              \n"
                                        "}"
                                        )

    def toggle_recording(self):
        if not self.is_recording_data:
            self.record_pb.setText("Stop")
            self.record_pb.setStyleSheet("QPushButton {"
                                         "    background-color: #8c1b07;"  # 设置背景为红色
                                         "    color: white;"  # 设置文字颜色为白色
                                         "    border-radius: 10px;"  # 保持圆角样式
                                         "}"
                                         "QPushButton:hover {\n"
                                         "    background-color: #af4747;  \n"
                                         "    color: black;              \n"
                                         "}"
                                         )
            self.start_recording()
        else:
            self.record_pb.setText("Record")
            self.record_pb.setStyleSheet("QPushButton {\n"
                                         "    background-color: rgb(0, 0, 127);\n"
                                         "    color: white;      \n"
                                         "border-radius: 10px;    \n"
                                         "}\n"
                                         "QPushButton:hover {\n"
                                         "    background-color: #0253a3;  \n"
                                         "    color: white;              \n"
                                         "}")
            self.stop_recording()

    def start_recording(self):
        self.file_path = 'ecg_ppg_log.csv'
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Recording")
        msg_box.setText(f"<h2>Recording Started</h2><p>Recording data will be saved to:<br><b>{self.file_path}</b></p>")
        msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #f2f2f2;
                    color: #333;
                    font-family: Arial;
                    font-size: 14px;
                    width: 2000px; /* Widen the message box */
                }
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 5px;
                    padding: 15px 20px; /* Bigger buttons */
                    font-size: 16px; /* Larger font size for the buttons */
                    margin: 10px 5px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        msg_box.exec_()
        self.is_recording_data = True

    def stop_recording(self):
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Recording")
        msg_box.setText("Recording stopped.")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #f2f2f2;
                    color: #333;
                    font-family: 'Arial';
                    font-size: 14px;
                }
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 5px;
                    padding: 10px;
                    font-size: 16px;
                    margin: 4px 2px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        msg_box.exec_()
        self.is_recording_data = False

    def record_data(self, ecg, ir, red, spo2):
        # 检查文件是否存在，如果不存在则添加标题
        headers = ["Timestamp", "ECG", "IR", "RED", "SpO2"]
        file_exists = os.path.exists(self.file_path)  # 使用self.file_path

        with open(self.file_path, mode='a', newline='') as file:
            writer = csv.writer(file)
            # 如果文件不存在，则写入列标题
            if not file_exists:
                writer.writerow(headers)

            # 写入实际的数据
            formatted_spo2 = spo2 if spo2 is not None else 'N/A'  # 处理None情况，显示为'N/A'
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ecg,
                ir,
                red,
                formatted_spo2
            ])

    def change_adc_bits(self, adc_bits):
        global resolution_bits
        # Update ADC bit setting based on selected radio button
        resolution_bits = adc_bits

    def add_data(self, ecg_data, ir_data):
        current_time = time.time()
        if self.start_time is None:
            self.start_time = current_time

        elapsed_time = current_time - self.start_time
        self.count += 1
        self.ir_data.append(ir_data)
        self.ecg_data.append(ecg_data)
        self.ecg_time_stamps.append(elapsed_time)
        self.ir_time_stamps.append(elapsed_time)
        if elapsed_time > 6:
            self.reset_plot()
        else:
            self.update_plot()

    def update_plot(self):
        self.ecg_line.set_data(self.ecg_time_stamps, self.ecg_data)
        self.ir_line.set_data(self.ir_time_stamps, self.ir_data)
        if len(self.ecg_data) > 0:
            min_val = min(self.ecg_data) - 1
            max_val = max(self.ecg_data) + 1
            if min_val == max_val:
                # 如果最小值和最大值相同，则人为地扩展范围
                min_val -= 0.1  # 例如，可以减少最小值的0.1
                max_val += 0.1  # 增加最大值的0.1
            self.ecg_ax.set_ylim(min_val, max_val)
        else:
            # 如果没有数据，则设置一个默认范围
            self.ecg_ax.set_ylim(0, 10)
        self.ecg_canvas.draw_idle()

        if len(self.ir_data) > 0:
            min_val = min(self.ir_data) - 10
            max_val = max(self.ir_data) + 10
            if min_val == max_val:
                # 如果最小值和最大值相同，则人为地扩展范围
                min_val -= 0.1  # 例如，可以减少最小值的0.1
                max_val += 0.1  # 增加最大值的0.1
            self.ir_ax.set_ylim(min_val, max_val)
        else:
            # 如果没有数据，则设置一个默认范围
            self.ir_ax.set_ylim(0, 10)
        self.ir_canvas.draw_idle()

    def reset_plot(self):

        print(self.count)
        self.count = 0
        self.ecg_data = []
        self.ecg_time_stamps = []
        self.start_time = time.time()  # 重置起始时间
        self.ecg_line.set_data([], [])
        self.ecg_canvas.draw_idle()

        self.ir_data = []
        self.ir_time_stamps = []
        self.start_time = time.time()  # 重置起始时间
        self.ir_line.set_data([], [])
        self.ir_canvas.draw_idle()

    def update_heart_rate_display(self, heart_rate_value):
        """Update the heart rate QTextBrowser with new value"""
        heart_rate_text = f"Heart Rate: {heart_rate_value} bpm"
        self.heartrate.setText(heart_rate_text)

    def update_spo2_display(self, spo2_value):
        """ Update the SpO2 QTextBrowser with new value """
        if spo2_value != "SpO2: N/A":
            spo2_text = spo2_value
            self.spO2.setText(spo2_text)
            self.spO2.setStyleSheet("QTextBrowser {\n"
                                    "  background-color: rgb(143, 0, 2);\n"
                                    "  color:#ffe6e9; /* 文字颜色为白色 */\n"
                                    "  font-size: 18pt;\n"
                                    "  font-weight: bold; /* 字体加粗 */\n"
                                    "  font-family: \'Arial\'; \n"
                                    "  text-align: center; \n"
                                    "  border-radius: 15px;\n"
                                    "}")
            self.last_valid_spo2 = spo2_text
            if self.spo2_timer.isActive():  # 检查计时器是否激活
                self.spo2_timer.stop()  # 如果计时器还在运行，停止它
        else:

            if not self.spo2_timer.isActive():  # 只有当计时器不在运行时才进行处理
                self.spO2.setText(self.last_valid_spo2)  # 显示最后有效的值
                self.spo2_timer.start(2000)  # 开始计时器，3秒后改变显示

    def on_spo2_timer_timeout(self):
        self.spO2.setText("SpO2: N/A")  # 计时结束后设置显示为"N/A"
        self.spO2.setStyleSheet("QTextBrowser {\n"
                                "  background-color: rgb(143, 0, 2);\n"
                                "  color:#ffe6e9; /* 文字颜色为白色 */\n"
                                "  font-size: 18pt;\n"
                                "  font-weight: bold; /* 字体加粗 */\n"
                                "  font-family: \'Arial\'; \n"
                                "  text-align: center; \n"
                                "  border-radius: 15px;\n"
                                "}")
        self.spo2_timer.start(2000)  # 确保停止计时器

    def change_data_source(self, id):
        if id == 1:
            self.using_ble = True
            # 逻辑代码切换到蓝牙数据处理
        elif id == 2:
            self.using_ble = False

    def hide_data_source_options(self):
        self.radio_bluetooth.hide()
        self.radio_serial.hide()

    def show_data_source_options(self):
        self.radio_bluetooth.show()
        self.radio_serial.show()


class BLEConnectionDialog(QtWidgets.QDialog, ):
    update_status_signal = QtCore.pyqtSignal(str)

    def __init__(self, parent=None, ui=None):
        super(BLEConnectionDialog, self).__init__(parent)
        self.ui = ui
        self.manager = None
        self.setWindowTitle("Connect to Bluetooth")
        self.setFixedSize(500, 400)  # Updated size
        layout = QtWidgets.QVBoxLayout()

        self.mac_address_input = QtWidgets.QLineEdit(self)
        self.mac_address_input.setPlaceholderText("Enter MAC address")
        layout.addWidget(self.mac_address_input)

        self.device_name_input = QtWidgets.QLineEdit(self)
        self.device_name_input.setPlaceholderText("Enter Device Name")
        layout.addWidget(self.device_name_input)

        self.uuid_input = QtWidgets.QLineEdit(self)
        self.uuid_input.setPlaceholderText("Enter UUID")
        layout.addWidget(self.uuid_input)

        self.scan_button = QtWidgets.QPushButton("Scan", self)
        self.scan_button.clicked.connect(self.scan_for_devices)
        layout.addWidget(self.scan_button)

        self.connect_default_button = QtWidgets.QPushButton("Connect Default", self)
        self.connect_default_button.clicked.connect(self.connect_to_default_device)
        layout.addWidget(self.connect_default_button)

        self.connect_button = QtWidgets.QPushButton("Connect", self)
        self.connect_button.clicked.connect(self.connect_to_custom_device)
        layout.addWidget(self.connect_button)

        self.setLayout(layout)
        self.apply_style()

    def scan_for_devices(self):
        def thread_target():
            device_name = self.device_name_input.text()
            self.ui.ble_manager = BluetoothManager(device_name=device_name, mac_address=None, uuid=None, ui=self.ui,
                                            dialog=self)
            self.update_status_signal.connect(self.show_status_message)
            self.ui.ble_manager.start_scan()
        self.ui.ble_thread = threading.Thread(target=thread_target)
        self.ui.ble_thread.daemon = True
        self.ui.ble_thread.start()

    def connect_to_custom_device(self):
        mac_address = self.mac_address_input.text()
        device_name = self.device_name_input.text()
        uuid = self.uuid_input.text()
        self.start_bluetooth_thread(mac_address, device_name, uuid)

    def connect_to_default_device(self):
        mac_address = "09:65:01:0b:5e:7e"
        uuid = "0000ffe1-0000-1000-8000-00805f9b34fb"
        self.start_bluetooth_thread(mac_address, None, uuid)

    def show_status_message(self, message):
        QtWidgets.QMessageBox.information(self, "Connection Status", message)

    def start_bluetooth_thread(self, mac_address, device_name, uuid):
        def thread_target():

            self.ui.ble_manager = BluetoothManager(device_name=device_name, mac_address=mac_address, uuid=uuid, ui=self.ui,
                                            dialog=self)
            self.update_status_signal.connect(self.show_status_message)
            self.ui.ble_manager.start()

        self.ui.ble_thread = threading.Thread(target=thread_target)
        self.ui.ble_thread.daemon = True
        self.ui.ble_thread.start()

    def apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f2f2f2;
            }
            QLineEdit {
                padding: 12px;  # Increased padding
                border: 2px solid #ccc;  # Increased border thickness
                border-radius: 4px;
                margin-bottom: 15px;  # Increased margin
                font-size: 16px;  # Larger font size
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                padding: 10px 15px;
                font-size: 16px;
                margin-top: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)


def get_serial_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]
