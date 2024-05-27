"""
This module handles the processing of serial data for a medical monitoring device, specifically focusing on the
acquisition and processing of ECG and SpO2 data. It includes functions to convert ADC values to voltages, and
a state machine to handle the custom packet-based communication protocol used for transmitting physiological data.

Key Components:
- State Machine: Manages the reception of data packets from a serial connection, parsing them according to
  a specific protocol defined by start bytes, length, and type fields.
- Data Conversion: Converts ADC readings to voltages for further processing.
- ECG and SpO2 Processing: Utilizes the ECGRespirationAlgorithm and the estimate_spo2 function to process
  the incoming data for real-time monitoring and analysis.

The module also defines packet constants, initializes global variables for packet processing, and maintains
lists of samples for time-series analysis. It interfaces with a user interface module to update displays and
emit status signals based on processed data.

Dependencies:
- heartrate_algorithm: Contains the ECGRespirationAlgorithm class for processing ECG signals.
- spo2_algorithm: Includes the estimate_spo2 function to calculate SpO2 from IR and red light sensor data.
- numpy: Used for numerical operations, especially in the handling of data lists and conversion calculations.

This script is typically employed in settings where continuous monitoring of patients is required, such as
hospitals or personal health monitoring devices. It is designed to run on systems that support Python execution
and have the necessary hardware interfaces for receiving serial data.
"""

from heartrate_algorithm import ECGRespirationAlgorithm
from spo2_algorithm import estimate_spo2
import numpy as np

# Packet state constants for managing data packet reception
CESState_Init = 0
CESState_SOF1_Found = 1
CESState_SOF2_Found = 2
CESState_PktLen_Found = 3

# Constants for packet identification and handling
CES_CMDIF_PKT_START_1 = 0x0A
CES_CMDIF_PKT_START_2 = 0xFA
CES_CMDIF_PKT_STOP = 0x0B
CES_CMDIF_IND_LEN = 2
CES_CMDIF_IND_LEN_MSB = 3
CES_CMDIF_IND_PKTTYPE = 4
CES_CMDIF_PKT_OVERHEAD = 5

# Initialize global variables
CES_Data_Counter = 0
CES_Pkt_Len = 0
CES_Pkt_PktType = 0
ecg_value = 0
ir_value = 0
red_value = 0
BUFFER_SIZE = 100  # Buffer size for data storage
ecg_mV = 0
pc_rx_state = CESState_Init  # Initial state of the packet receiver
CES_Pkt_Pos_Counter = 0
CES_Pkt_Data_Counter = [0, 0, 0, 0, 0, 0]
ir_samples = []  # List to store IR samples
red_samples = []  # List to store Red light samples
ecg_samples = []
heart_rate = None
ecg_processor = ECGRespirationAlgorithm()


