// #include <Adafruit_BNO08x.h>
// #include <math.h>

// #define BNO08X_CS    10
// #define BNO08X_INT   9
// #define BNO08X_RESET -1

// Adafruit_BNO08x bno08x(BNO08X_RESET);
// sh2_SensorValue_t sensorValue;

// const uint16_t REPORT_US = 10000; // ~100 Hz

// // ---- Strumming detection (tune) ----
// static const float    THRESH_ON     = 1.8f;   // rad/s to turn ON
// static const float    THRESH_OFF    = 1.2f;   // rad/s to turn OFF
// static const uint32_t TAU_MS        = 120;    // EMA time constant
// static const uint32_t MIN_HOLD_MS   = 80;     // min time between state flips

// // ---- Pulse / debouncing (burst control) ----
// static const uint32_t PULSE_MS      = 40;     // pulse width for "strum event"
// static const uint32_t REFRACTORY_MS = 200;    // lockout after a pulse

// // Optional: drive a pin with the pulse (uncomment to use)
// // const int PULSE_PIN = 5;

// // ---- State ----
// static bool     have_prev = false;
// static float    q_w = 1.f, q_x = 0.f, q_y = 0.f, q_z = 0.f;
// static float    qpw = 1.f, qpx = 0.f, qpy = 0.f, qpz = 0.f;
// static uint32_t ts_prev = 0;

// static float    w_filt = 0.f;          // filtered |ω|
// static uint8_t  ifStrumming = 0;       // latched state (0/1)
// static uint8_t  prevStrumming = 0;
// static uint32_t lastToggleMs = 0;

// // Pulse one-shot + refractory
// static uint8_t  strumPulse = 0;        // 1 while pulse is active
// static uint32_t pulseEndMs = 0;
// static uint32_t lastPulseMs = 0;

// // ---- helpers ----
// static inline float vmag3(float x, float y, float z){ return sqrtf(x*x + y*y + z*z); }
// static inline void  quatNormalize(float &w, float &x, float &y, float &z){
//   float n = sqrtf(w*w + x*x + y*y + z*z); if(n>0.f){ w/=n; x/=n; y/=n; z/=n; }
// }
// static inline void  quatConj(float w,float x,float y,float z,float &cw,float &cx,float &cy,float &cz){
//   cw=w; cx=-x; cy=-y; cz=-z;
// }
// static inline void  quatMul(float aw,float ax,float ay,float az,float bw,float bx,float by,float bz,
//                             float &ow,float &ox,float &oy,float &oz){
//   ow = aw*bw - ax*bx - ay*by - az*bz;
//   ox = aw*bx + ax*bw + ay*bz - az*by;
//   oy = aw*by - ax*bz + ay*bw + az*bx;
//   oz = aw*bz + ax*by - ay*bx + az*bw;
// }
// static inline float dt_from_timestamps(uint32_t nowTs, uint32_t prevTs){
//   uint32_t d = (nowTs >= prevTs) ? (nowTs - prevTs) : (0xFFFFFFFFu - prevTs + 1u + nowTs);
//   return d * 1e-6f;
// }
// static bool omega_from_quats(float qpw,float qpx,float qpy,float qpz,
//                              float qnw,float qnx,float qny,float qnz,
//                              float dt,float &wx,float &wy,float &wz){
//   if(dt<=0.f) return false;
//   float cw,cx,cy,cz; quatConj(qpw,qpx,qpy,qpz,cw,cx,cy,cz);
//   float dw,dx,dy,dz; quatMul(cw,cx,cy,cz,qnw,qnx,qny,qnz,dw,dx,dy,dz);
//   quatNormalize(dw,dx,dy,dz);
//   if(dw<0.f){ dw=-dw; dx=-dx; dy=-dy; dz=-dz; }
//   float half_angle = acosf(fmaxf(-1.f, fminf(1.f, dw)));
//   float sh = sinf(half_angle);
//   float theta = 2.f*half_angle;
//   if(theta<1e-7f || fabsf(sh)<1e-7f){ wx=wy=wz=0.f; return true; }
//   float ax = dx/sh, ay = dy/sh, az = dz/sh;
//   float rate = theta/dt;
//   wx = ax*rate; wy = ay*rate; wz = az*rate;
//   return true;
// }

// static void setReports(){
//   if(!bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, REPORT_US)){
//     Serial.println("Could not enable Game Rotation Vector");
//   }
// }

