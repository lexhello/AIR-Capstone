// ===================== BLE (same style, with NOTIFY) =====================
#include <BLEDevice.h> 
#include <BLEUtils.h>
#include <BLEServer.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

// FSR: 3.3V -> FSR -> Node -> 10kΩ -> GND, Node -> A1 (D1)
const int FSR_PIN  = A1;

// ---- FSR thresholds (tune after reading serial output) ----
const int FSR_PRESS_ON  = 500;  // above = pressed
const int FSR_PRESS_OFF = 400;   // below = released

BLECharacteristic *pCharacteristic;

void setup() {
  Serial.begin(115200);
  Serial.println("Starting BLE work!");

  BLEDevice::init("XIAO_ESP32S3");
  BLEServer *pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService(SERVICE_UUID);

  pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ |
    BLECharacteristic::PROPERTY_WRITE |
    BLECharacteristic::PROPERTY_NOTIFY
  );

  pCharacteristic->setValue("Hello World");
  pService->start();

  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();
  Serial.println("Characteristic defined! Connect and enable notifications.");
}

void sendBLE(int new_strum) {
  if (pCharacteristic != nullptr) {
    char buf[16];
    snprintf(buf, sizeof(buf), "test, %d", new_strum);
    pCharacteristic->setValue(buf);
    pCharacteristic->notify();
    Serial.print("📤 Sent integer as string: ");
    Serial.println(buf);
  }
}

// ===================== IMU + STRUM DETECTION =====================
#include <Adafruit_BNO08x.h>
#include <math.h>

#define BNO08X_CS    10
#define BNO08X_INT   9
#define BNO08X_RESET -1

Adafruit_BNO08x bno08x(BNO08X_RESET);
sh2_SensorValue_t sensorValue;

const uint16_t REPORT_US = 10000; // ~100 Hz

// ---- Strumming + acceleration thresholds ----
// angular velocity is too sensitive

static const float    THRESH_ON     = 1.2f;
static const float    THRESH_OFF    = 0.8f;
static const uint32_t TAU_MS        = 120;
static const uint32_t MIN_HOLD_MS   = 80;
static const uint32_t PULSE_MS      = 40;
static const uint32_t REFRACTORY_MS = 200;

static const float    A_SPIKE_ABS   = 20.0f;
static const float    A_SPIKE_REL   = 5.0f;
static const uint32_t A_TAU_MS      = 80;

// ---- State ----
static bool     have_prev = false;
static float    q_w = 1.f, q_x = 0.f, q_y = 0.f, q_z = 0.f;
static float    qpw = 1.f, qpx = 0.f, qpy = 0.f, qpz = 0.f;
static uint32_t ts_prev = 0;

static float    w_filt = 0.f;
static float    a_filt = 0.f;
static uint8_t  ifStrumming = 0;
static uint8_t  prevStrumming = 0;
static uint32_t lastToggleMs = 0;

static uint8_t  strumPulse = 0;
static uint32_t pulseEndMs = 0;
static uint32_t lastPulseMs = 0;

static inline float vmag3(float x,float y,float z){ return sqrtf(x*x + y*y + z*z); }

static inline void quatNormalize(float &w,float &x,float &y,float &z){
  float n = sqrtf(w*w + x*x + y*y + z*z);
  if(n>0.f){ w/=n; x/=n; y/=n; z/=n; }
}
static inline void quatConj(float w,float x,float y,float z,float &cw,float &cx,float &cy,float &cz){
  cw=w; cx=-x; cy=-y; cz=-z;
}
static inline void quatMul(float aw,float ax,float ay,float az,float bw,float bx,float by,float bz,
                           float &ow,float &ox,float &oy,float &oz){
  ow = aw*bw - ax*bx - ay*by - az*bz;
  ox = aw*bx + ax*bw + ay*bz - az*by;
  oy = aw*by - ax*bz + ay*bw + az*bx;
  oz = aw*bz + ax*by - ay*bx + az*bw;
}
static inline float dt_from_timestamps(uint32_t nowTs, uint32_t prevTs){
  uint32_t d = (nowTs >= prevTs) ? (nowTs - prevTs)
                                 : (0xFFFFFFFFu - prevTs + 1u + nowTs);
  return d * 1e-6f; // seconds
}
static bool omega_from_quats(float qpw,float qpx,float qpy,float qpz,
                             float qnw,float qnx,float qny,float qnz,
                             float dt,float &wx,float &wy,float &wz){
  if(dt<=0.f) return false;
  float cw,cx,cy,cz; quatConj(qpw,qpx,qpy,qpz,cw,cx,cy,cz);
  float dw,dx,dy,dz; quatMul(cw,cx,cy,cz,qnw,qnx,qny,qnz,dw,dx,dy,dz);
  quatNormalize(dw,dx,dy,dz);
  if(dw<0.f){ dw=-dw; dx=-dx; dy=-dy; dz=-dz; }

  float half_angle = acosf(fmaxf(-1.f, fminf(1.f, dw)));
  float sh         = sinf(half_angle);
  float theta      = 2.f * half_angle;
  if(theta < 1e-7f || fabsf(sh) < 1e-7f){ wx=wy=wz=0.f; return true; }

  float ax = dx/sh, ay = dy/sh, az = dz/sh;
  float rate = theta / dt;
  wx = ax * rate; wy = ay * rate; wz = az * rate;
  return true;
}

