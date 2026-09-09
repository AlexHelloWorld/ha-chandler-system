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
- 🔄 Follow a regeneration cycle live — state, valve position, and step timers
- ▶️ Start a regeneration on demand, or queue one for the next scheduled time
- ⚙️ Adjust settings from HA: water hardness, day override, reserve capacity, and more
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
| Salt Level | Sensor | Percentage remaining |
| Salt Remaining | Sensor | Pounds remaining |
| Water Hardness | Sensor | Configured GPG |
| Battery Voltage | Sensor | Battery level in volts |
| Days In Operation | Sensor | Total days active |
| Reserve Capacity | Sensor | Reserve gallons |
| Total Grains Capacity | Sensor | System capacity |
| Salt Low | Binary Sensor | Problem when the brine tank is low |
| Valve Error | Binary Sensor | Problem when the valve reports a fault |

### Regeneration

| Entity | Type | Description |
|--------|------|-------------|
| Regeneration Active | Binary Sensor | Whether a cycle is running right now |
| Regeneration State | Sensor | Current step, e.g. "Waiting In Brine Soak" |
| Regeneration Position | Sensor | Valve position, with `total_positions` attribute |
| Regeneration Step Time Remaining | Sensor | Seconds left in the current step |
| Brine Soak Time Remaining | Sensor | Minutes left in the brine soak |
| In Aeration | Binary Sensor | Whether the cycle is in aeration |
| In Brine Soak | Binary Sensor | Whether the cycle is in brine soak |
| Regenerations Since Reset | Sensor | Resettable regen count |
| Gallons Since Reset | Sensor | Resettable gallon total |
| Scheduled Regeneration Time | Sensor | Hour of day regens are scheduled for |
| Gallons Used Last Regeneration Cycle | Sensor | With a `history` attribute of prior cycles |
| Last Error | Sensor | Most recent fault, with the full 20-entry `error_log` attribute |

### Controls

> [!WARNING]
> **Start Regeneration Now** immediately begins a real regeneration cycle. It uses
> water and salt, takes the system offline for the duration, and **cannot be
> cancelled** — the API has no abort command. Consider hiding this button or
> putting it behind a confirmation in your dashboard.

| Entity | Type | Description |
|--------|------|-------------|
| Start Regeneration Now | Button | Begins a cycle immediately |
| Schedule Regeneration | Button | Queues a cycle for the next scheduled time |
| Find Home | Button | Returns the valve to its home position |
| Water Hardness Setting | Number | 0–99 GPG |
| Day Override | Number | 0–29 days between forced regens |
| Regeneration Hour | Number | 0–23, hour of day regens run |
| Reserve Capacity Setting | Number | 0–49 % |
| Total Grains Capacity Setting | Number | Up to 399,000 grains |
| Salt Remaining Setting | Number | Record a brine tank refill |
| Auto Reserve Mode | Switch | Automatic vs. manual reserve |
| Display Off | Switch | Turn the valve's display off |

## Services

| Service | Description |
|---------|-------------|
| `chandler_system.start_regeneration` | Start a cycle `now` or at the `next_scheduled` time |
| `chandler_system.find_home` | Locate the valve's home position |
| `chandler_system.set_salt_level` | Record pounds of salt after a refill |
| `chandler_system.reset_counters` | Zero the resettable regen and gallon counters |
| `chandler_system.sync_clock` | Set the valve's clock from Home Assistant |

```yaml
# Regenerate when salt is topped up and the tank is nearly exhausted
action:
  - service: chandler_system.start_regeneration
    data:
      device_id: !input water_system
      when: next_scheduled
```

### A note on writes

The valve silently ignores a write that matches the value it already holds, and
ignores keys it does not accept. A successful call therefore means the command
was *delivered* — not that anything changed. Watch the relevant sensor to
confirm an actual change.

### Replaced entities

The `Regeneration Active`, `Salt Low Alert`, and `Valve Error` **sensors** are
superseded by binary sensors of the same name and are now disabled for new
installs. Existing installs keep them enabled so dashboards don't break; you can
disable them manually once you've switched to the binary sensors.

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
