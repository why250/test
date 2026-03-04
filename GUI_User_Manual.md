# 自动化测试系统 GUI 使用说明书

## 1. 简介
本软件是一个基于 Python 和 PySide6 开发的自动化测试工具，用于电源上/下电时序控制、DAC/电源参数配置、直流线性度测试以及 CP Wafer Sort 自动化测试。

## 2. 环境准备
在运行软件前，请确保满足以下条件：
1.  **Python 环境**: 已安装 Python 3.8+。
2.  **依赖库**: 已运行 `pip install -r requirements.txt` 安装所需库 (PySide6, numpy, matplotlib, pyvisa, pyserial)。
3.  **配置文件**: 根目录 `config/` 文件夹下包含以下文件：
    *   `visa.yaml`: 存放电源的 VISA 地址。
    *   `Power_on_config.yaml`: 上电顺序配置。
    *   `Power_limit_config.yaml`: 电流判定阈值配置。
    *   `Power_Config.yaml`: 独立电源配置。
    *   `DAC_Config.csv`: DAC 初始化配置。
    *   `cp_test_config.yaml`: CP 测试参数配置。
    *   `cp_hardware_config.yaml`: CP 测试各阶段硬件配置。
    *   `wafer_layout.csv` / `wafer_layout.json`: 晶圆布局配置。

## 3. 软件界面概览
软件启动后，主界面分为五个主要标签页：
*   **Device Manager**: 设备连接管理。
*   **Power Control**: 电源控制。
*   **Configuration**: 设备参数配置。
*   **Linearity Test**: 直流线性度测试。
*   **CP Wafer Sort**: CP 自动化测试。

顶部设有 **"Simulation Mode"** 复选框，默认不勾选。
*   **勾选状态**: 软件运行在仿真模式，不连接真实硬件，返回模拟数据。
*   **取消勾选**: 软件尝试连接真实仪器。

底部为 **System Log**，实时显示操作日志和测试结果。点击 **"Clear"** 按钮可清除日志内容。

## 4. 功能操作指南

### 4.1 设备管理 (Device Manager)
1.  **查看设备**: 树状图显示所有已注册的设备及其状态。
2.  **添加设备**: 点击 "Add Device" 手动添加设备。
3.  **移除设备**: 选中设备后点击 "Remove Device"。
4.  **连接/断开**: 使用 "Connect All" 或 "Disconnect All" 批量操作。

### 4.2 电源上/下电测试 (Power Control)
1.  切换到 **"Power Control"** 标签页。
2.  **上电测试**: 点击 **"Power ON Sequence"**。
    *   程序将读取 `Power_on_config.yaml`，按顺序开启电源通道。
    *   等待稳定后读取电流，并根据 `Power_limit_config.yaml` 判定 Pass/Fail。
    *   结果将保存至 `results/power_on_result/` 目录下。
    *   **注意**: 如果两个配置文件的通道数量不一致，日志中会显示警告。
3.  **下电测试**: 点击 **"Power OFF Sequence"**。
    *   程序将按上电配置的**逆序**关闭电源通道。

### 4.3 设备配置 (Configuration)
1.  切换到 **"Configuration"** 标签页。
2.  **DAC 配置**:
    *   选择 DAC Alias。
    *   点击 **"Load & Apply DAC_Config.csv"**。
    *   程序解析文件并将电压转换为 DAC 码值发送给设备。
3.  **电源配置**:
    *   点击 **"Load & Apply Power_Config.yaml"**。
    *   程序将设置电源通道的电压和限流值（不执行开关操作）。

### 4.4 直流线性度测试 (Linearity Test)
1.  切换到 **"Linearity Test"** 标签页。
2.  **设置参数**:
    *   **Source Selection**: 选择信号源是 DAC 还是 信号发生器 (DG)。
    *   **Start/Step Voltage**: 设置扫描起始电压和步进。
    *   **Points**: 设置扫描点数。
    *   **Channels**: 设置 DAC/DG 通道。
3.  **开始测试**: 点击 **"Start Linearity Test"**。
    *   程序自动控制源输出电压，并读取万用表数值。
    *   右侧图表实时绘制 Vout vs Vin 曲线及拟合直线。
    *   测试结束后，日志区显示 Gain, Offset, INL, DNL 指标。
    *   详细数据和截图保存至 `results/dc_linearity_result/<site_id>/` 和 `results/image/<site_id>/` 目录下。

### 4.5 CP Wafer Sort 自动化测试 (CP Wafer Sort)
1.  切换到 **"CP Wafer Sort"** 标签页。
2.  **Site Management**:
    *   **Site ID**: 输入当前测试的 Site ID，坐标 (Row, Col) 会自动更新。
    *   **Auto Increment**: 勾选后，测试完成后自动跳转到下一个 Site ID。
3.  **Test Control**:
    *   **Start CP Test**: 开始自动化测试流程。
        *   执行 Power On 序列。
        *   执行 Power Check。
        *   按顺序执行多个 Stage 的线性度测试（Stage 数量由配置文件动态决定）。
        *   测试完成后自动执行 Safe Power Down（回退配置至初始状态并下电）。
    *   **Stop**: 停止当前测试。程序会停止扫描并执行 Safe Power Down。
    *   **Generate Wafer Map**: 生成晶圆测试结果热力图。
4.  **结果保存**:
    *   汇总结果保存至 `Wafer_Sort_Results.csv`。
    *   包含 Power Check 结果、各 Stage 的线性度指标及 DP 电流值。

## 5. 常见问题
*   **无法连接设备**: 请检查 `visa.yaml` 地址是否正确，或串口号是否被占用。确保已安装 NI-VISA 驱动。
*   **报错 "File not found"**: 请确认所有配置文件都在程序运行根目录的 `config/` 文件夹下。
*   **Stop 按钮无效**: 点击 Stop 后，程序会等待当前指令执行完毕并安全停止 Worker 线程，可能需要几秒钟响应。