// void setup(){
//   Serial.begin(115200);
//   while(!Serial) delay(10);

//   Serial.println("BNO08x: |ω| strum detection with pulse + refractory");
//   if(!bno08x.begin_I2C()){
//     Serial.println("Failed to find BNO08x chip");
//     while(1) delay(10);
//   }
//   Serial.println("BNO08x Found!");
//   setReports();

//   // pinMode(PULSE_PIN, OUTPUT); digitalWrite(PULSE_PIN, LOW);

//   Serial.print("TH_ON="); Serial.print(THRESH_ON);
//   Serial.print(" TH_OFF="); Serial.print(THRESH_OFF);
//   Serial.print(" TAU(ms)="); Serial.print(TAU_MS);
//   Serial.print(" HOLD(ms)="); Serial.print(MIN_HOLD_MS);
//   Serial.print(" PULSE(ms)="); Serial.print(PULSE_MS);
//   Serial.print(" LOCK(ms)="); Serial.println(REFRACTORY_MS);
// }

// void loop(){
//   // optional manual reset
//   while(Serial.available()){
//     int c = Serial.read();
//     if(c=='r'||c=='R'){
//       have_prev=false;
//       w_filt=0.f;
//       ifStrumming=prevStrumming=strumPulse=0;
//       // digitalWrite(PULSE_PIN, LOW);
//       Serial.println("State reset.");
//     }
//   }

//   if(bno08x.wasReset()){
//     Serial.println("Sensor reset; re-enabling");
//     setReports();
//     have_prev=false;
//     w_filt=0.f;
//     ifStrumming=prevStrumming=strumPulse=0;
//     // digitalWrite(PULSE_PIN, LOW);
//   }

//   while(bno08x.getSensorEvent(&sensorValue)){
//     if(sensorValue.sensorId!=SH2_GAME_ROTATION_VECTOR) continue;

//     // quat
//     q_w = sensorValue.un.gameRotationVector.real;
//     q_x = sensorValue.un.gameRotationVector.i;
//     q_y = sensorValue.un.gameRotationVector.j;
//     q_z = sensorValue.un.gameRotationVector.k;
//     quatNormalize(q_w,q_x,q_y,q_z);

//     uint32_t ts = sensorValue.timestamp;
//     if(!have_prev){
//       qpw=q_w; qpx=q_x; qpy=q_y; qpz=q_z;
//       ts_prev=ts; have_prev=true; continue;
//     }

//     float dt = dt_from_timestamps(ts, ts_prev);
//     ts_prev = ts;

//     // ω
//     float wx,wy,wz;
//     if(!omega_from_quats(qpw,qpx,qpy,qpz,q_w,q_x,q_y,q_z,dt,wx,wy,wz)){
//       qpw=q_w; qpx=q_x; qpy=q_y; qpz=q_z;
//       continue;
//     }
//     qpw=q_w; qpx=q_x; qpy=q_y; qpz=q_z;

//     float w_mag = vmag3(wx,wy,wz);

//     // EMA
//     float tau_s = TAU_MS/1000.0f;
//     float alpha = 1.0f - expf(-dt / fmaxf(1e-6f, tau_s));
//     w_filt += alpha * (w_mag - w_filt);

//     // Hysteresis state
//     prevStrumming = ifStrumming;
//     uint32_t nowMs = millis();

//     if(ifStrumming==0){
//       if(w_filt >= THRESH_ON && (nowMs - lastToggleMs) >= MIN_HOLD_MS){
//         ifStrumming = 1;
//         lastToggleMs = nowMs;
//       }
//     }else{
//       if(w_filt <= THRESH_OFF && (nowMs - lastToggleMs) >= MIN_HOLD_MS){
//         ifStrumming = 0;
//         lastToggleMs = nowMs;
//       }
//     }

//     // Rising-edge: generate one-shot pulse with refractory lockout
//     if(prevStrumming==0 && ifStrumming==1){
//       if((nowMs - lastPulseMs) >= REFRACTORY_MS){
//         strumPulse = 1;
//         pulseEndMs = nowMs + PULSE_MS;
//         lastPulseMs = nowMs;
//         // digitalWrite(PULSE_PIN, HIGH);
//       }
//     }

