"""
heartrate_algorithm.py

This script is used to implement the ECG Respiration Algorithm in a Python application. It uses the numpy library for
numerical operations.

The script defines a class, ECGRespirationAlgorithm, which is responsible for managing the ECG Respiration Algorithm.
The class has several methods:

- __init__(self): This is the constructor method. It initializes the ECGRespirationAlgorithm with the necessary
variables.

- process_current_sample(self, current_sample): This method processes the current sample and returns the filtered
output.

- QRS_algorithm_interface(self, curr_sample): This method is the interface for the QRS algorithm. It processes the
current sample.

- QRS_process_buffer(self): This method processes the buffer to detect QRS complex.

- QRS_check_sample_crossing_threshold(self, scaled_result): This method checks if the sample crosses the threshold.

- calculate_heart_rate(self): This method calculates the heart rate.

- handle_no_peak(self): This method handles the situation when no peak is detected.

- reset_variables(self): This method resets the variables.

To use this script, you need to create an instance of the ECGRespirationAlgorithm class. Then, you can use the
process_current_sample method to process the current sample, the QRS_algorithm_interface method to process the
current sample with the QRS algorithm, and the other methods as needed."""
import numpy as np

# Constants
FILTER_ORDER = 161
MAX_PEAK_TO_SEARCH = 4
TWO_SEC_SAMPLES = 125 * 2
MAXIMA_SEARCH_WINDOW = 50
MINIMUM_SKIP_WINDOW = 30
SAMPLING_RATE = 125
NRCOEFF = 3  # Assume this value based on your setup

CoeffBuf_40Hz_LowPass = np.array([
    -72, 122, -31, -99, 117, 0, -121, 105, 34,
    -137, 84, 70, -146, 55, 104, -147, 20, 135,
    -137, -21, 160, -117, -64, 177, -87, -108, 185,
    -48, -151, 181, 0, -188, 164, 54, -218, 134,
    112, -238, 90, 171, -244, 33, 229, -235, -36,
    280, -208, -115, 322, -161, -203, 350, -92, -296,
    361, 0, -391, 348, 117, -486, 305, 264, -577,
    225, 445, -660, 93, 676, -733, -119, 991, -793,
    -480, 1486, -837, -1226, 2561, -865, -4018, 9438, 20972,
    9438, -4018, -865, 2561, -1226, -837, 1486, -480, -793,
    991, -119, -733, 676, 93, -660, 445, 225, -577,
    264, 305, -486, 117, 348, -391, 0, 361, -296,
    -92, 350, -203, -161, 322, -115, -208, 280, -36,
    -235, 229, 33, -244, 171, 90, -238, 112, 134,
    -218, 54, 164, -188, 0, 181, -151, -48, 185,
    -108, -87, 177, -64, -117, 160, -21, -137, 135,
    20, -147, 104, 55, -146, 70, 84, -137, 34,
    105, -121, 0, 117, -99, -31, 122, -72
])


def ecg_filter_process(working_buff, coeff_buf):
    """
    Process the ECG filter.

    Parameters:
    - working_buff: The working buffer.
    - coeff_buf: The coefficient buffer.

    Returns:
    - filter_out: The output of the filter.
    """
    # Perform the multiply-accumulate operation using dot product
    acc = np.dot(coeff_buf, working_buff)
    filtered_output = np.convolve(working_buff, coeff_buf, 'valid')

    acc = int(acc)  # Convert to Python native int

    # Saturate the result to emulate fixed-point overflow behavior
    acc = max(min(acc, 0x3fffffff), -0x40000000)

    # Convert from Q30 to Q15 by right shifting 15
    filter_out = np.int16(acc >> 15)

    return filter_out


