import asyncio
from bleak import BleakScanner, BleakClient
from PyQt5.QtCore import QTimer

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

class BLEReader:
    """
    BLEReader subscribes to a notify-only characteristic.
    When a notification is received, it sets `event_flag[0] = True`.
    """

    def __init__(self, address: str, client: BleakClient, event_flag: list):
        """
        :param address: BLE device address
        :param client: BleakClient instance
        :param event_flag: list containing a single boolean element,
                           which will be set to True on notification
        """
        self.address = address
        self.client = client
        self.event_flag = event_flag

    @classmethod
    async def create(cls, event_flag: list):
        """
        Scan, connect, and return BLEReader instance with event_flag pointer.
        """
        print("🔍 Scanning for BLE devices...")
        devices = await BleakScanner.discover(timeout=6.0)

        target = None
        for d in devices:
            print(f"- {d.name or 'Unknown'} ({d.address})")
            if d.name and "XIAO_ESP32S3" in d.name:
                target = d
                break

        if not target:
            raise RuntimeError("Could not find XIAO_ESP32S3.")

        print(f"\nFound device: {target.name} [{target.address}]")
        print("Connecting...")

        client = BleakClient(target.address)
        await client.connect()

        if not client.is_connected:
            raise RuntimeError("Failed to connect to ESP32 BLE Server")

        print("CONNECTED !!  to ESP32 BLE Server")

        reader = cls(target.address, client, event_flag)
        await reader.start_notify()
        print("awaiting reader")
        return reader

    async def start_notify(self):
        """
        Subscribe to the notify-only characteristic.
        """
        await self.client.start_notify(CHARACTERISTIC_UUID, self._notification_handler)
        print("Subscribed to notifications.")

    def _notification_handler(self, sender: int, data: bytearray):
        """
        Called automatically by Bleak when the characteristic notifies.
        Sets the boolean to True.
        """
        decoded = data.decode('utf-8', errors='ignore')
        QTimer.singleShot(0, lambda: print(f"Notification received from {sender}|||| {decoded}", flush=True))
        self.event_flag[0] = True

    async def disconnect(self):
        """
        Stop notifications and disconnect.
        """
        try:
            await self.client.stop_notify(CHARACTERISTIC_UUID)
        except Exception:
            pass
        await self.client.disconnect()
        print("Disconnected.")
