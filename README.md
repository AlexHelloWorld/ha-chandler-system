# Chandler Water System Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration to monitor and control Chandler Systems water treatment devices (SpringWell / Chandler softeners, filters, etc.) via Bluetooth Low Energy using the official [Chandler Signature API](https://github.com/ChandlerSystems/Signature-API-Guide).

## Supported Devices

- SpringWell Water Softeners & Filters (Chandler Systems valves, firmware C6.13+)
- Other Chandler Systems Legacy View / Signature Bluetooth valves (C6.18 and C6.19+)

## Key Features

- **Stable Short-Lived BLE Polling:** Connects briefly (~3–5 s), drains the state dump, sends the graceful `R` device-reset byte before disconnecting, and observes an inter-session cooldown so the valve radio doesn't lock up and the mobile app stays usable.
- **Fast Flow-Aware Water Tracking:** Polls every **60 s** when idle (configurable down to 15 s) and automatically speeds up to **15 s** while water is actively flowing (`Current Flow Rate > 0 GPM`).
- **Automatic Firmware Detection:** Reads firmware version (`dlf` / `gef`), serial number, valve type, and valve series from the handshake and automatically selects `/ 100` (C6.18 and older) vs. `/ 4` (C6.19+) for historical gallon counters.
- **Automatic Clock Sync:** Detects valve clock drift accurately against the packet sample timestamp and automatically syncs the valve clock inside the same poll session whenever drift exceeds your threshold (skipped during active regenerations).
- **Full Regeneration Visibility:** Tracks active state, stage (`Position X of Y` / `Brine Soak` / `Aeration`), step minutes remaining, estimated total minutes remaining, motor movement, and configured cycle position times.
- **Full Write Controls:** Water hardness, day overrides, regeneration hour, reserve capacity, auto reserve, total grains capacity, brine prefill, salt refill, counter resets, regeneration triggers, and cycle position times.
- **Native Home Assistant Water Dashboard Support & Local Brand Icons:** Cumulative gallon sensors use `device_class: water` (`total_increasing`), and light/dark brand icons are bundled in `brand/` for HA 2026.3+.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant → **Integrations** → **`⋮`** → **Custom repositories**
2. Add `https://github.com/AlexHelloWorld/ha-chandler-system` with category **Integration**
3. Install and restart Home Assistant

### Manual Installation

1. Copy `custom_components/chandler_system` into your Home Assistant `/config/custom_components/` directory
2. Restart Home Assistant

## Configuration & Options

1. Go to **Settings → Devices & Services → + Add Integration → Chandler Water System**
2. Select your discovered valve (or enter its BLE address) and paste the API token from the Chandler/SpringWell app (**Settings → API**)
3. Click **Configure** on the integration card anytime to tune:
   - **Normal poll interval** (`15–3600 s`, default `60 s`)
   - **Active water flow poll interval** (`0–300 s`, default `15 s`; `0` disables speedup)
   - **Automatically sync valve clock** (default enabled)
   - **Clock drift threshold** (`30–3600 s`, default `120 s`)

## Entities

### Water Usage & Flow
| Entity | Type | Notes |
|--------|------|-------|
| Water Used Today | Sensor | Gallons (`water`, Energy Dashboard compatible) |
| Total Gallons Processed | Sensor | Lifetime gallons (`water`, firmware-aware C6.18 / C6.19+) |
| Gallons Since Last Regeneration | Sensor | Gallons (`water`, firmware-aware) |
| Gallons Since Reset | Sensor | Resettable gallons (`water`, firmware-aware) |
| Treated Water Remaining | Sensor | Softened gallons remaining before regen |
| Average Daily Water Usage | Sensor | Rolling daily average |
| Reserve Capacity Gallons | Sensor | Calculated reserve capacity |
| Current Flow Rate | Sensor | Live flow in `gal/min` |
| Peak Flow Today | Sensor | Peak daily flow in `gal/min` |

