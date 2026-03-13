import time
import os
from datetime import datetime

from .test_context import TestContext


class TPTestLogic:
    """
    Encapsulates the logic for TP (Test Point) voltage measurement.
    Sends DMM x; via serial to switch the measurement port, then reads
    voltage from the multimeter.
    """

    def run_test(self, context: TestContext, serial_inst, dm, test_points: dict) -> list:
        """
        Run TP voltage measurements for all test points.

        Args:
            context:      TestContext for logging and stop-check.
            serial_inst:  Serial instrument (DAC) used to send 'DMM x;' commands.
            dm:           Multimeter instrument used to read voltage.
            test_points:  dict mapping test-point name -> DMM port number.

        Returns:
            List of dicts with keys: name, port, voltage.
        """
        context.log("Starting TP Test...")
        results = []
        total = len(test_points)

        for idx, (name, port) in enumerate(test_points.items()):
            if context.check_stop():
                context.log("TP Test stopped by user.")
                break

            cmd = f"DMM {port};"
            context.log(f"Sending: {cmd}")
            serial_inst.send_raw_command(cmd)

            time.sleep(1.0)  # 等待 DM 稳定

            voltage = dm.measure_voltage()
            results.append({"name": name, "DMM": port, "voltage": voltage})
            context.log(f"  {name} (DMM{port}): {voltage:.4f} V")
            context.report_progress(int((idx + 1) / total * 100))

        if results:
            self._save_results(results, context)

        context.log("TP Test finished.")
        return results

    def _save_results(self, results: list, context: TestContext):
        folder = "results/tp_result"
        os.makedirs(folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = os.path.join(folder, f"tp_result_{timestamp}.txt")

        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(f"TP Test Results - {timestamp}\n")
                f.write("-" * 40 + "\n")
                f.write(f"{'Name':<12} {'DMM':>4}  {'Voltage (V)':>12}\n")
                f.write("-" * 40 + "\n")
                for r in results:
                    f.write(f"{r['name']:<12} {r['DMM']:>4}  {r['voltage']:>12.4f}\n")
            context.log(f"Results saved to {fname}")
        except Exception as e:
            context.log(f"Error saving TP results: {e}")
