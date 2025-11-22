#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

BLECharacteristic *pCharacteristic;

// ---- Inputs ----
// Ball tilt: one leg -> 3.3V, other -> D0 (GPIO1) + 10kΩ to GND
const int TILT_PIN = 1;     // HIGH=CLOSED, LOW=OPEN
// FSR: 3.3V -> FSR -> Node -> 10kΩ -> GND, Node -> A1 (D1)
const int FSR_PIN  = A1;

// ---- Timing ----
const unsigned long LOCKOUT_MS    = 5;     // short ISR lockout
const unsigned long DEBOUNCE_MS   = 50;    // tilt must be stable this long
const unsigned long REFRACTORY_MS = 500;   // min gap between sends

// ---- FSR thresholds (tune after reading serial output) ----
const int FSR_PRESS_ON  = 500;  // above = pressed
const int FSR_PRESS_OFF = 400;   // below = released

// ---- ISR communication ----
volatile bool edgeFlag = false;
volatile unsigned long lastIrqMs = 0;

void IRAM_ATTR tiltISR() {
  unsigned long now = millis();
  if (now - lastIrqMs >= LOCKOUT_MS) {
    lastIrqMs = now;
    edgeFlag = true;
  }
}

static inline void sendOne() {
  if (!pCharacteristic) return;
  pCharacteristic->setValue("1");
  pCharacteristic->notify();
  Serial.println("Sent: 1");
}

void setup() {
  Serial.begin(115200);
  Serial.println("Starting BLE with FSR gate...");

  // ---- BLE setup ----
  BLEDevice::init("XIAO_ESP32S3");
  BLEServer *server = BLEDevice::createServer();
  BLEService *service = server->createService(SERVICE_UUID);
  pCharacteristic = service->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_WRITE
  );
  pCharacteristic->setValue("BOOT");
  service->start();

  auto *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(SERVICE_UUID);
  adv->setScanResponse(true);
  adv->setMinPreferred(0x06);
  adv->setMinPreferred(0x12);
  BLEDevice::startAdvertising();

  // ---- IO ----
  pinMode(TILT_PIN, INPUT); // external pulldown
  attachInterrupt(digitalPinToInterrupt(TILT_PIN), tiltISR, CHANGE);

  Serial.println("✅ Ready: will send '1' on strum when FSR is pressed.");
}

void loop() {
  static unsigned long lastSendMs = 0;
  static int lastStableState = -1;
  static unsigned long tCandidate = 0;
  static int candidateState = -1;

  // ---- FSR read + hysteresis ----
  static bool fsrPressed = false;
  int fsrValue = analogRead(FSR_PIN); // A1/D1 analog input (0–4095)
  if (!fsrPressed && fsrValue >= FSR_PRESS_ON) fsrPressed = true;
  else if (fsrPressed && fsrValue <= FSR_PRESS_OFF) fsrPressed = false;

  // Uncomment this line temporarily to calibrate threshold
  Serial.printf("FSR=%d pressed=%d\n", fsrValue, fsrPressed);

  // ---- Tilt debounce ----
  if (edgeFlag) {
    noInterrupts();
    edgeFlag = false;
    unsigned long irqTime = lastIrqMs;
    interrupts();

    tCandidate = irqTime;
    candidateState = digitalRead(TILT_PIN);
  }

  if (tCandidate) {
    int nowState = digitalRead(TILT_PIN);
    unsigned long now = millis();

    if (nowState != candidateState) {
      candidateState = nowState;
      tCandidate = now;
    }

    if ((now - tCandidate) >= DEBOUNCE_MS) {
      if (candidateState != lastStableState &&
          (now - lastSendMs) >= REFRACTORY_MS &&
          fsrPressed) {
        sendOne();                   // only send if FSR is pressed
        lastSendMs = now;
      }
      lastStableState = candidateState;
      tCandidate = 0;
    }
  }
}
