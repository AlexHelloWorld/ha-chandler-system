# Chandler Water System Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration to monitor and control Chandler Systems water treatment devices (softeners, filters, etc.) via Bluetooth.

## Supported Devices

- Springwell Water Softener (powered by Chandler Systems)
- Springwell Water Filter (powered by Chandler Systems)
- Other Chandler Systems Bluetooth-enabled water treatment devices

## Features

- 📊 Monitor salt level and remaining capacity
- 💧 Track water flow and daily usage
- 🔄 View regeneration status and history
- 🔋 Monitor battery voltage
- 📱 Bluetooth Low Energy (BLE) connectivity
- 🔍 Auto-discovery of nearby devices

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL with category "Integration"
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/chandler_system` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Chandler Water System"
4. If devices are discovered, select one from the list
5. Enter your authentication token (from the manufacturer's app)
6. Click **Submit**

### Getting Your Authentication Token

The authentication token can be found in the manufacturer's mobile app:
1. Open the Springwell/Chandler app on your phone
2. Navigate to Settings > API
3. Copy the API token (UUID format)

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| Water Used Today | Sensor | Gallons used today |
| Average Daily Water Usage | Sensor | Rolling average usage |
| Treated Water Remaining | Sensor | Gallons until regeneration |
| Total Gallons Processed | Sensor | Lifetime total |
| Current Flow Rate | Sensor | Real-time flow (gal/min) |
| Peak Flow Today | Sensor | Maximum flow rate today |
| Days Until Regeneration | Sensor | Estimated days |
| Days Since Last Regeneration | Sensor | Days since last regen |
| Total Regeneration Cycles | Sensor | Lifetime regen count |
| Regeneration Active | Sensor | On/Off status |
| Salt Level | Sensor | Percentage remaining |
| Salt Remaining | Sensor | Pounds remaining |
| Salt Low Alert | Sensor | OK/Low status |
| Water Hardness | Sensor | Configured GPG |
| Battery Voltage | Sensor | Battery level in volts |
| Days In Operation | Sensor | Total days active |
| Valve Error | Sensor | Error status |
| Reserve Capacity | Sensor | Reserve gallons |
| Total Grains Capacity | Sensor | System capacity |

## Troubleshooting

### Device not found
- Ensure Bluetooth is enabled on your Home Assistant host
- Make sure the device is powered on and in range
- Verify no other device (like your phone) is connected to it

### Connection issues
- Try restarting Home Assistant
- Check if other devices can connect to the water system
- Ensure no other device is currently connected

### Authentication failed
- Verify your auth token is correct (UUID format)
- Try regenerating the token in the manufacturer's app

## Development

### Setting up the development environment

```bash
# Clone the repository
git clone https://github.com/AlexHelloWorld/ha-chandler-system.git
cd ha-chandler-system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements_dev.txt
```

### Running tests

```bash
pytest tests/
```

### Testing BLE Connection

```bash
# Scan for nearby devices
python scan_devices.py

# Test connection with demo client
python client_demo.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with or endorsed by Chandler Systems, Inc. or Springwell Water. Use at your own risk.

## Credits

- Chandler Systems, Inc. for the Bluetooth API documentation
- Home Assistant community for integration patterns
