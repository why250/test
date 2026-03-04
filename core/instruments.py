import time
import random

# Try importing real libraries, fall back to None if missing
try:
    import pyvisa
except ImportError:
    pyvisa = None

try:
    import serial
except ImportError:
    serial = None

__all__ = [
    "InstrumentManager",
    "VisaInstrument",
    "PowerSupply",
    "DAC",
    "Multimeter",
    "SignalGenerator",
]

class InstrumentManager:
    def __init__(self, simulation_mode=True):
        self._simulation_mode = simulation_mode
        self.rm = None
        self.instruments = {} # Registry: {alias: instrument_instance}
        
        # Always try to initialize ResourceManager if pyvisa is available
        # This allows switching to real mode later even if started in sim mode
        if pyvisa:
            try:
                self.rm = pyvisa.ResourceManager()
            except Exception as e:
                print(f"Error initializing VISA ResourceManager: {e}")
                # If RM fails, we might want to enforce sim mode, but let's just log for now
                pass

    @property
    def simulation_mode(self):
        return self._simulation_mode

    @simulation_mode.setter
    def simulation_mode(self, value):
        self._simulation_mode = value
        # Update all registered instruments
        for inst in self.instruments.values():
            inst.simulation_mode = value

    def register_instrument(self, alias, inst_type, address):
        """
        Registers a new instrument.
        inst_type: 'DP', 'DAC', 'DM', 'DG'
        """
        instrument_classes = {
            'DP': PowerSupply,
            'DAC': DAC,
            'DM': Multimeter,
            'DG': SignalGenerator
        }

        if inst_type not in instrument_classes:
            print(f"Unknown instrument type: {inst_type}")
            return None

        inst_class = instrument_classes[inst_type]
        
        # Determine arguments based on class signature or common pattern
        # Currently, DAC has a different signature (port, baudrate vs address, rm)
        # We can standardize this or handle the exception here.
        
        inst = None
        if inst_type == 'DAC':
             # DAC uses (port, baudrate, simulation_mode)
             # Assuming address is the port
             inst = inst_class(address, 9600, self._simulation_mode)
        else:
             # Others use (address, resource_manager, simulation_mode)
             inst = inst_class(address, self.rm, self._simulation_mode)

        if inst:
            self.instruments[alias] = inst
            return inst
        return None

    def get_instrument(self, alias):
        return self.instruments.get(alias)

    def get_all_instruments(self):
        return self.instruments

    def remove_instrument(self, alias):
        if alias in self.instruments:
            inst = self.instruments[alias]
            if inst.connected:
                inst.close()
            del self.instruments[alias]

    # Legacy/Direct access helpers (optional, but keeping for compatibility if needed)
    def get_power_supply(self, address):
        return PowerSupply(address, self.rm, self.simulation_mode)

    def get_dac(self, port, baudrate=9600):
        return DAC(port, baudrate, self.simulation_mode)

    def get_multimeter(self, address):
        return Multimeter(address, self.rm, self.simulation_mode)
    
    def get_signal_generator(self, address):
        return SignalGenerator(address, self.rm, self.simulation_mode)

class VisaInstrument:
    """
    Base class for VISA-based instruments.
    Implements the Rule of Three / DRY principle by centralizing connection logic.
    """
    def __init__(self, address, resource_manager, simulation_mode):
        self.address = address
        self.simulation_mode = simulation_mode
        self.inst = None
        self.connected = False
        self.rm = resource_manager

    def connect(self):
        if self.simulation_mode:
            self.connected = True
            print(f"[SIM] Connected to {self.__class__.__name__} at {self.address}")
            return True
        
        if not self.rm:
            print("VISA Resource Manager not available.")
            return False

        try:
            if self.rm:
                self.inst = self.rm.open_resource(self.address)
                self.connected = True
                return True
        except Exception as e:
            print(f"Failed to connect to {self.__class__.__name__}: {e}")
            return False

    def close(self):
        if self.inst:
            self.inst.close()
        self.connected = False

