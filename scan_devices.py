#!/usr/bin/env python3
"""Scan for nearby Bluetooth devices using Bleak - with full advertisement data."""

import asyncio
from bleak import BleakScanner

# Springwell advertised service UUID (different from GATT service UUID)
SPRINGWELL_SERVICE_UUID = "8d53dc1d-1db7-4cd3-868b-8a527460aa84"
# Manufacturer ID for Springwell/Chandler Systems
SPRINGWELL_MANUFACTURER_ID = 1850


async def main():
    print("Scanning for Bluetooth devices (10 seconds)...\n")

    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)

    if not devices:
        print("No devices found.")
        return

    print(f"Found {len(devices)} device(s):\n")
    print("=" * 80)

    # Sort by RSSI (signal strength)
    sorted_devices = sorted(
        devices.items(), key=lambda x: x[1][1].rssi or -100, reverse=True
    )

    springwell_found = []

    for address, (device, adv_data) in sorted_devices:
        name = device.name or adv_data.local_name or "Unknown"
        rssi = adv_data.rssi

        # Check if this is a Springwell device
        is_springwell = False

        # Check by service UUID
        if adv_data.service_uuids:
            for uuid in adv_data.service_uuids:
                if SPRINGWELL_SERVICE_UUID.lower() in uuid.lower():
                    is_springwell = True
                    break

        # Check by manufacturer ID
        if adv_data.manufacturer_data:
            if SPRINGWELL_MANUFACTURER_ID in adv_data.manufacturer_data:
                is_springwell = True

        if is_springwell:
            springwell_found.append((address, device, adv_data))

        print(f"Name:              {name}")
        print(f"Address:           {address}")
        print(f"RSSI:              {rssi} dBm")

        if adv_data.service_uuids:
            print(f"Service UUIDs:     {adv_data.service_uuids}")

        if adv_data.manufacturer_data:
            print(f"Manufacturer Data: {adv_data.manufacturer_data}")

        if adv_data.service_data:
            print(f"Service Data:      {adv_data.service_data}")

        if adv_data.tx_power:
            print(f"TX Power:          {adv_data.tx_power}")

        if is_springwell:
            print(">>> SPRINGWELL DEVICE DETECTED <<<")

        print("-" * 80)

    # Summary
    print("\n" + "=" * 80)
    if springwell_found:
        print(f"\n✓ Found {len(springwell_found)} Springwell device(s):\n")
        for addr, dev, adv in springwell_found:
            name = dev.name or adv.local_name or "Unknown"
            print(f"  - {name} ({addr})")
    else:
        print("\n✗ No Springwell devices found.")
        print(f"  (Looking for service UUID: {SPRINGWELL_SERVICE_UUID})")


if __name__ == "__main__":
    asyncio.run(main())
