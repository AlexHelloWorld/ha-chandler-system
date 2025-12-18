#!/usr/bin/env python3
"""Scan for nearby Bluetooth devices using Bleak."""

import asyncio
from bleak import BleakScanner


async def main():
    print("Scanning for Bluetooth devices (10 seconds)...\n")
    
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    
    if not devices:
        print("No devices found.")
        return
    
    print(f"Found {len(devices)} device(s):\n")
    print("-" * 80)
    
    # Sort by RSSI (signal strength)
    sorted_devices = sorted(devices.items(), key=lambda x: x[1][1].rssi or -100, reverse=True)
    
    for address, (device, adv_data) in sorted_devices:
        name = device.name or adv_data.local_name or "Unknown"
        rssi = adv_data.rssi
        print(f"Name:    {name}")
        print(f"Address: {address}")
        print(f"RSSI:    {rssi} dBm")
        print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())