### Regeneration Status
| Entity | Type | Notes |
|--------|------|-------|
| Regeneration Active | Binary Sensor | Running / Idle |
| Regeneration State | Sensor | Valve state machine enum (`Idle`, `Waiting In Position`, `Waiting In Brine Soak`, etc.) |
| Regeneration Stage | Sensor | `Idle`, `Brine Soak`, `Aeration`, or `Position X of Y` |
| Regeneration Step Time Remaining | Sensor | Minutes remaining in current step (`0` when idle) |
| Regeneration Total Time Remaining | Sensor | Estimated total minutes left across current & remaining cycle positions |
| Brine Soak Time Remaining | Sensor | Minutes left in brine soak |
| Regeneration Position | Sensor (Diagnostic) | Raw position index with `total_positions` attribute |
| Cycle Position Times | Sensor (Diagnostic) | Configured `aspt` step times |
| Regeneration Motor Moving | Binary Sensor (Diagnostic) | `dlr` motor movement flag |
| In Aeration / In Brine Soak | Binary Sensor (Diagnostic) | Sub-phase flags |
| Days Until / Since Last Regeneration | Sensor | Days |
| Total / Resettable Regeneration Cycles | Sensor | Cycle counters |

### Salt, Diagnostics & History
| Entity | Type | Notes |
|--------|------|-------|
| Salt Level / Salt Remaining / Salt Tank Capacity | Sensor | `%` and `lb` |
| Salt Low / Valve Error | Binary Sensor | Problem alerts |
| Valve Error Detail / Last Error | Sensor (Diagnostic) | Current fault & 20-entry `error_log` attribute |
| Battery Voltage / Days In Operation | Sensor (Diagnostic) | `V` and days |
| Device Time / Clock Drift | Sensor (Diagnostic) | Valve clock & drift in seconds (sampled at receipt) |
| Firmware Version / Valve Type | Sensor (Diagnostic) | Auto-detected from handshake (`dlf`/`gef`, `dlvt`/`gedt`, serial, series) |
| Gallons Used Last Regeneration Cycle / Yesterday / Peak Flow Yesterday | Sensor (Diagnostic) | Graph histories in `history` attribute |

### Controls (Writable Entities)
> [!WARNING]
> **Start Regeneration Now** immediately starts a real regeneration cycle using water and salt and **cannot be cancelled** via the API.

| Entity | Type | Key / Range |
|--------|------|-------------|
| Refresh Now | Button | Triggers an immediate BLE poll |
| Start Regeneration Now / Schedule Regeneration / Find Home | Button | `grn`, `grl`, `gfh` |
| Sync Clock | Button | Writes `dh`, `dm`, `ds` from HA local time |
| Refill Salt Tank | Button | Sets `dbtr` to configured `dbts` tank capacity |
| Reset Regeneration Counter / Reset Gallons Counter | Button | Writes `shrr: 0` / `shgr: 0` |
| Water Hardness | Number | `dwh` (`0–99` GPG) |
| Day Override / Current Day Override / Regen Day Override | Number | `ddo`, `dcdo`, `asr` (`0–29` days) |
| Regeneration Hour | Number | `drth` (`0–23` h) |
| Reserve Capacity | Number | `asrc` (`0–49` %) |
| Total Grains Capacity | Number | `astg` (`0–399,000` grains, step `1,000`) |
| Salt Remaining Setting | Number | `dbtr` (`0–400` lb) |
| Brine Prefill Duration | Number | `dpd` (`1–4` hours) |
| Aeration Days / Chlorine Pulses | Number (disabled by default) | `asad` (`0–9`), `ascp` (`0–4`) |
| Auto Reserve Mode / Brine Prefill / Display Off | Switch | `asar`, `dpe`, `asdo` |

## Services

| Service | Description |
|---------|-------------|
| `chandler_system.start_regeneration` | Start a cycle `now` or at `next_scheduled` |
| `chandler_system.find_home` | Locate the valve's home position |
| `chandler_system.set_salt_level` | Record pounds of salt currently in the brine tank |
| `chandler_system.reset_counters` | Zero resettable regeneration and/or gallon counters |
| `chandler_system.sync_clock` | Set the valve's clock from Home Assistant's local time |
| `chandler_system.set_cycle_position_times` | Set `aspt` step durations (automatically preserves index 0 service slot) |

## Development & Testing

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_dev.txt
pytest tests/
ruff check custom_components/ tests/
```

## License

MIT License — see [LICENSE](LICENSE). Not affiliated with Chandler Systems, Inc. or SpringWell Water.
