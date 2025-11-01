#include <Wire.h>
#include <Adafruit_BNO08x.h>
#include <Trill.h>

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

// -------------------- Timers --------------------------
const uint16_t BNO_PERIOD_MS   = 10;   // ~100 Hz
const uint16_t TRILL_PERIOD_MS = 50;   // ~20 Hz
unsigned long nextBNO   = 0;
unsigned long nextTrill = 0;

// -------------------- Mode control --------------------
// 0 -> BNO only, 1 -> TRILL only
volatile uint8_t mode = 0;

void setBNOReports() { bno08x.enableReport(SH2_GAME_ROTATION_VECTOR); }

void handleSerialMode() {
  while (Serial.available()) {
    int c = Serial.read();
    if (c == '0') mode = 0;
    else if (c == '1') mode = 1;
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin();

  // --------- Try BNO08x (non-blocking on failure) ----------
  if (bno08x.begin_I2C()) {
    bno_ok = true;
    setBNOReports();
  }

  // --------- Try Trill (non-blocking on failure) -----------
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

  // If default mode is unavailable, fall back to the other if present
  if (mode == 0 && !bno_ok && trill_ok) mode = 1;
  if (mode == 1 && !trill_ok && bno_ok) mode = 0;
}

void loop() {
  unsigned long now = millis();

  // Always listen for '0' / '1'
  handleSerialMode();

  // -------------------- BNO08x service ----------------
  if (mode == 0 && bno_ok && now >= nextBNO) {
    if (bno08x.wasReset()) setBNOReports();

    while (bno08x.getSensorEvent(&sensorValue)) {
      if (sensorValue.sensorId == SH2_GAME_ROTATION_VECTOR) {
        // BNO,grv,<ms>,<r>,<i>,<j>,<k>
        Serial.print("imu");
        // Serial.print(now);
        // Serial.print(",");
        Serial.print(sensorValue.un.gameRotationVector.real, 6);
        Serial.print(",");
        Serial.print(sensorValue.un.gameRotationVector.i, 6);
        Serial.print(",");
        Serial.print(sensorValue.un.gameRotationVector.j, 6);
        Serial.print(",");
        Serial.println(sensorValue.un.gameRotationVector.k, 6);
      }
    }
    nextBNO = now + BNO_PERIOD_MS;
  }

  // -------------------- Trill service -----------------
  if (mode == 1 && trill_ok && now >= nextTrill) {
    trillSensor.read();

    if (trillSensor.getNumTouches() > 0) {
      // TRILL,<ms>,loc1:size1,loc2:size2,...
      Serial.print("TRILL,");
      // Serial.print(now);
      // Serial.print(",");
      for (int i = 0; i < trillSensor.getNumTouches(); i++) {
        if (i) Serial.print(",");
        Serial.print(trillSensor.touchLocation(i), 2); // always decimal
        Serial.print(":");
        Serial.print(trillSensor.touchSize(i), 2);     // always decimal
      }
      Serial.println();
      trillTouchActive = true;
    } else {
      // Print a line even with no touch, using decimal format
      Serial.print("TRILL,");
      Serial.print(now);
      Serial.println(",0.00:0.00");
      trillTouchActive = false;
    }

    nextTrill = now + TRILL_PERIOD_MS;
  }
}