class ECGRespirationAlgorithm:
    """
    Class to implement the ECG Respiration Algorithm.
    """

    def __init__(self):
        """
        Initialize the ECGRespirationAlgorithm.
        """
        self.ecg_buffer = np.zeros(FILTER_ORDER)
        self.resp_buffer = np.zeros(FILTER_ORDER)

        self.first_flag = True
        self.buf_start = 0
        self.buf_cur = FILTER_ORDER - 1
        self.prev_dc_sample = 0
        self.prev_sample = 0

        self.max = 0
        self.qrs_b4_buffer_ptr = 0
        self.qrs_threshold_old = 0
        self.qrs_threshold_new = 0
        self.first_peak_detected = False
        self.heart_rate = 0
        self.qrs_samples = [0] * 5  # For QRS_Second_Prev_Sample to QRS_Second_Next_Sample
        self.prev_data = np.zeros(32, dtype=np.int16)

        self.sample_count = 0
        self.nopeak_count = 0
        self.maxima_search = 0
        self.peak = 0
        self.maxima_sum = 0
        self.sample_index = np.zeros(MAX_PEAK_TO_SEARCH + 2, dtype=int)
        self.s_array_index = 0
        self.m_array_index = 0
        self.threshold_crossed = False
        self.peak_detected = False
        self.first_peak_detect = False
        self.heart_rate = 0
        self.start_sample_count_flag = False
        self.sample_sum = 0

    def process_current_sample(self, current_sample):
        """
        Process the current sample.

        Parameters:
        - current_sample: The current sample to process.

        Returns:
        - filtered_output: The output after processing.
        """
        # Initialize on first run
        if self.first_flag:
            self.ecg_buffer.fill(0)
            self.prev_dc_sample = 0
            self.prev_sample = 0
            self.first_flag = False

        # First order IIR filter
        temp1 = NRCOEFF * self.prev_dc_sample
        self.prev_dc_sample = (current_sample - self.prev_sample) + temp1
        self.prev_sample = current_sample
        ecg_data = self.prev_dc_sample / 4

        # Store the DC removed value in the working buffer
        self.ecg_buffer[self.buf_start] = ecg_data

        # Prepare data for filtering
        filtered_output = ecg_filter_process(self.ecg_buffer, CoeffBuf_40Hz_LowPass)

        # Rotate the buffer
        self.buf_start += 1

        # Wrap the circular buffer pointers
        if self.buf_start == FILTER_ORDER:
            self.buf_start = 0

        return filtered_output

    def QRS_algorithm_interface(self, curr_sample):
        """
        Interface for the QRS algorithm.

        Parameters:
        - curr_sample: The current sample to process.
        """
        # Shift previous data for new incoming sample
        self.prev_data[1:] = self.prev_data[:-1]
        self.prev_data[0] = curr_sample

        # Moving average calculation
        mac = np.mean(self.prev_data)
        curr_sample = int(mac)  # Simulate bit shift by 2 (/4) with int cast

        # Update the sample pipeline
        self.qrs_samples = [curr_sample] + self.qrs_samples[:-1]

        # Process the buffer to detect QRS complex
        self.QRS_process_buffer()

    def QRS_process_buffer(self):
        """
        Process the buffer to detect QRS complex.
        """
        QRS_Prev_Sample = self.qrs_samples[-2]  # Second last sample
        QRS_Next_Sample = self.qrs_samples[-1]  # Last sample
        # Calculating first derivative
        first_derivative = QRS_Next_Sample - QRS_Prev_Sample

        # Taking the absolute value
        scaled_result = abs(first_derivative)

        # Update the maximum if current result is higher
        if scaled_result > self.max:
            self.max = scaled_result

        self.qrs_b4_buffer_ptr += 1

        # Check if buffer has reached two seconds of samples
        if self.qrs_b4_buffer_ptr == TWO_SEC_SAMPLES:
            # Calculate new threshold based on maximum scaled result
            self.qrs_threshold_old = (self.max * 7) // 10
            self.qrs_threshold_new = self.qrs_threshold_old
            self.first_peak_detected = True
            self.max = 0
            self.qrs_b4_buffer_ptr = 0

        # If a peak was detected in previous cycles
        if self.first_peak_detected:
            self.QRS_check_sample_crossing_threshold(scaled_result)

    def QRS_check_sample_crossing_threshold(self, scaled_result):
        """
        Check if the sample crosses the threshold.

        Parameters:
        - scaled_result: The scaled result to check.
        """
        if self.threshold_crossed:
            self.sample_count += 1
            self.maxima_search += 1

            if scaled_result > self.peak:
                self.peak = scaled_result

            if self.maxima_search >= MAXIMA_SEARCH_WINDOW:
                self.maxima_sum += self.peak
                self.maxima_search = 0
                self.threshold_crossed = False
                self.peak_detected = True

        elif self.peak_detected:
            self.sample_count += 1
            self.nopeak_count += 1

            if self.nopeak_count >= MINIMUM_SKIP_WINDOW:
                self.nopeak_count = 0
                self.peak_detected = False

            if self.m_array_index == MAX_PEAK_TO_SEARCH:
                self.calculate_heart_rate()

        elif scaled_result > self.qrs_threshold_new:
            self.start_sample_count_flag = True
            self.sample_count += 1
            self.m_array_index += 1
            self.threshold_crossed = True
            self.peak = scaled_result
            self.sample_index[self.s_array_index] = self.sample_count

            if self.s_array_index >= 1:
                self.sample_sum += (self.sample_index[self.s_array_index] -
                                    self.sample_index[self.s_array_index - 1])

            self.s_array_index += 1

        elif scaled_result < self.qrs_threshold_new and self.start_sample_count_flag:
            self.handle_no_peak()

        else:
            self.nopeak_count += 1
            if self.nopeak_count > (3 * SAMPLING_RATE):
                self.reset_variables()

    def calculate_heart_rate(self):
        """
        Calculate the heart rate.
        """
        sample_sum_avg = self.sample_sum / (MAX_PEAK_TO_SEARCH - 1)
        self.heart_rate = 60 * SAMPLING_RATE / sample_sum_avg
        self.heart_rate = min(self.heart_rate, 250)
        self.maxima_sum = self.maxima_sum / MAX_PEAK_TO_SEARCH
        max_value = int(self.maxima_sum)
        self.maxima_sum = max_value * 7 / 10
        self.qrs_threshold_new = int(self.maxima_sum)
        self.reset_variables()

    def handle_no_peak(self):
        """
        Handle the situation when no peak is detected.

        This function increments the sample count and the no-peak count. If the no-peak count exceeds a threshold
        (3 times the sampling rate), it resets the variables.
        """
        self.sample_count += 1
        self.nopeak_count += 1

        if self.nopeak_count > (3 * SAMPLING_RATE):
            self.reset_variables()

    def reset_variables(self):
        """
        Reset the variables.

        This function resets all the variables used in the QRS detection algorithm. It is called when no peak is
        detected for a certain period of time or after the heart rate is calculated.
        """
        self.sample_count = 0
        self.s_array_index = 0
        self.m_array_index = 0
        self.maxima_sum = 0
        self.sample_index.fill(0)
        self.start_sample_count_flag = False
        self.peak_detected = False
        self.sample_sum = 0
        self.first_peak_detect = False
        self.nopeak_count = 0
        self.heart_rate = 0
