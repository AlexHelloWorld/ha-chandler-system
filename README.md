# Springwell Water Softener Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration to monitor and control your Springwell water softener via Bluetooth.

## Features

- 📊 Monitor salt level
- 💧 Track water flow (coming soon)
- 🔄 View regeneration status (coming soon)
- 📱 Bluetooth Low Energy (BLE) connectivity

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

1. Copy the `custom_components/springwell_softener` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Springwell Water Softener"
4. Enter your softener's Bluetooth MAC address
5. Click **Submit**

### Finding Your Device's Bluetooth Address

You can find your Springwell softener's Bluetooth address by:
- Using a Bluetooth scanner app on your phone
- Checking your device's documentation
- Looking in the manufacturer's mobile app

## Supported Devices

- Springwell Water Softener (Bluetooth-enabled models)

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| Salt Level | Sensor | Current salt level percentage |

## Troubleshooting

### Device not found
- Ensure Bluetooth is enabled on your Home Assistant host
- Make sure the softener is powered on and in range
- Verify the Bluetooth address is correct

### Connection issues
- Try restarting Home Assistant
- Check if other devices can connect to the softener
- Ensure no other device is currently connected to the softener

## Development

### Setting up the development environment

```bash
# Clone the repository
git clone https://github.com/your-username/ha_springwell_softener.git
cd ha_springwell_softener

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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with or endorsed by Springwell. Use at your own risk.

