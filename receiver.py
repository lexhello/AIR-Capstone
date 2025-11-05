import asyncio
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
TIMEOUT_MS = 50

class BLEReader:
    def __init__(self, address: str, client: BleakClient):
        self.address = address
        self.client = client

    # 🧩 Async factory method — performs scanning and connection
    @classmethod
    async def create(cls):
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

        print(f"\n Found device: {target.name} [{target.address}]")
        print("Connecting...")

        client = BleakClient(target.address)
        await client.connect()

        if not client.is_connected:
            raise RuntimeError("Failed to connect to ESP32 BLE Server")

        print("CONNECTED !!  to ESP32 BLE Server")
        return cls(target.address, client)

    async def read_characteristic(self):
        # value = await self.client.read_gatt_char(CHARACTERISTIC_UUID)
        try:
            value = await asyncio.wait_for(
                    self.client.read_gatt_char(CHARACTERISTIC_UUID),
                    timeout=TIMEOUT_MS / 1000.0
                )
        except asyncio.TimeoutError:
            return None, None
        except Exception as e:
            print(f"Error reading characteristic: {e}")
            return None, None
        
        decoded = value.decode('utf-8', errors='ignore')
        speed_bucket, new_strum = decoded.strip().split(',')
        print(f"Read value: {decoded}")
        return speed_bucket, new_strum

    async def disconnect(self):
        await self.client.disconnect()
        print("Disconnected.")


# --- Example usage ---
# async def main():
#     try:
#         ble = await BLEReader.create()  # async constructor

#         await ble.read_characteristic()
#         await ble.write_characteristic("Hello from macOS 🧠")
#         await ble.read_characteristic()

#     except Exception as e:
#         print(f"⚠️ Error: {e}")

#     finally:
#         if 'ble' in locals():
#             await ble.disconnect()


# if __name__ == "__main__":
#     asyncio.run(main())
