"""
spo2_algorithm.py

This script is used to estimate the blood oxygen saturation (SpO2) from the IR and RED signals obtained from a pulse
oximeter. It uses a lookup table to convert the ratio of the RED/IR signals to SpO2.

The script defines a function, estimate_spo2, which takes the IR and RED signals as input and returns the estimated
SpO2 and heart rate.

- estimate_spo2(pun_ir_buffer, pun_red_buffer): This function estimates the SpO2 and heart rate from the IR and RED
signals. It first removes the DC components from the IR signal and then detects the valleys in the signal. It then
calculates the ratio of the AC components of the RED and IR signals at the valleys and uses a lookup table to convert
the ratio to SpO2."""

import numpy as np

# Define the SpO2 lookup table
uch_spo2_table = np.array([
    95, 95, 95, 96, 96, 96, 97, 97, 97, 97, 97, 98, 98, 98, 98, 98, 99, 99, 99, 99,
    99, 99, 99, 99, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
    100, 100, 100, 100, 99, 99, 99, 99, 99, 99, 99, 99, 98, 98, 98, 98, 98, 98, 97, 97,
    97, 97, 96, 96, 96, 96, 95, 95, 95, 94, 94, 94, 93, 93, 93, 92, 92, 92, 91, 91,
    90, 90, 89, 89, 89, 88, 88, 87, 87, 86, 86, 85, 85, 84, 84, 83, 82, 82, 81, 81,
    80, 80, 79, 78, 78, 77, 76, 76, 75, 74, 74, 73, 72, 72, 71, 70, 69, 69, 68, 67,
    66, 66, 65, 64, 63, 62, 62, 61, 60, 59, 58, 57, 56, 56, 55, 54, 53, 52, 51, 50,
    49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 31, 30, 29,
    28, 27, 26, 25, 23, 22, 21, 20, 19, 17, 16, 15, 14, 12, 11, 10, 9, 7, 6, 5,
    3, 2, 1
])



def estimate_spo2(pun_ir_buffer, pun_red_buffer):
    if len(pun_ir_buffer) == 0 or len(pun_red_buffer) == 0:
        return None, None

    n_ir_buffer_length = len(pun_ir_buffer)
    BUFFER_SIZE = n_ir_buffer_length
    MA4_SIZE = 4

    an_x = np.zeros(BUFFER_SIZE)
    an_y = np.zeros(BUFFER_SIZE)

    # 计算红外平均并去直流分量
    un_ir_mean = np.mean(pun_ir_buffer)
    an_x = -1 * (pun_ir_buffer - un_ir_mean)

    # 4点移动平均
    for i in range(BUFFER_SIZE - MA4_SIZE):
        an_x[i] = np.mean(an_x[i:i + MA4_SIZE])

    # 计算阈值
    n_th1 = np.mean(np.abs(an_x))
    n_th1 = max(30, min(n_th1, 60))

    # 使用峰值检测找到波谷
    an_ir_valley_locs = []
    for i in range(1, BUFFER_SIZE - 1):
        if an_x[i] < -n_th1 and an_x[i] < an_x[i - 1] and an_x[i] < an_x[i + 1]:
            an_ir_valley_locs.append(i)

    n_npks = len(an_ir_valley_locs)
    n_peak_interval_sum = np.diff(an_ir_valley_locs).sum() if n_npks >= 2 else 0
    pn_heart_rate = (60 * 25) / n_peak_interval_sum if n_npks >= 2 else -999
    pch_hr_valid = n_npks >= 2

    # 加载原始值以计算SPO2：红色和红外
    an_x = pun_ir_buffer
    an_y = pun_red_buffer

    # 使用波谷位置寻找IR和Red的AC和DC
    n_ratio_average = 0
    n_i_ratio_count = 0
    an_ratio = np.zeros(200)

    for k in range(1, n_npks):
        if an_ir_valley_locs[k] < BUFFER_SIZE:
            n_x_dc_max = np.max(an_x[an_ir_valley_locs[k - 1]:an_ir_valley_locs[k]])
            n_y_dc_max = np.max(an_y[an_ir_valley_locs[k - 1]:an_ir_valley_locs[k]])

            n_x_ac = n_x_dc_max - np.mean(an_x[an_ir_valley_locs[k - 1]:an_ir_valley_locs[k]])
            n_y_ac = n_y_dc_max - np.mean(an_y[an_ir_valley_locs[k - 1]:an_ir_valley_locs[k]])

            n_nume = n_y_ac * n_x_dc_max
            n_denom = n_x_ac * n_y_dc_max

            if n_denom > 0:
                an_ratio[n_i_ratio_count] = 100 * n_nume / n_denom
                n_i_ratio_count += 1

    # 使用中值获取R值
    if n_i_ratio_count > 0:
        an_ratio = an_ratio[:n_i_ratio_count]
        an_ratio.sort()
        n_middle_idx = n_i_ratio_count // 2
        n_ratio_average = int(an_ratio[n_middle_idx])
        pn_spo2 = uch_spo2_table[n_ratio_average] if 2 < n_ratio_average < 183 else None
    else:
        pn_spo2 = None

    return pn_spo2, pn_heart_rate
