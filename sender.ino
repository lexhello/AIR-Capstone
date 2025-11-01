#include <esp_now.h>
#include <WiFi.h>

// Receiver MAC address - REPLACE WITH YOUR RECEIVER ESP32 MAC ADDRESS
uint8_t receiverMAC[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}; // Broadcast address

// Structure to hold transmitted data
typedef struct {
  int id;
  float temperature;
  float humidity;
  unsigned long timestamp;
} DataPacket;

DataPacket packet;
int packetCounter = 0;

// Callback when data is sent
void onDataSent(const uint8_t *mac, esp_now_send_status_t status) {
  Serial.print("Packet Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // Set device as Wi-Fi station
  WiFi.mode(WIFI_STA);
  
  // Print MAC address
  Serial.print("ESP32 MAC Address: ");
  Serial.println(WiFi.macAddress());
  
  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // Register send callback
  esp_now_register_send_cb(onDataSent);
  
  // Register peer
  esp_now_peer_info_t peerInfo;
  memcpy(peerInfo.peer_addr, receiverMAC, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }
  
  Serial.println("ESP-NOW Transmitter Ready");
}

void loop() {
  // Prepare data packet
  packet.id = packetCounter++;
  packet.temperature = random(200, 300) / 10.0; // Simulate 20.0-30.0°C
  packet.humidity = random(400, 800) / 10.0;    // Simulate 40.0-80.0%
  packet.timestamp = millis();
  
  // Send packet via ESP-NOW
  esp_err_t result = esp_now_send(receiverMAC, (uint8_t *)&packet, sizeof(packet));
  
  if (result == ESP_OK) {
    Serial.print("Sent packet #");
    Serial.print(packet.id);
    Serial.print(" | Temp: ");
    Serial.print(packet.temperature);
    Serial.print("°C | Humidity: ");
    Serial.print(packet.humidity);
    Serial.println("%");
  } else {
    Serial.println("Error sending packet");
  }
  
  delay(2000); // Send every 2 seconds
}