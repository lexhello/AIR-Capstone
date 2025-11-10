// ===================== BLE (same style, with NOTIFY) =====================
#include <BLEDevice.h> 
#include <BLEUtils.h>
#include <BLEServer.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

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
  pAdvertising->setName("XIAO_ESP32S3"); 
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
static const float    THRESH_ON     = 1.5f;
static const float    THRESH_OFF    = 1.0f;
static const uint32_t TAU_MS        = 120;
static const uint32_t MIN_HOLD_MS   = 80;
static const uint32_t PULSE_MS      = 40;
static const uint32_t REFRACTORY_MS = 200;

static const float    A_SPIKE_ABS   = 20.0f;
static const float    A_SPIKE_REL   = 20.0f;
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
  delay(700);
  sendBLE(1);
  Serial.println("sent");
}
