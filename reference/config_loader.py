# 文件名: config_loader.py (已更新)
import os

def _calculate_gear(gears):
    """将4个通道的档位值合并为一个16位的整数码。"""
    gear_to_code_map = {2.5: 14, 5.0: 9, 10.0: 10, 20.0: 12}
    if len(gears) != 4:
        raise ValueError("CalculateGear函数需要一个包含4个档位值的列表。")
    code0 = gear_to_code_map.get(gears[0], 0)
    code1 = gear_to_code_map.get(gears[1], 0)
    code2 = gear_to_code_map.get(gears[2], 0)
    code3 = gear_to_code_map.get(gears[3], 0)
    return (code3 << 12) | (code2 << 8) | (code1 << 4) | code0

def _voltage_to_dac_code(voltage, gear):
    """将电压值转换为16位DAC码值。"""
    if gear == 0: return 0
    voltage = max(-gear, min(gear, voltage))
    return round((gear + voltage) * 65535 / (2 * gear))

def load_config_data(filepath):
    """从文件加载配置，并返回结构化的数据列表。"""
    if not os.path.exists(filepath):
        # 如果文件不存在，返回一个默认的32通道配置
        print(f"警告：找不到 {os.path.basename(filepath)}，将使用默认值。")
        return [{'gear': 2.5, 'voltage': 0.0} for _ in range(32)]

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()[1:]
    
    config_data = []
    for i, line in enumerate(lines):
        parts = line.strip().split()
        if len(parts) == 3:
            try:
                config_data.append({
                    'gear': float(parts[1]),
                    'voltage': float(parts[2])
                })
            except (ValueError, IndexError):
                raise Exception(f"错误：文件第 {i+2} 行格式不正确: '{line.strip()}'")
    
    if len(config_data) != 32:
        raise Exception(f"错误：配置文件应包含32行有效数据，实际找到 {len(config_data)} 行。")
    return config_data

def generate_full_config_commands(config_data):
    """根据完整的32通道数据，生成所有配置命令。"""
    for i in range(0, 32, 4):
        chunk = config_data[i : i+4]
        dac_chip_num = 0 if i < 16 else 1
        register_addr = 13 - (i % 16) // 4

        gears_in_chunk = [item['gear'] for item in chunk]
        calculated_gear_value = _calculate_gear(gears_in_chunk)
        yield (f"DAC{dac_chip_num:02d} {register_addr} {calculated_gear_value};", 0.1)

        for j, item in enumerate(chunk):
            channel = i + j
            dac_code = _voltage_to_dac_code(item['voltage'], item['gear'])
            yield (f"OUTPUT {channel} {dac_code};", 0.1)

def load_visa_address(filepath):
    """从VISAID.txt文件读取VISA地址"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line for line in f.read().splitlines() if line.strip()]
        if len(lines) >= 2:
            # 返回第二行非空行的内容
            return lines[1].strip()
        else:
            raise Exception("文件格式不正确，至少需要两行内容。")
    except FileNotFoundError:
        raise Exception(f"在程序目录下找不到文件 {os.path.basename(filepath)}")
