#!/usr/bin/env python3
"""Demo client for Chandler Water System devices."""

import asyncio
import json
from enum import Enum

from bleak import BleakClient

AUTH_REQUEST = "EA"
ACK_REQUEST = "CC"
KEEP_ALIVE_REQUEST = "E0"
KEEP_ALIVE_REPLY = "F0"

# Update these values for your device
AUTH_TOKEN = "C2D603F86EE649E3BFD8946821EEFF55"
DEVICE_ADDRESS = "66CA6B53-55A5-6664-28DF-6929668E225A"

# Chandler Systems GATT characteristics
READ_CHAR = "a725458c-bee2-4d2e-9555-edf5a8082303"
WRITE_CHAR = "a725458c-bee3-4d2e-9555-edf5a8082303"


class Status(Enum):
    UNKNOWN = 0
    READY_TO_CONNECT = 1
    WAITING_TO_SEND_AUTH = 2
    RUNNING = 3


def is_ack(data):
    return data.hex().upper() == ACK_REQUEST


class ChandlerDemoClient:
    """Demo client for testing Chandler device communication."""

    def __init__(self, address, auth_token):
        self.client = BleakClient(address)
        self._data_buffer = bytearray()
        self._notification_queue = asyncio.Queue()
        self._auth_token = bytearray.fromhex(auth_token)
        self._status = Status.READY_TO_CONNECT

    def _notification_callback(self, sender, data):
        print(f"Receive: {data.hex()}")
        self._notification_queue.put_nowait(data)

    async def _send_packet(self, bytearray):
        print(f"Send: {bytearray.hex()}")
        await self.client.write_gatt_char(WRITE_CHAR, bytearray, response=False)

    async def _wait_for_response(self, timeout=3.0):
        return await asyncio.wait_for(
            self._notification_queue.get(), timeout=timeout
        )

    async def _authenticate(self):
        # 1. Sends initial authenticate request.
        await self._send_packet(bytearray.fromhex(AUTH_REQUEST))
        self._status = Status.WAITING_TO_SEND_AUTH
        while self._status == Status.WAITING_TO_SEND_AUTH:
            data = await self._wait_for_response()
            if is_ack(data):
                await self._send_packet(self._auth_token)
                self._status = Status.RUNNING
            else:
                await self._send_packet(bytearray.fromhex(ACK_REQUEST))

    async def connect(self):
        await self.client.connect()
        await self.client.start_notify(READ_CHAR, self._notification_callback)
        await self._authenticate()

    async def clean(self):
        if self.client.is_connected:
            await self.client.stop_notify(READ_CHAR)
            await asyncio.sleep(0.3)
            await self.client.write_gatt_char(WRITE_CHAR, b"R", response=False)
            await asyncio.sleep(0.3)

    def parse_json(self):
        payload = self._data_buffer
        try:
            return json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Failed to decode JSON: {e}")
            return None

    async def monitor_loop(self):
        while self._status == Status.RUNNING:
            try:
                data = await self._wait_for_response(timeout=30.0)
                hex_val = data.hex().upper()
                if hex_val == KEEP_ALIVE_REQUEST:
                    await self._send_packet(bytearray.fromhex(KEEP_ALIVE_REPLY))
                    continue

                if is_ack(data):
                    continue

                # Sends ACK first for any data packet.
                await self._send_packet(bytearray.fromhex(ACK_REQUEST))
                self._data_buffer.extend(data[1:-2])
                is_last_packet = (data[0] & 0x40) != 0
                if is_last_packet:
                    parsed_json_data = self.parse_json()
                    print(f"Parsed JSON data: {parsed_json_data}")
                    self._data_buffer.clear()

            except asyncio.TimeoutError:
                break
            except Exception:
                break


async def main():
    client = ChandlerDemoClient(address=DEVICE_ADDRESS, auth_token=AUTH_TOKEN)
    try:
        await client.connect()
        await client.monitor_loop()
    finally:
        await client.clean()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