class PowerSupply(VisaInstrument):
    def set_channel(self, channel, voltage, current):
        if self.simulation_mode:
            print(f"[SIM] DP Set CH{channel}: {voltage}V, {current}A")
            return
        
        if self.connected and self.inst:
            try:
                cmd = f":APPLy CH{channel},{voltage},{current}"
                self.inst.write(cmd)
            except Exception as e:
                print(f"Error setting DP: {e}")

    def set_protection(self, channel, ovp, ocp):
        if self.simulation_mode:
            print(f"[SIM] DP Set Protection CH{channel}: OVP={ovp:.2f}V, OCP={ocp:.2f}A")
            return

        if self.connected and self.inst:
            try:
                # Setting OVP
                self.inst.write(f":OUTPut:OVP:VALue CH{channel},{ovp:.4f}")
                self.inst.write(f":OUTPut:OVP CH{channel},ON")
                
                # Setting OCP
                self.inst.write(f":OUTPut:OCP:VALue CH{channel},{ocp:.4f}")
                self.inst.write(f":OUTPut:OCP CH{channel},ON")
                
            except Exception as e:
                print(f"Error setting DP protection: {e}")

    def output_on(self, channel):
        if self.simulation_mode:
            print(f"[SIM] DP Output ON CH{channel}")
            return
        if self.connected and self.inst:
            try:
                self.inst.write(f":OUTPut CH{channel},ON")
            except Exception as e:
                print(f"Error turning output ON: {e}")

    def output_off(self, channel):
        if self.simulation_mode:
            print(f"[SIM] DP Output OFF CH{channel}")
            return
        if self.connected and self.inst:
            try:
                self.inst.write(f":OUTPut CH{channel},OFF")
            except Exception as e:
                print(f"Error turning output OFF: {e}")

    def measure_current(self, channel):
        if self.simulation_mode:
            val = random.uniform(0.1, 0.8)
            print(f"[SIM] DP Measure Current CH{channel}: {val:.3f}A")
            return val
        
        if self.connected and self.inst:
            try:
                val = self.inst.query(f":MEASure:CURRent? CH{channel}")
                return float(val)
            except Exception as e:
                print(f"Error measuring current: {e}")
                return 0.0
        return 0.0

class DAC:
    def __init__(self, port, baudrate, simulation_mode):
        self.port = port
        self.baudrate = baudrate
        self.simulation_mode = simulation_mode
        self.ser = None
        self.connected = False

    def connect(self):
        if self.simulation_mode:
            self.connected = True
            print(f"[SIM] Connected to DAC at {self.port}")
            return True
        
        if not serial:
             print("Serial library not available.")
             return False

        if serial:
            try:
                self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
                self.connected = True
                return True
            except Exception as e:
                print(f"Failed to connect to DAC: {e}")
                return False
        return False

    def set_output(self, channel_idx, dac_code):
        cmd = f"OUTPUT {channel_idx} {dac_code};"
        self.send_raw_command(cmd)

    def send_raw_command(self, cmd):
        if self.simulation_mode: # Although simulation_mode property was removed, we check connection logic
             pass # Logic handled below

        if not self.connected:
             print(f"DAC not connected. Cannot send: {cmd}")
             return

        if self.connected and self.ser:
            try:
                # print(f"Sending DAC: {cmd}")
                self.ser.write(cmd.encode('ascii') + b'\n')
            except Exception as e:
                print(f"Error sending to DAC: {e}")

    def close(self):
        if self.ser:
            self.ser.close()
        self.connected = False

class Multimeter(VisaInstrument):
    def measure_voltage(self):
        if self.simulation_mode:
            val = random.uniform(-5, 5)
            return val
        
        if self.connected and self.inst:
            try:
                val = self.inst.query(":MEASure:VOLTage:DC?")
                return float(val)
            except Exception as e:
                print(f"Error measuring voltage: {e}")
                return 0.0
        return 0.0

class SignalGenerator(VisaInstrument):
    def initialize_dc_mode(self, channel=1):
        if self.simulation_mode:
            print(f"[SIM] DG Initialize DC Mode CH{channel}")
            return

        if self.connected and self.inst:
            try:
                # Follows configure_dg4202_for_sweep.py
                self.inst.write("*RST")
                time.sleep(0.1)
                self.inst.write(f"SOUR{channel}:FUNC DC")
                self.inst.write(f"SOUR{channel}:VOLT 0")
                self.inst.write(f"SOUR{channel}:VOLT:OFFS 0")
                self.inst.write(f"OUTP{channel}:LOAD 50")
                self.inst.write(f"OUTP{channel} ON")
            except Exception as e:
                print(f"Error initializing DG: {e}")

    def set_dc_voltage(self, voltage, channel=1):
        if self.simulation_mode:
            print(f"[SIM] DG Set DC CH{channel}: {voltage}V")
            return
        
        if self.connected and self.inst:
            try:
                # Use Offset for DC level as per reference script
                self.inst.write(f"SOUR{channel}:VOLT:OFFS {voltage}")
            except Exception as e:
                print(f"Error setting DG voltage: {e}")
