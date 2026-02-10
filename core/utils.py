import numpy as np
import os
from datetime import datetime
import yaml
import csv

def calculate_gear_code(gears):
    """
    Calculates the 16-bit register value for 4 channels' ranges.
    gears: list of 4 float values [range0, range1, range2, range3]
    Mapping: 2.5->14, 5.0->9, 10.0->10, 20.0->12
    """
    gear_to_code_map = {2.5: 14, 5.0: 9, 10.0: 10, 20.0: 12}
    if len(gears) != 4:
        return 0
    
    code0 = gear_to_code_map.get(float(gears[0]), 0)
    code1 = gear_to_code_map.get(float(gears[1]), 0)
    code2 = gear_to_code_map.get(float(gears[2]), 0)
    code3 = gear_to_code_map.get(float(gears[3]), 0)
    
    return (code3 << 12) | (code2 << 8) | (code1 << 4) | code0

def calculate_dac_code(voltage_range_str, desired_voltage):
    """
    Calculates the 16-bit DAC control code.
    voltage_range_str: '2.5', '5', '10', '20' (representing range)
    Let's assume Range N means [-N, N] for simplicity unless specified otherwise.
    """
    try:
        v_range = float(voltage_range_str)
        # Assumption: Range X means [-X, +X]
        min_v = -v_range
        max_v = v_range
        
        # Let's stick to [-Range, +Range] as a safe default for lab equipment handling negative voltages.
        
        desired_v = float(desired_voltage)
        
        if not (min_v <= desired_v <= max_v):
            # Try unipolar 0 to Range
            if 0 <= desired_v <= v_range:
                min_v = 0
                max_v = v_range
            else:
                 # If still out of range, warn but clamp or error?
                 # Requirement says "Calculates...".
                 pass

        dac_resolution = 2**16 - 1
        voltage_span = max_v - min_v
        
        if voltage_span == 0:
            return 0

        control_code = int(((desired_v - min_v) / voltage_span) * dac_resolution)
        return max(0, min(control_code, 65535)) # Clamp
    except ValueError:
        return 0

def load_yaml_config(filepath):
    """
    Parses YAML config files.
    Returns a list of dictionaries.
    """
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            return yaml.safe_load(f) or []
        except yaml.YAMLError as e:
            print(f"Error parsing YAML {filepath}: {e}")
            return []

def load_csv_config(filepath):
    """
    Parses CSV config files.
    Returns a list of dictionaries.
    """
    data = []
    if not os.path.exists(filepath):
        return data
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def parse_config_file(filepath):
    """
    Parses config files.
    Returns a list of lists/tuples.
    Handles lines like: "DAC0 5 0" or "(DP1, 1, 5.0, 1.0)"
    """
    data = []
    if not os.path.exists(filepath):
        return data
        
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            # Remove parentheses if present
            clean_line = line.replace('(', '').replace(')', '').replace(',', ' ')
            parts = clean_line.split()
            if parts:
                data.append(parts)
    return data

def calculate_linearity_metrics(input_values, measured_values):
    """
    Calculates Gain, Offset, DNL, INL.
    input_values: Theoretical/Set values (X)
    measured_values: Measured values (Y)
    """
    x = np.array(input_values, dtype=float)
    y = np.array(measured_values, dtype=float)
    
    if len(x) < 2:
        return None

    # 1. Gain & Offset (Linear Fit: y = Gain * x + Offset)
    A = np.vstack([x, np.ones(len(x))]).T
    gain, offset = np.linalg.lstsq(A, y, rcond=None)[0]
    
    # 2. INL (Integral Non-Linearity)
    # INL = (Vmeas - Vfit) / LSB_ideal
    # LSB_ideal can be estimated as (Max_Meas - Min_Meas) / (Num_Steps - 1) 
    # OR derived from the Step size of input * Gain.
    # Let's use the fitted line as reference.
    y_fit = gain * x + offset
    
    # Calculate LSB based on input step size * gain (expected output step)
    # Assuming uniform step size in input
    if len(x) > 1:
        avg_step = np.mean(np.diff(x))
        lsb_ideal = avg_step * gain
    else:
        lsb_ideal = 1.0 # Avoid div by zero
        
    if lsb_ideal == 0:
        lsb_ideal = 1e-9

    inl = (y - y_fit) / lsb_ideal
    
    # 3. DNL (Differential Non-Linearity)
    # DNL_i = ( (Vmeas_i - Vmeas_{i-1}) / LSB_ideal ) - 1
    dnl = np.zeros(len(y))
    # DNL is usually defined for steps. DNL[0] is usually 0 or undefined.
    for i in range(1, len(y)):
        step_meas = y[i] - y[i-1]
        dnl[i] = (step_meas / lsb_ideal) - 1
        
    # 4. Nonlinearity (% FSR)
    # Max deviation from fit / Full Scale Range
    # FSR = Max(y) - Min(y)
    fsr = np.max(y) - np.min(y)
    max_dev = np.max(np.abs(y - y_fit))
    
    nonlinearity_pct = 0.0
    if fsr > 0:
        nonlinearity_pct = (max_dev / fsr) * 100.0

    # Max INL / DNL
    max_inl = np.max(np.abs(inl))
    max_dnl = np.max(np.abs(dnl))

    return {
        "gain": gain,
        "offset": offset,
        "inl": inl,
        "dnl": dnl,
        "lsb_ideal": lsb_ideal,
        "nonlinearity_pct": nonlinearity_pct,
        "max_inl": max_inl,
        "max_dnl": max_dnl
    }

def save_linearity_results(filename, input_vals, measured_vals, metrics):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("                --- 传输曲线测试报告 ---\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("--- 分析结果 ---\n")
        f.write(f"{'Gain (Vout/Vin)':<30}: {metrics['gain']:.6f}\n")
        f.write(f"{'Offset':<30}: {metrics['offset']:.6f} V\n")
        f.write(f"{'Nonlinearity':<30}: {metrics['nonlinearity_pct']:.4f} % FSR\n")
        f.write(f"{'Max INL':<30}: {metrics['max_inl']:.6f} LSB\n")
        f.write(f"{'Max DNL':<30}: {metrics['max_dnl']:.6f} LSB\n\n")
        
        f.write("--- 原始数据 ---\n")
        f.write(f"{'Vin (V)':<16}\t{'Vout (V)':<16}\n")
        f.write(f"{'-'*8:<16}\t{'-'*8:<16}\n")
        
        for i in range(len(input_vals)):
            f.write(f"{input_vals[i]:<16.4f}\t{measured_vals[i]:<16.6f}\n")