def process_data(rx_char, ui):
    """
        Processes incoming serial data based on a state machine to parse custom packets for a medical device.

        This function manages state transitions based on incoming bytes (rx_char) to construct data packets that
        include physiological parameters such as ECG and SpO2. Upon successfully receiving a complete packet,
        the function updates global variables and UI components with new data, and resets its state to be ready
        for the next packet.

        Parameters:
        - rx_char: The next byte received from the serial interface, representing part of a data packet.
        - ui: A reference to the user interface object, which allows the function to update the UI and emit signals
          based on received data.

        Global Variables:
        - pc_rx_state: Current state of the packet processing state machine.
        - CES_Pkt_Pos_Counter, CES_Pkt_Data_Counter, CES_Pkt_Len, CES_Pkt_PktType: Variables to manage packet parsing.
        - ecg_value, ir_value, red_value, ecg_mV: Variables to store the latest values of physiological parameters.
        - ecg_samples, ir_samples, red_samples: Lists to store time series data for plotting or analysis.
        - heart_rate: Variable to store the latest calculated heart rate.

        The function utilizes a state machine with states for packet initialization (CESState_Init), start-of-frame
        detection (CESState_SOF1_Found, CESState_SOF2_Found), packet length and type reading (CESState_PktLen_Found),
        and data handling to extract and convert packet data into meaningful physiological measurements.
        """
    # Global variable declaration for shared state and data across function calls
    global pc_rx_state, CES_Pkt_Pos_Counter, ecg_value, ir_value, red_value, CES_Data_Counter, CES_Pkt_Len
    global CES_Pkt_PktType, ecg_mV, ecg_samples, ir_samples, red_samples, heart_rate, ecg_mV

    # Initial state: looking for the first byte of the packet start sequence
    if pc_rx_state == CESState_Init:
        if rx_char == CES_CMDIF_PKT_START_1:
            pc_rx_state = CESState_SOF1_Found

    # State after finding the first start byte, looking for the second
    elif pc_rx_state == CESState_SOF1_Found:
        if rx_char == CES_CMDIF_PKT_START_2:
            pc_rx_state = CESState_SOF2_Found
        else:
            pc_rx_state = CESState_Init  # Reset to initial if the sequence breaks

    # State after finding the start sequence, next byte should be packet length
    elif pc_rx_state == CESState_SOF2_Found:
        pc_rx_state = CESState_PktLen_Found
        CES_Pkt_Len = rx_char
        CES_Pkt_Pos_Counter = CES_CMDIF_IND_LEN
        CES_Data_Counter = 0

    # Reading the packet length and type
    elif pc_rx_state == CESState_PktLen_Found:
        CES_Pkt_Pos_Counter += 1
        if CES_Pkt_Pos_Counter < CES_CMDIF_PKT_OVERHEAD:
            if CES_Pkt_Pos_Counter == CES_CMDIF_IND_LEN_MSB:
                CES_Pkt_Len = (rx_char << 8) | CES_Pkt_Len  # Update packet length with MSB
            elif CES_Pkt_Pos_Counter == CES_CMDIF_IND_PKTTYPE:
                CES_Pkt_PktType = rx_char  # Update packet type
        elif CES_CMDIF_PKT_OVERHEAD <= CES_Pkt_Pos_Counter < CES_CMDIF_PKT_OVERHEAD + CES_Pkt_Len + 1:
            if CES_Pkt_PktType == 2:  # Specific packet type processing
                if CES_Data_Counter < len(CES_Pkt_Data_Counter):
                    CES_Pkt_Data_Counter[CES_Data_Counter] = rx_char
                    CES_Data_Counter += 1

        # Check for packet completion
        else:
            if rx_char == CES_CMDIF_PKT_STOP:
                # Processing received data
                ecg_value = CES_Pkt_Data_Counter[0] | (CES_Pkt_Data_Counter[1] << 8)
                ir_value = CES_Pkt_Data_Counter[2] | (CES_Pkt_Data_Counter[3] << 8)
                red_value = CES_Pkt_Data_Counter[4] | (CES_Pkt_Data_Counter[5] << 8)
                ecg_mV = adc_to_voltage(ecg_value, ui.resolution_bits)
                ecg_samples.append(ecg_mV)
                ecg_processor.QRS_algorithm_interface(ecg_value)
                heart_rate = ecg_processor.heart_rate
                ui.add_data(ecg_mV, ir_value)
                ecg_samples.append(ecg_mV)
                ir_samples.append(ir_value)
                red_samples.append(red_value)

                if len(ir_samples) > BUFFER_SIZE:
                    ir_samples.pop(0)
                if len(red_samples) > BUFFER_SIZE:
                    red_samples.pop(0)

                # Update UI and record data
                spo2_value = None
                if len(ir_samples) >= BUFFER_SIZE and len(red_samples) >= BUFFER_SIZE:
                    spo2_value, heart_rate = estimate_spo2(ir_samples[-BUFFER_SIZE:], red_samples[-BUFFER_SIZE:])
                    if 60 <= heart_rate <= 140:
                        ui.heart_rate_signal.emit(str(int(heart_rate)))  # Emit heart rate
                    if spo2_value is not None:
                        spo2_text = f"SpO2: {spo2_value}%"
                    else:
                        spo2_text = "SpO2: N/A"
                    ui.spo2_update_signal.emit(spo2_text)
                if ui.is_recording_data:
                    ui.record_data(adc_to_voltage(ecg_value, ui.resolution_bits), ir_value, red_value, spo2_value)

                # Reset state and counters for the next packet
                pc_rx_state = CESState_Init
                CES_Data_Counter = 0
            else:
                # If packet does not end correctly, reset to initial state
                pc_rx_state = CESState_Init


def adc_to_voltage(adc_value, resolution_bits):
    """
    Converts an ADC value to a corresponding voltage in millivolts.

    This function takes a digital value from an ADC (Analog to Digital Converter)
    and converts it to the corresponding analog voltage in millivolts. The conversion
    depends on the reference voltage and the resolution of the ADC.

    Parameters:
    - adc_value: The digital value read from the ADC, which is to be converted to voltage.
    - resolution_bits: The bit resolution of the ADC. This determines the number of discrete
                       digital values that the ADC can output.

    Returns:
    - voltage_mv: The calculated voltage in millivolts corresponding to the adc_value.

    The formula used for conversion is:
        voltage = (adc_value / max_adc_value) * v_ref
    where max_adc_value is derived from the resolution of the ADC (2^resolution_bits - 1),
    and v_ref is the reference voltage for the ADC.
    """
    v_ref = 1.8  # Reference voltage for the ADC in volts
    max_adc_value = (1 << resolution_bits) - 1  # Calculates the maximum ADC value based on resolution
    voltage = (adc_value / max_adc_value) * v_ref  # Converts the ADC value to a voltage
    voltage_mv = voltage * 1000  # Convert voltage from volts to millivolts

    return voltage_mv

