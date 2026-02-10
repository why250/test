这是一个非常典型的 **CP 测试（Chip Probing / Wafer Sort）** 需求。为了实现芯片物理位置与测试结果的一一对应，并便于后续生成如你截图所示的 **Wafer Map（晶圆图谱）**，你需要引入 **坐标系统 (Coordinates)** 的概念。

以下是实现该需求的完整技术方案，包含数据结构设计、CSV 格式定义以及自动化流程的修改建议。

### 1. 核心思路：引入坐标 (Row, Column)

目前的自动化测试脚本是针对“单次”运行设计的。为了对应位置，需要在每次启动测试前，输入当前探针所扎芯片的 **坐标信息**（如行 Row、列 Column 或 序号 Site_ID）。

### 2. CSV 结果文件设计

你需要一个总的日志文件（Summary Log），而不是散落在 `./results` 文件夹下的单个文件。这个 CSV 应该随着测试的进行不断追加（Append）新的一行。

**推荐的 `wafer_map_results.csv` 格式：**

| Row | Col | Result  | Failure_Reason        | Stage_Passed | Current_CH2(A) | Max_INL | Test_Time           |
| :-- | :-- | :------ | :-------------------- | :----------- | :------------- | :------ | :------------------ |
| 1   | 1   | PASS    | None                  | 7/7          | 0.22           | 0.45    | 2023-10-27 14:00:01 |
| 1   | 2   | FAIL    | Power_Limit_Exceeded  | 0/7          | **0.85** | N/A     | 2023-10-27 14:05:22 |
| 1   | 3   | PARTIAL | Linearity_Fail_Stage7 | 6/7          | 0.23           | 2.1     | 2023-10-27 14:10:05 |

* **Row/Col**: 对应物理位置。
* **Result**: 最终判定（PASS/FAIL/PARTIAL）。
* **Failure_Reason**: 记录具体是上电电流超标 [4]，还是线性度计算中的 DNL/INL 超标。
* **Stage_Passed**: 记录 7 个增益档位中通过了几个（对应截图中的“部分正常”）。

### 3. 自动化程序的修改逻辑

你需要将之前的自动化脚本封装在一个新的 **`run_chip_test(row, col)`** 函数中。

#### 步骤 A: 判定标准定义 (Pass/Fail Criteria)

在代码中硬性规定什么是 Pass，什么是 Fail：

1. **上电判定**：读取实测电流，必须在 `Power_limit_config.txt` 定义的范围内 [4]。如果不在此范围，直接判定 **FAIL**，停止后续测试以保护探针和芯片。
2. **线性度判定**：
   * 在执行直流线性度测试时 [1]，计算出的 INL 和 DNL 必须小于某个阈值（例如 1.0 LSB）。
   * 如果 7 个档位全部通过 $\rightarrow$ **PASS** (绿色)。
   * 如果前 N 个档位通过，后续失败 $\rightarrow$ **PARTIAL** (黄色)。
   * 如果第 1 个档位就失败 $\rightarrow$ **FAIL** (粉色)。

#### 步骤 B: 软件操作流程优化

建议在 GUI 上增加一个 **Grid（网格）视图** 或者两个输入框（Row, Col）。

1. **输入位置**：操作员手动扎针到位置 (X=3, Y=5)。
2. **输入坐标**：在软件中输入 Row=3, Col=5（或者直接点击 GUI 网格上的对应方块）。
3. **运行测试**：
   * 软件读取 `visa.txt` 连接仪器 [1]。
   * 执行 **Power On** [1]，检查电流 [4]。若电流超标，写入 CSV 结果 "FAIL"，结束。
   * 若电流正常，执行 **7 档位线性度循环**。记录通过的档位数量。
   * 执行 **Power Off** [1]。
4. **保存与显示**：
   * 将结果 `[3, 5, PASS, ...]` 追加写入 `wafer_map_results.csv`。
   * GUI 上对应的方块根据结果变色（绿/红/黄）。

### 4. 代码实现示例 (Python)

