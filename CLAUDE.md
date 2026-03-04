# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is an automated test system for power supply and DAC (Digital-to-Analog Converter) testing. The application is built with Python and PySide6 for GUI development, featuring instrument control, configuration management, linear regression analysis, and CP Wafer Sort capabilities.

## Development Commands

### Running the Application
```bash
python main.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Project Structure
```
test/
├── core/                 # Core instrument control and test logic
│   ├── instruments.py     # Instrument classes (PowerSupply, DAC, Multimeter, SignalGenerator)
│   ├── power_test.py      # Power sequence logic
│   ├── linearity_test.py  # Linearity test logic
│   ├── test_context.py    # Test execution context
│   └── utils.py         # Utility functions
├── cp_test/              # CP Wafer Sort specific logic
│   ├── data_manager.py   # Result file handling (CSV)
│   └── runner.py         # CP test sequence runner
├── gui/                  # GUI components
│   ├── main_window.py    # Main application window
│   └── workers.py       # Background workers for long-running tasks
├── config/               # Configuration files
├── main.py              # Application entry point
└── requirements.txt     # Python dependencies
```

## Architecture Overview

### Core Architecture
- **InstrumentManager**: Central registry for managing all test instruments (Power Supplies, DACs, Multimeters, Signal Generators)
- **Simulation Mode**: Built-in simulation mode for testing without physical hardware
- **Worker Threads**: Background threads handle long-running operations (power sequences, linearity tests) to keep UI responsive

### GUI Structure
The application has 5 main tabs:
1. **Device Manager**: Connect/disconnect instruments and view connection status
2. **Power Control**: Execute power on/off sequences with current validation
3. **Configuration**: Load and apply DAC and power supply configurations
4. **Linearity Test**: Perform DC linearity measurements with real-time plotting
5. **CP Wafer Sort**: Automated multi-stage testing with dynamic hardware configuration and result logging

### Key Components

#### Instrument Control
- **PowerSupply**: Controls power supply channels (voltage, current, output)
- **DAC**: Controls digital-to-analog converter outputs
- **Multimeter**: Measures voltage/current readings
- **SignalGenerator**: Generates test signals for linearity testing

#### CP Wafer Sort Logic
- **CPTestRunner** (`cp_test/runner.py`): Manages the multi-stage test sequence (Power On -> Power Check -> Linearity Stages -> Power Off)
- **DataManager**: Handles `Wafer_Sort_Results.csv` writing, supporting dynamic column names based on hardware config
- **Failure Handling**: Supports `ABORT_ON_POWER_FAIL` and `ABORT_ON_NONLINEARITY_FAIL` modes

#### Configuration Files
- `visa.yaml`: VISA addresses for instruments
- `Power_on_config.yaml`: Power on sequence configuration
- `Power_limit_config.yaml`: Current threshold settings
- `DAC_Config.csv`: DAC initialization and voltage settings
- `Power_Config.yaml`: Power supply channel configurations
- `cp_test_config.yaml`: CP test parameters (stages, limits)
- `cp_hardware_config.yaml`: Per-stage hardware settings (Power/DAC)

#### Test Workers
- **PowerWorker**: Executes power on/off sequences
- **LinearityWorker**: Performs DC linearity measurements and analysis

### Important Notes
- The application supports both real hardware and simulation modes
- Configuration files are loaded from the `config/` directory
- Test results are saved to `results/` directory
- Plots are saved to `image/` directory
- All instrument communication is handled through the InstrumentManager registry
- `Wafer_Sort_Results.csv` columns are dynamically generated based on `cp_hardware_config.yaml` to record specific power channel currents.

## Development Guidelines
- Use the InstrumentManager for all instrument interactions
- Background tasks should use worker threads to avoid UI freezing
- Configuration files follow specific formats (CSV for DAC, YAML for power)
- Always check instrument connection status before operations
- Simulation mode provides mock data for development and testing

## Skills
This project contains a collection of skills in `.agents/skills/`.
- When starting a new task or refactoring, check this directory for relevant skills.
- Use the `find-skills` skill (if available) or list the directory to discover capabilities.
- Apply the patterns and guidelines defined in these skills to maintain code quality and consistency.
