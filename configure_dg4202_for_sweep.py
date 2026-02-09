def _configure_dg4202_for_sweep(self, params):
    """配置DG4202任意波形发生器进行电压扫描"""
    if not self.dg_ctrl.is_connected:
        raise ConnectionError("DG4202未连接。")

    # 重置DG4202到已知状态
    self.dg_ctrl.write("*RST")
    time.sleep(0.1) # 稍作等待

    # 设置输出通道（假设使用CH1）
    # 明确切换到直流模式，并将幅度设为0，仅使用偏置作为直流电平
    self.dg_ctrl.write("SOUR1:FUNC DC")
    self.dg_ctrl.write("SOUR1:VOLT 0")
    self.dg_ctrl.write("SOUR1:VOLT:OFFS 0")
    self.dg_ctrl.write("OUTP1:LOAD 50") # 设置50欧阻抗负载
    self.dg_ctrl.write("OUTP1 ON") # 开启CH1输出

    # DG4202通常通过List模式或编程循环来步进电压
    # 这里仅设置基本参数，实际步进在_acquire_data_from_dg4202_sweep中完成
    start_v = params["start_v"]
    end_v = params["start_v"] + (params["points"] - 1) * params["step_v"]
    
    print(f"DG4202配置为扫描：从 {start_v}V 到 {end_v}V。")