以下是一个简化的逻辑，展示如何将测试结果与位置绑定并存为 CSV：

```python
import csv
import time
import os
# 假设这是你之前封装好的自动化测试类
from auto_test_core import AutomatedTester 

class CP_Wafer_Sort:
    def __init__(self):
        self.csv_file = "wafer_map_results.csv"
        self.tester = AutomatedTester()
        self.init_csv()

    def init_csv(self):
        # 如果文件不存在，写入表头
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Row", "Col", "Result", "Fail_Reason", "Passed_Stages", "Time"])

    def test_single_chip(self, row, col):
        """
        对应手动扎针后的单次测试
        """
        result = "PASS"
        fail_reason = "None"
        passed_stages = 0
      
        try:
            # 1. 上电测试 (Power On)
            # 读取 Power_limit_config.txt 进行判定 [4]
            power_status = self.tester.run_power_on_sequence() 
          
            if not power_status['passed']:
                result = "FAIL"
                fail_reason = f"Power Current Fail: {power_status['current_val']}A"
                # 严重错误，直接下电并记录
                self.tester.run_power_off_sequence()
                self.save_result(row, col, result, fail_reason, passed_stages)
                return "FAIL"

            # 2. 线性度测试 (7个档位)
            # 遍历 7 个增益配置 [2][3]
            for stage in range(1, 8):
                # 动态配置 DAC 和 Power，执行扫描 [1]
                scan_res = self.tester.run_linearity_stage(stage)
              
                # 假设设定 INL > 1.0 为失败
                if scan_res['max_inl'] < 1.0 and scan_res['max_dnl'] < 0.5:
                    passed_stages += 1
                else:
                    if passed_stages == 0:
                        result = "FAIL"
                    else:
                        result = "PARTIAL" # 部分正常
                    fail_reason = f"Linearity Fail at Stage {stage}"
                    break # 只要有一档不过，后续是否继续测取决于策略，通常停止

        except Exception as e:
            result = "ERROR"
            fail_reason = str(e)
        finally:
            # 3. 下电 (Power Off) [1]
            self.tester.run_power_off_sequence()
          
            # 4. 保存 CSV
            self.save_result(row, col, result, fail_reason, passed_stages)
            return result

    def save_result(self, row, col, result, reason, stages):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([row, col, result, reason, stages, timestamp])
        print(f"Chip ({row}, {col}) Test Finished: {result}")

# 使用示例：
# 操作员将探针扎在 第3行 第5列，然后在 GUI 点击 "Run Test"
# GUI 调用: cp_system.test_single_chip(3, 5)
```

### 5. 总结

要实现您的复查分析需求：

1. **数据源**：利用现有的上电限流配置 [4] 和 DAC 扫描逻辑 [1]。
2. **输入**：在 GUI 上增加 **Row/Col 输入框**。
3. **输出**：生成一份包含坐标信息的 **CSV 文件**。
4. **判定**：依据上电电流（是否烧片）和 7 个档位的通过率，给出 PASS/FAIL/PARTIAL 的综合结论。

这样，您最终得到的 CSV 文件可以直接导入 Excel 或专门的良率分析软件（如 JMP, Galaxy），直接生成与物理位置对应的良率分布图。


# 6.more


CSV里除了Row/Col和PASS/FAIL，我还想记录每个挡位的Max INL/Max DNL、输入幅度、以及失败阈值，推荐的列结构怎么设计？

---

我不想每次手动输入Row/Col，能不能用连续编号（Site_ID）自动递增，并支持跳号/重测同一颗的情况？怎么做最稳？

---

如果测试中途异常（仪器掉线/电流超限/脚本报错），如何确保也能写入一条结果并且自动下电保护，同时在CSV里标记ERROR原因？

---

我希望生成一个wafer map（按Row/Col上色的图）并导出PNG/HTML，能给一个实现思路或Python示例吗？

---

同一颗芯片可能需要复测多次，我想在CSV里保留历史并给出最终判定（比如取最好/取最后一次/多数投票），应该怎么定义规则和实现？
