import asyncio
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

async def main():
    print("🔍 Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=6.0)

    target = None
    for d in devices:
        print(f"- {d.name or 'Unknown'} ({d.address})")
        if d.name and "XIAO_ESP32S3" in d.name:
            target = d
            break

    if not target:
        print("❌ Could not find XIAO_ESP32S3. Make sure it's powered and advertising.")
        return

    print(f"\n✅ Found device: {target.name} [{target.address}]")
    print("Connecting...")

    async with BleakClient(target.address) as client:
        if not await client.is_connected():
            print("❌ Failed to connect.")
            return

        print("✅ Connected to ESP32 BLE Server")

        # --- Read initial value ---
        try:
            value = await client.read_gatt_char(CHARACTERISTIC_UUID)
            print(f"📖 Initial characteristic value: {value.decode('utf-8', errors='ignore')}")
        except Exception as e:
            print("⚠️ Error reading characteristic:", e)

        # --- Write a new value ---
        try:
            new_value = "Hello from macOS 🧠"
            await client.write_gatt_char(CHARACTERISTIC_UUID, new_value.encode('utf-8'))
            print(f"✍️ Wrote new value: {new_value}")
        except Exception as e:
            print("⚠️ Error writing characteristic:", e)

        # --- Verify write ---
        try:
            updated = await client.read_gatt_char(CHARACTERISTIC_UUID)
            print(f"📖 Updated characteristic value: {updated.decode('utf-8', errors='ignore')}")
        except Exception as e:
            print("⚠️ Error re-reading characteristic:", e)

    print("🔌 Disconnected.")

asyncio.run(main())