static inline void try_pulse_and_send(uint32_t nowMs){
  if ((nowMs - lastPulseMs) >= REFRACTORY_MS) {
    strumPulse  = 1;
    pulseEndMs  = nowMs + PULSE_MS;
    lastPulseMs = nowMs;
    sendBLE(1);
  }
}

// ===================== MAIN LOOP =====================
void loop() {
  // ---- FSR read + hysteresis ----
  static bool fsrPressed = false;

  // FSR: 3.3V -> FSR -> Node -> 10kΩ -> GND, Node -> A1 (D1)

  static bool imu_inited = false;
  if (!imu_inited) {
    if (!bno08x.begin_I2C()) {
      Serial.println("Failed to find BNO08x chip");
      delay(1000);
      return;
    }
    bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, REPORT_US);
    bno08x.enableReport(SH2_LINEAR_ACCELERATION, REPORT_US);
    Serial.println("IMU ready");
    imu_inited = true;
  }

  if (bno08x.wasReset()) {
    Serial.println("Sensor reset; re-enabling reports");
    bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, REPORT_US);
    bno08x.enableReport(SH2_LINEAR_ACCELERATION, REPORT_US);
    have_prev = false;
    w_filt = 0.f;
    a_filt = 0.f;
  }

  while (bno08x.getSensorEvent(&sensorValue)) {
    int fsrValue = analogRead(FSR_PIN); // A1/D1 analog input (0–4095)
    if (!fsrPressed && fsrValue >= FSR_PRESS_ON) fsrPressed = true;
    else if (fsrPressed && fsrValue <= FSR_PRESS_OFF) fsrPressed = false;
    uint32_t nowMs = millis();

    if (sensorValue.sensorId == SH2_GAME_ROTATION_VECTOR) {
      // Angular velocity estimation
      q_w = sensorValue.un.gameRotationVector.real;
      q_x = sensorValue.un.gameRotationVector.i;
      q_y = sensorValue.un.gameRotationVector.j;
      q_z = sensorValue.un.gameRotationVector.k;
      quatNormalize(q_w, q_x, q_y, q_z);

      uint32_t ts = sensorValue.timestamp;
      if (!have_prev) {
        qpw = q_w; qpx = q_x; qpy = q_y; qpz = q_z;
        ts_prev = ts;
        have_prev = true;
        continue;
      }

      float dt = dt_from_timestamps(ts, ts_prev);
      ts_prev = ts;

      float wx, wy, wz;
      if (!omega_from_quats(qpw, qpx, qpy, qpz, q_w, q_x, q_y, q_z, dt, wx, wy, wz)) {
        qpw = q_w; qpx = q_x; qpy = q_y; qpz = q_z;
        continue;
      }
      qpw = q_w; qpx = q_x; qpy = q_y; qpz = q_z;

      float w_mag = vmag3(wx, wy, wz);
      float tau_s = TAU_MS / 1000.0f;
      float alpha = 1.0f - expf(-dt / fmaxf(1e-6f, tau_s));
      w_filt += alpha * (w_mag - w_filt);

      prevStrumming = ifStrumming;
      if (ifStrumming == 0) {
        if (w_filt >= THRESH_ON && (nowMs - lastToggleMs) >= MIN_HOLD_MS &&
          fsrPressed) {
          ifStrumming = 1;
          lastToggleMs = nowMs;
        }
      } else {
        if (w_filt <= THRESH_OFF && (nowMs - lastToggleMs) >= MIN_HOLD_MS) {
          ifStrumming = 0;
          lastToggleMs = nowMs;
        }
      }

      if (prevStrumming == 0 && ifStrumming == 1 && fsrPressed) try_pulse_and_send(nowMs);
      if (strumPulse && nowMs >= pulseEndMs) strumPulse = 0;

      // ✅ Print angular velocity
      // Serial.print("ωx="); Serial.print(wx, 3);
      // Serial.print(" ωy="); Serial.print(wy, 3);
      // Serial.print(" ωz="); Serial.print(wz, 3);
      // Serial.print(" |ω|="); Serial.print(w_mag, 3);
      // Serial.print(" filt_w="); Serial.print(w_filt, 3);
      // Serial.print(" strum="); Serial.println((int)ifStrumming);
      Serial.print(fsrPressed);
    }

    else if (sensorValue.sensorId == SH2_LINEAR_ACCELERATION) {
      // Linear acceleration
      float ax = sensorValue.un.linearAcceleration.x;
      float ay = sensorValue.un.linearAcceleration.y;
      float az = sensorValue.un.linearAcceleration.z;
      float a_mag = vmag3(ax, ay, az);

      float alpha_a = 1.0f - expf(-(REPORT_US * 1e-6f) / fmaxf(1e-6f, A_TAU_MS / 1000.0f));
      a_filt += alpha_a * (a_mag - a_filt);

      // bool spike = (a_mag >= A_SPIKE_ABS) || ((a_mag - a_filt) >= A_SPIKE_REL);
      bool spike = ((a_mag - a_filt) >= A_SPIKE_REL);
      if (spike && fsrPressed) try_pulse_and_send(nowMs);
      if (strumPulse && nowMs >= pulseEndMs) strumPulse = 0;

      // ✅ Print linear acceleration
      Serial.print("Ax="); Serial.print(ax, 3);
      Serial.print(" Ay="); Serial.print(ay, 3);
      Serial.print(" Az="); Serial.print(az, 3);
      Serial.print(" |a|="); Serial.print(a_mag, 3);
      Serial.print(" filt_a="); Serial.print(a_filt, 3);
      Serial.print(" spike="); Serial.println((int)spike);
    }
  }

  delay(2);
}
