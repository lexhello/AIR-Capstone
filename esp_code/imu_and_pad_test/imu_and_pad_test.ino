#include <Wire.h>
#include <Adafruit_BNO08x.h>
#include <Trill.h>
#include <math.h>
#include <NimBLEDevice.h>

// -------------------- BLE UART Setup --------------------
NimBLEServer* pServer = nullptr;
NimBLECharacteristic* pCharacteristic = nullptr;
bool deviceConnected = false;

class MyServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* pServer, ble_gap_conn_desc* desc) {
    Serial.println("Client connected");
  }

  void onDisconnect(NimBLEServer* pServer) {
    Serial.println("Client disconnected");
  }
};

// -------------------- BNO08x setup --------------------
#define BNO08X_CS    10
#define BNO08X_INT   9
#define BNO08X_RESET -1

Adafruit_BNO08x bno08x(BNO08X_RESET);
sh2_SensorValue_t sensorValue;
bool bno_ok = false;

// -------------------- Trill setup ---------------------
Trill trillSensor;
bool trillTouchActive = false;
bool trill_ok = false;
bool useTrillSensor = false;

// -------------------- Timers --------------------------
const uint16_t BNO_PERIOD_MS   = 10;   // ~100 Hz
const uint16_t TRILL_PERIOD_MS = 50;   // ~20 Hz
unsigned long nextBNO   = 0;
unsigned long nextTrill = 0;

// -------------------- Motion detection -----------------
float prevVx = 0, prevVy = 0;
float speed = 0;
float strumThreshold = 2.0;
unsigned long lastStrumTime = 0;      
const unsigned long strumCooldown = 100; // ms

// -------------------- Mode control --------------------
// 0 -> BNO only, 1 -> TRILL only
volatile uint8_t mode = 0;

void setBNOReports() {
  bno08x.enableReport(SH2_LINEAR_ACCELERATION);
}

void handleSerialMode() {
  while (Serial.available()) {
    int c = Serial.read();
    if (c == '0') mode = 0;
    else if (c == '1') mode = 1;
  }
}

// Send over BLE UART
void sendBLE(float speed, bool motionEvent, String trillStr) {
  Serial.print(".");
  // snprintf("pcharacteristic: %p\n", pCharacteristic);
  if(deviceConnected && pCharacteristic != nullptr) {
    char buf[128];
    snprintf(buf, sizeof(buf), "Speed:%.3f,Motion:%d,Trill:%s", speed, motionEvent ? 1 : 0, trillStr.c_str());
    pCharacteristic->setValue(buf);
    pCharacteristic->notify();
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  delay(1000); // give time to open serial monitor

  // ---- BLE UART init ----
  NimBLEDevice::init("ESP32_IMU");
  pServer = NimBLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());
  
  NimBLEService* pService = pServer->createService("6E400001-B5A3-F393-E0A9-E50E24DCCA9E");

  NimBLECharacteristic* pTxCharacteristic = pService->createCharacteristic(
    "6E400003-B5A3-F393-E0A9-E50E24DCCA9E",
    NIMBLE_PROPERTY::NOTIFY
  );

  NimBLECharacteristic* pRxCharacteristic = pService->createCharacteristic(
    "6E400002-B5A3-F393-E0A9-E50E24DCCA9E",
    NIMBLE_PROPERTY::WRITE
  );

  pService->start();
  NimBLEAdvertising* pAdvertising = NimBLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(pService->getUUID());
  pAdvertising->start();
  Serial.println("BLE UART ready, waiting for connection...");

  // ---- BNO08x init ----
  if (bno08x.begin_I2C()) {
    bno_ok = true;
    setBNOReports();
  }

  if (useTrillSensor) {
    // ---- Trill init ----
    int ret = trillSensor.setup(Trill::TRILL_FLEX);
    if (ret == 0) {
      trill_ok = true;
      trillSensor.setMode(Trill::CENTROID);
      delay(10);
      trillSensor.setPrescaler(3);
      delay(10);
      trillSensor.setNoiseThreshold(200);
      delay(10);
      trillSensor.updateBaseline();
    }
  }
  

  // Fallback mode
  if (mode == 0 && !bno_ok && trill_ok) mode = 1;
  if (mode == 1 && !trill_ok && bno_ok) mode = 0;
}

void loop() {
  unsigned long now = millis();
  handleSerialMode();

  String trillData = "0.00:0.00";

  // ---- Trill ----
  // if (useTrillSensor) {

  //   if (trill_ok && now >= nextTrill) {
  //     trillSensor.read();
  //     if (trillSensor.getNumTouches() > 0) {
  //       trillData = "";
  //       for (int i = 0; i < trillSensor.getNumTouches(); i++) {
  //         if (i) trillData += ",";
  //         trillData += String(trillSensor.touchLocation(i), 2);
  //         trillData += ":";
  //         trillData += String(trillSensor.touchSize(i), 2);
  //       }
  //       trillTouchActive = true;
  //     } else {
  //       trillTouchActive = false;
  //     }
  //     nextTrill = now + TRILL_PERIOD_MS;
  //   }

  // }
  

  // ---- BNO08x ----
  if (bno_ok && now >= nextBNO) {
      while (bno08x.getSensorEvent(&sensorValue)) {
          if (sensorValue.sensorId == SH2_LINEAR_ACCELERATION) {
              float ax = sensorValue.un.linearAcceleration.x;
              float ay = sensorValue.un.linearAcceleration.y;
              float az = sensorValue.un.linearAcceleration.z;

              float dt = BNO_PERIOD_MS / 1000.0;
              float vx = prevVx + ax * dt;
              float vy = prevVy + ay * dt;
              speed = sqrt(vx*vx + vy*vy);

              // detect strum (acceleration spike)
              bool motionEvent = false;
              float a_mag = sqrt(ax*ax + ay*ay + az*az);
              if (a_mag > strumThreshold && (millis() - lastStrumTime) > strumCooldown) {
                  motionEvent = true;
                  lastStrumTime = millis();
              }

              prevVx = vx;
              prevVy = vy;

              // Send BLE
              sendBLE(speed, motionEvent, trillData);

              // Local print
              Serial.print("Speed: ");
              Serial.print(speed, 3);
              Serial.print(" m/s, Motion: ");
              Serial.print(motionEvent ? "YES" : "NO");
              Serial.print(", TRILL: ");
              Serial.println(trillData);
          }
      }
      nextBNO = now + BNO_PERIOD_MS;
  }


}
