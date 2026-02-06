# 自动化测试系统 GUI 使用说明书

## 1. 简介
本软件是一个基于 Python 和 PySide6 开发的自动化测试工具，用于电源上/下电时序控制、DAC/电源参数配置以及直流线性度测试。

## 2. 环境准备
在运行软件前，请确保满足以下条件：
1.  **Python 环境**: 已安装 Python 3.8+。
2.  **依赖库**: 已运行 `pip install -r requirements.txt` 安装所需库 (PySide6, numpy, matplotlib, pyvisa, pyserial)。
3.  **配置文件**: 根目录下包含以下文件：
    *   `visa.txt`: 存放电源的 VISA 地址。
    *   `Power_on_config.txt`: 上电顺序配置。
    *   `Power_limit_config.txt`: 电流判定阈值配置。
    *   `Power_Config.txt`: 独立电源配置。
    *   `DAC_Config.txt`: DAC 初始化配置。

## 3. 软件界面概览
软件启动后，主界面分为三个主要标签页：
*   **Power Control**: 电源控制。
*   **Configuration**: 设备参数配置。
*   **Linearity Test**: 直流线性度测试。

顶部设有 **"Simulation Mode"** 复选框，默认勾选。
*   **勾选状态**: 软件运行在仿真模式，不连接真实硬件，返回模拟数据。
*   **取消勾选**: 软件尝试连接真实仪器。

底部为 **System Log**，实时显示操作日志和测试结果。

## 4. 功能操作指南

### 4.1 电源上/下电测试 (Power Control)
1.  切换到 **"Power Control"** 标签页。
2.  **上电测试**: 点击 **"Power ON Sequence"**。
    *   程序将读取 `Power_on_config.txt`，按顺序开启电源通道。
    *   等待稳定后读取电流，并根据 `Power_limit_config.txt` 判定 Pass/Fail。
    *   结果将保存至 `Power_on_result_{时间戳}.txt`。
3.  **下电测试**: 点击 **"Power OFF Sequence"**。
    *   程序将按上电配置的**逆序**关闭电源通道。

### 4.2 设备配置 (Configuration)
1.  切换到 **"Configuration"** 标签页。
2.  **DAC 配置**:
    *   输入 DAC 串口号 (如 `COM3`)。
    *   点击 **"Load & Apply DAC_Config.txt"**。
    *   程序解析文件并将电压转换为 DAC 码值发送给设备。
3.  **电源配置**:
    *   点击 **"Load & Apply Power_Config.txt"**。
    *   程序将设置电源通道的电压和限流值（不执行开关操作）。

### 4.3 直流线性度测试 (Linearity Test)
1.  切换到 **"Linearity Test"** 标签页。
2.  **设置参数**:
    *   **Source Selection**: 选择信号源是 DAC 还是 信号发生器 (DG)。
    *   **Start/End Voltage**: 设置扫描起始和终止电压 (如 -2.5 到 2.5)。
    *   **Step**: 设置步进电压 (如 0.1)。
    *   **DAC Channel**: 设置被测通道。
3.  **开始测试**: 点击 **"Start Linearity Test"**。
    *   程序自动控制源输出电压，并读取万用表数值。
    *   右侧图表实时绘制 Vout vs Vin 曲线及拟合直线。
    *   测试结束后，日志区显示 Gain, Offset, INL, DNL 指标。
    *   详细数据保存至 `results/` 目录下。

## 5. 常见问题
*   **无法连接设备**: 请检查 `visa.txt` 地址是否正确，或串口号是否被占用。确保已安装 NI-VISA 驱动。
*   **报错 "File not found"**: 请确认所有配置文件都在程序运行根目录下。
