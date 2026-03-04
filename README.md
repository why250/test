# 测试需求说明书 v2.0

通过 Python 函数实现自动化测试功能。

## 测试功能需求目录

1.  Power on 上电顺序控制
2.  Power off 下电顺序控制
3.  配置 DAC 配置、电源配置
4.  直流线性度测试
5.  CP Wafer Sort 自动化测试

## 1. Power on 上电顺序控制

1.  **连接 DP 电源**
    通过 VISA 地址连接 DP 电源（配置在 `config/visa.yaml`）。

2.  **配置通道上电顺序和参数**
    定义通道上电顺序及参数。
    配置文件：`config/Power_on_config.yaml`
    ```yaml
    - instrument: DP1
      channel: 1
      voltage: 2.3
      current: 0.5
    ```
    *支持动态扩展 DP Channel 数量。*

3.  **按序上电并记录电流**

4.  **电流值范围比较**
    配置文件：`config/Power_limit_config.yaml`
    ```yaml
    - instrument: DP1
      channel: 1
      min_current: 0.4
      max_current: 0.5
    ```
    *   系统会自动检查 Config 和 Limit 文件中通道数量的一致性并给出警告。
    *   保存上电后电流结果和比较结果为 `results/power_on_result/<site_id>/Power_on_result_{时间戳}.txt`。

## 2. Power off 下电顺序控制

按照与 Power on 顺序相反的顺序下电。

## 3. 配置 DAC 配置、电源配置

1.  **连接设备**
    通过 VISA/串口连接 DAC 和电源。

2.  **配置 DAC 参数**
    配置文件：`config/DAC_Config.csv`
    ```csv
    Channel,Range,Voltage
    DAC1,10,-2.5
    ```

3.  **配置电源参数**
    配置文件：`config/Power_Config.yaml`

## 4. 直流线性度测试

1.  **连接万用表 DM**
    万用表读取的参数为“输出参数”。

2.  **多种“输入参数”扫描方式**
    *   扫描 DAC 某一通道。
    *   连接 DG，扫描 DG 直流输出。

3.  **进行直流线性度分析并保存结果**
    *   绘制“输入参数”vs“输出参数”图。
    *   计算 Gain, Offset, Nonlinearity, DNL, INL 等参数。
    *   保存路径：`results/dc_linearity_result/<site_id>/`。
    *   图片保存路径：`results/image/<site_id>/`。

## 5. CP Wafer Sort 自动化测试

1.  **Site 管理**
    *   支持 Site ID 输入，自动关联 Row/Col 坐标。
    *   支持测试完成后自动递增 Site ID。

2.  **多 Stage 测试流程**
    *   **Power On**: 执行上电序列。
    *   **Power Check**: 检查电流是否在限制范围内。
    *   **Stage Loop**: 根据 `config/cp_test_config.yaml` 和 `config/cp_hardware_config.yaml` 定义的 Stage 数量，自动执行多阶段测试。
        *   每个 Stage 可配置不同的 DAC 电压和电源电压。
        *   支持动态扩展 Stage 数量（如增加到 8 个或更多）。
    *   **Safe Power Down**: 测试结束或中止时，先将所有配置回退至初始状态，再执行下电序列。

3.  **结果汇总**
    *   所有测试关键指标汇总保存至 `Wafer_Sort_Results.csv`。
    *   包含：Test Time, Site ID, 坐标, Final Result, Power Check Result, 各 Stage 的 Gain/Offset/INL/DNL 及 DP 电流值。
    *   如果 Stage 数量发生变化，CSV 文件头会自动更新（旧文件备份）。

4.  **Wafer Map 生成**
    *   根据测试结果生成晶圆热力图。

## 6. 日志与异常处理

*   **System Log**: GUI 界面实时显示日志，支持一键清除。
*   **Stop 功能**: 点击 Stop 按钮可安全停止正在进行的扫描任务，并执行 Safe Power Down。

## 7. 项目结构

*   `core/`: 核心仪器控制与测试逻辑
    *   `instruments.py`: 仪器类定义
    *   `power_test.py`: 上电/下电测试逻辑
    *   `linearity_test.py`: 线性度测试逻辑
    *   `test_context.py`: 测试上下文管理
    *   `utils.py`: 通用工具函数
*   `cp_test/`: CP Wafer Sort 专用逻辑
    *   `runner.py`: CP 测试序列运行器
    *   `data_manager.py`: 数据管理与 CSV 导出
*   `gui/`: 图形用户界面
*   `config/`: 配置文件