//     // End pulse when time elapses
//     if(strumPulse && nowMs >= pulseEndMs){
//       strumPulse = 0;
//       // digitalWrite(PULSE_PIN, LOW);
//     }

//     // Serial debug
//     Serial.print("|w|="); Serial.print(w_mag,3);
//     Serial.print(" filt="); Serial.print(w_filt,3);
//     Serial.print(" strum="); Serial.print((int)ifStrumming);
//     Serial.print(" pulse="); Serial.println((int)strumPulse);
//   }

//   delay(2);
// }

// ---------- IMU + BLE Strumming Pulse over Notifications ----------
// Board: XIAO ESP32S3 (ESP32-S3)
// IMU: Adafruit BNO08x (I2C)
// BLE: Classic ESP32 BLE library (BLEDevice)

#include <Adafruit_BNO08x.h>
#include <math.h>

// ---- BLE ----
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

BLECharacteristic *pCharacteristic = nullptr;

// ---- IMU ----
#define BNO08X_CS    10
#define BNO08X_INT   9
#define BNO08X_RESET -1

Adafruit_BNO08x bno08x(BNO08X_RESET);
sh2_SensorValue_t sensorValue;

const uint16_t REPORT_US = 10000; // ~100 Hz

// ---- Strumming detection (tune these) ----
static const float    THRESH_ON     = 2.0f;   // rad/s average to turn ON
static const float    THRESH_OFF    = 1.2f;   // rad/s average to turn OFF
static const uint32_t TAU_MS        = 120;    // EMA time constant
static const uint32_t MIN_HOLD_MS   = 80;     // min time between state flips
static const uint32_t PULSE_MS      = 40;     // pulse width (ms)
static const uint32_t REFRACTORY_MS = 200;    // lockout after a pulse

// ---- State ----
static bool     have_prev = false;
static float    q_w = 1.f, q_x = 0.f, q_y = 0.f, q_z = 0.f;
static float    qpw = 1.f, qpx = 0.f, qpy = 0.f, qpz = 0.f;
static uint32_t ts_prev = 0;

static float    w_filt = 0.f;          // filtered |ω|
static uint8_t  ifStrumming = 0;       // latched state (0/1)
static uint8_t  prevStrumming = 0;
static uint32_t lastToggleMs = 0;

// Pulse one-shot + refractory
static uint8_t  strumPulse = 0;        // 1 while pulse is active
static uint32_t pulseEndMs = 0;
static uint32_t lastPulseMs = 0;
static uint8_t  lastSentPulse = 255;   // force first send

// ========== Helpers ==========
static inline float vmag3(float x, float y, float z){ return sqrtf(x*x + y*y + z*z); }

static inline void quatNormalize(float &w, float &x, float &y, float &z){
  float n = sqrtf(w*w + x*x + y*y + z*z); if(n>0.f){ w/=n; x/=n; y/=n; z/=n; }
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
  uint32_t d = (nowTs >= prevTs) ? (nowTs - prevTs) : (0xFFFFFFFFu - prevTs + 1u + nowTs);
  return d * 1e-6f;
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
  float sh = sinf(half_angle);
  float theta = 2.f*half_angle;
  if(theta<1e-7f || fabsf(sh)<1e-7f){ wx=wy=wz=0.f; return true; }
  float ax = dx/sh, ay = dy/sh, az = dz/sh;
  float rate = theta/dt; // rad/s
  wx = ax*rate; wy = ay*rate; wz = az*rate;
  return true;
}

// ========== BLE send ==========
void sendBLE(uint8_t new_strumPulse){
  if(!pCharacteristic) return;
  // Send as a tiny string: "P:0" or "P:1" (easy to debug on phone)
  char buf[8];
  snprintf(buf, sizeof(buf), "P:%d", (int)new_strumPulse);
  pCharacteristic->setValue((uint8_t*)buf, strlen(buf));
  pCharacteristic->notify();

  Serial.print("📤 BLE notify -> "); Serial.println(buf);
}

