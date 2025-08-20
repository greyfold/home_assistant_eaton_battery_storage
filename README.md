# Home Assistant Eaton xStorage Home Battery Integration

A Home Assistant custom component for integrating Eaton xStorage Home battery systems.

> ⚠️ This project is not affiliated with or endorsed by Eaton. Use at your own risk.

## Attribution

This project is based on the excellent work by [greyfold](https://github.com/greyfold) in the [home_assistant_eaton_battery_storage](https://github.com/greyfold/home_assistant_eaton_battery_storage) repository. While this integration has been significantly enhanced and restructured, we acknowledge and appreciate the foundational work that made this project possible.

## Features

- Real-time monitoring of battery status and energy flow
- Control charging/discharging modes
- Monitor PV production and grid consumption
- Energy saving mode configuration
- Notifications and alerts management
- Technical status monitoring

## API Documentation

This integration is based on the reverse-engineered REST API of the Eaton xStorage Home system. For detailed API documentation including all endpoints, authentication, and response formats, see:

**xStorage Home REST API Documentation:** <https://github.com/genestealer/eaton-xstorage-home-api-doc/>

## Important Accuracy Warning

> ⚠️ Inverter Power Measurement Accuracy: The built-in inverter energy monitoring has poor accuracy and typically reports power output/consumption values approximately 30% higher than actual values. Do not rely on consumption and production metrics from the inverter for accurate energy calculations. This affects all power-related sensors including grid power, load values, PV production, and consumption metrics.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/Genestealer/homeassistant-eaton-xstorage-home-battery-integration`
6. Select "Integration" as the category
7. Click "Add"
8. Click "Install"
9. Restart Home Assistant
