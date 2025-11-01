import serial
import struct
import queue
import threading
import time

class ESP32Receiver:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        """
        Initialize ESP32 receiver with serial connection
        
        Args:
            port: Serial port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate: Serial baudrate (must match ESP32 setting)
        """
        self.port = port
        self.baudrate = baudrate
        self.data_queue = queue.Queue()
        self.running = False
        self.serial_conn = None
        
    def connect(self):
        """Establish serial connection to ESP32"""
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Connected to {self.port} at {self.baudrate} baud")
            time.sleep(2)  # Wait for connection to stabilize
            return True
        except serial.SerialException as e:
            print(f"Error connecting to {self.port}: {e}")
            return False
    
    def parse_packet(self, data):
        """
        Parse binary packet data
        Expected structure: int (4), float (4), float (4), unsigned long (4) = 16 bytes
        """
        if len(data) >= 16:
            try:
                packet_id, temp, humidity, timestamp = struct.unpack('<iffI', data[:16])
                return {
                    'id': packet_id,
                    'temperature': temp,
                    'humidity': humidity,
                    'timestamp': timestamp
                }
            except struct.error as e:
                print(f"Error parsing packet: {e}")
        return None
    
    def read_serial(self):
        """Read data from serial port and add to queue"""
        buffer = b''
        
        while self.running:
            try:
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    byte = self.serial_conn.read(1)
                    buffer += byte
                    
                    # Look for packet markers or process when we have enough bytes
                    if len(buffer) >= 16:
                        packet = self.parse_packet(buffer[:16])
                        if packet:
                            self.data_queue.put(packet)
                            print(f"Received: ID={packet['id']}, "
                                  f"Temp={packet['temperature']:.1f}°C, "
                                  f"Humidity={packet['humidity']:.1f}%, "
                                  f"Timestamp={packet['timestamp']}")
                        buffer = buffer[16:]  # Remove processed data
                        
            except serial.SerialException as e:
                print(f"Serial read error: {e}")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                time.sleep(0.1)
    
    def start(self):
        """Start receiving data in background thread"""
        if not self.serial_conn:
            if not self.connect():
                return False
        
        self.running = True
        self.thread = threading.Thread(target=self.read_serial, daemon=True)
        self.thread.start()
        print("Receiver started")
        return True
    
    def stop(self):
        """Stop receiving data"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2)
        if self.serial_conn:
            self.serial_conn.close()
        print("Receiver stopped")
    
    def get_packet(self, timeout=None):
        """
        Get packet from queue
        
        Args:
            timeout: Maximum time to wait for packet (None = block indefinitely)
        
        Returns:
            Packet dictionary or None if timeout
        """
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None


# Example usage
if __name__ == "__main__":
    # Initialize receiver (adjust port for your system)
    # Windows: 'COM3', Linux: '/dev/ttyUSB0', Mac: '/dev/cu.usbserial-*'
    # receiver = ESP32Receiver(port='/dev/ttyUSB0', baudrate=115200)
    receiver = ESP32Receiver(port='/dev/cu.usbserial-*', baudrate=115200)
    
    try:
        if receiver.start():
            print("Waiting for packets... (Press Ctrl+C to stop)")
            
            # Process packets from queue
            while True:
                packet = receiver.get_packet(timeout=1)
                if packet:
                    # Process the packet (already printed in read_serial)
                    pass
                
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        receiver.stop()