// ========== Setup ==========
void setup() {
  Serial.begin(115200);
  while(!Serial) delay(10);

  Serial.println("BNO08x + BLE: |ω| strum pulse notifications");

  // --- IMU init ---
  if(!bno08x.begin_I2C()){
    Serial.println("Failed to find BNO08x chip");
    while(1) delay(10);
  }
  Serial.println("BNO08x Found!");
  if(!bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, REPORT_US)){
    Serial.println("Could not enable Game Rotation Vector");
  }

  // --- BLE init ---
  BLEDevice::init("XIAO_ESP32S3");
  BLEServer *pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService(SERVICE_UUID);
  pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ |
    BLECharacteristic::PROPERTY_NOTIFY |   // important for notify()
    BLECharacteristic::PROPERTY_WRITE
  );
  // 0x2902 descriptor so central (esp. iOS) can enable notifications
  pCharacteristic->addDescriptor(new BLE2902());
  pCharacteristic->setValue("P:0");
  pService->start();

  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();

  Serial.println("BLE ready. Notifying P:0 on strum pulses.");
}

// ========== Main loop ==========
void loop() {
  // Optional manual reset with 'r'
  while(Serial.available()){
    int c = Serial.read();
    if(c=='r'||c=='R'){
      have_prev=false;
      w_filt=0.f;
      ifStrumming=prevStrumming=strumPulse=0;
      lastSentPulse = 255;
      Serial.println("State reset.");
    }
  }

  if(bno08x.wasReset()){
    Serial.println("Sensor reset; re-enabling GRV");
    bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, REPORT_US);
    have_prev=false;
    w_filt=0.f;
    ifStrumming=prevStrumming=strumPulse=0;
    lastSentPulse = 255;
  }

  // Drain IMU events
  while(bno08x.getSensorEvent(&sensorValue)){
    if(sensorValue.sensorId != SH2_GAME_ROTATION_VECTOR) continue;

    // Read quaternion
    q_w = sensorValue.un.gameRotationVector.real;
    q_x = sensorValue.un.gameRotationVector.i;
    q_y = sensorValue.un.gameRotationVector.j;
    q_z = sensorValue.un.gameRotationVector.k;
    quatNormalize(q_w,q_x,q_y,q_z);

    uint32_t ts = sensorValue.timestamp; // µs
    if(!have_prev){
      qpw=q_w; qpx=q_x; qpy=q_y; qpz=q_z;
      ts_prev=ts; have_prev=true; continue;
    }

    float dt = dt_from_timestamps(ts, ts_prev);
    ts_prev = ts;

    // ω from quaternion delta
    float wx,wy,wz;
    if(!omega_from_quats(qpw,qpx,qpy,qpz,q_w,q_x,q_y,q_z,dt,wx,wy,wz)){
      qpw=q_w; qpx=q_x; qpy=q_y; qpz=q_z;
      continue;
    }
    qpw=q_w; qpx=q_x; qpy=q_y; qpz=q_z;

    float w_mag = vmag3(wx,wy,wz);

    // EMA smoothing over TAU_MS
    float tau_s = TAU_MS/1000.0f;
    float alpha = 1.0f - expf(-dt / fmaxf(1e-6f, tau_s));
    w_filt += alpha * (w_mag - w_filt);

    // Hysteresis state + debounce
    prevStrumming = ifStrumming;
    uint32_t nowMs = millis();

    if(ifStrumming==0){
      if(w_filt >= THRESH_ON && (nowMs - lastToggleMs) >= MIN_HOLD_MS){
        ifStrumming = 1;
        lastToggleMs = nowMs;
      }
    } else {
      if(w_filt <= THRESH_OFF && (nowMs - lastToggleMs) >= MIN_HOLD_MS){
        ifStrumming = 0;
        lastToggleMs = nowMs;
      }
    }

    // One-shot pulse on rising edge with refractory window
    if (prevStrumming == 0 && ifStrumming == 1) {
      if ((nowMs - lastPulseMs) >= REFRACTORY_MS) {
        strumPulse  = 1;
        pulseEndMs  = nowMs + PULSE_MS;
        lastPulseMs = nowMs;

        // ✅ Send BLE only when pulse goes HIGH
        sendBLE(1);
        lastSentPulse = 1;
      }
    }

    // End pulse when time elapses (no BLE send on falling edge)
    if (strumPulse && nowMs >= pulseEndMs) {
      strumPulse = 0;
      lastSentPulse = 0;   // reset so next rising edge can notify again
    }



    // Debug line
    Serial.print("|w|="); Serial.print(w_mag,3);
    Serial.print(" filt="); Serial.print(w_filt,3);
    Serial.print(" strum="); Serial.print((int)ifStrumming);
    Serial.print(" pulse="); Serial.println((int)strumPulse);
  }

  delay(2);
}
