// #include <Adafruit_BNO08x.h>
// #include <math.h>

// #define BNO08X_CS    10
// #define BNO08X_INT   9
// #define BNO08X_RESET -1

// Adafruit_BNO08x bno08x(BNO08X_RESET);
// sh2_SensorValue_t sensorValue;

// const uint16_t REPORT_US = 10000; // ~100 Hz
// #define COMPARE_WITH_GYRO 0       // set to 1 to also enable SH2_GYROSCOPE_CALIBRATED

// // Current and previous GameRV quaternions (unit)
// static float q_w = 1.f, q_x = 0.f, q_y = 0.f, q_z = 0.f;
// static float qpw = 1.f, qpx = 0.f, qpy = 0.f, qpz = 0.f;

// // Timestamps (sensor clock, microseconds)
// static uint32_t ts_prev = 0;
// static bool have_prev = false;

// // ---- helpers ----
// static inline float vmag(float x, float y, float z) {
//   return sqrtf(x*x + y*y + z*z);
// }

// static inline void quatNormalize(float &w, float &x, float &y, float &z) {
//   float n = sqrtf(w*w + x*x + y*y + z*z);
//   if (n > 0.f) { w/=n; x/=n; y/=n; z/=n; }
// }

// static inline void quatConj(float w, float x, float y, float z,
//                             float &cw, float &cx, float &cy, float &cz) {
//   cw =  w; cx = -x; cy = -y; cz = -z;
// }

// static inline void quatMul(float aw, float ax, float ay, float az,
//                            float bw, float bx, float by, float bz,
//                            float &ow, float &ox, float &oy, float &oz) {
//   ow = aw*bw - ax*bx - ay*by - az*bz;
//   ox = aw*bx + ax*bw + ay*bz - az*by;
//   oy = aw*by - ax*bz + ay*bw + az*bx;
//   oz = aw*bz + ax*by - ay*bx + az*bw;
// }

// // 32-bit microsecond wrap handling
// static inline float dt_from_timestamps(uint32_t nowTs, uint32_t prevTs) {
//   uint32_t d = (nowTs >= prevTs) ? (nowTs - prevTs)
//                                  : (0xFFFFFFFFu - prevTs + 1u + nowTs);
//   return d * 1e-6f; // seconds
// }

// // Compute angular velocity from consecutive quaternions.
// // q_delta = conj(q_prev) ⊗ q_now;  θ = 2*acos(q_delta.w);  axis = d_vec/sin(θ/2);
// // ω = axis * (θ/Δt)
// static bool omega_from_quats(float qpw, float qpx, float qpy, float qpz,
//                              float qnw, float qnx, float qny, float qnz,
//                              float dt, float &wx, float &wy, float &wz) {
//   if (dt <= 0.f) return false;

//   float cw, cx, cy, cz;
//   quatConj(qpw, qpx, qpy, qpz, cw, cx, cy, cz);

//   float dw, dx, dy, dz;
//   quatMul(cw, cx, cy, cz, qnw, qnx, qny, qnz, dw, dx, dy, dz);
//   quatNormalize(dw, dx, dy, dz);

//   // ensure shortest arc
//   if (dw < 0.f) { dw = -dw; dx = -dx; dy = -dy; dz = -dz; }

//   float half_angle = acosf(fmaxf(-1.f, fminf(1.f, dw))); // [0, pi]
//   float sin_half   = sinf(half_angle);
//   float theta      = 2.f * half_angle;

//   if (theta < 1e-7f || fabsf(sin_half) < 1e-7f) {
//     wx = wy = wz = 0.f;
//     return true;
//   }

//   float ax = dx / sin_half;
//   float ay = dy / sin_half;
//   float az = dz / sin_half;

//   float rate = theta / dt; // rad/s
//   wx = ax * rate;
//   wy = ay * rate;
//   wz = az * rate;
//   return true;
// }

// // ---- setup / loop ----
// static void setReports() {
//   if (!bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, REPORT_US)) {
//     Serial.println("Could not enable Game Rotation Vector");
//   }
// #if COMPARE_WITH_GYRO
//   if (!bno08x.enableReport(SH2_GYROSCOPE_CALIBRATED, REPORT_US)) {
//     Serial.println("Could not enable Gyro Calibrated");
//   }
// #endif
// }

// void setup() {
//   Serial.begin(115200);
//   while (!Serial) delay(10);

//   Serial.println("BNO08x: Angular velocity magnitude from GameRV quaternions");

//   if (!bno08x.begin_I2C()) {
//     Serial.println("Failed to find BNO08x chip");
//     while (1) delay(10);
//   }
//   Serial.println("BNO08x Found!");
//   setReports();
//   Serial.println("Press 'r' to reset previous sample.");
// }

// void loop() {
//   // optional reset of previous sample
//   while (Serial.available()) {
//     int c = Serial.read();
//     if (c == 'r' || c == 'R') {
//       have_prev = false;
//       Serial.println("State reset.");
//     }
//   }

//   if (bno08x.wasReset()) {
//     Serial.println("Sensor was reset; re-enabling reports");
//     setReports();
//     have_prev = false;
//   }

//   while (bno08x.getSensorEvent(&sensorValue)) {
//     if (sensorValue.sensorId != SH2_GAME_ROTATION_VECTOR) continue;

//     q_w = sensorValue.un.gameRotationVector.real;
//     q_x = sensorValue.un.gameRotationVector.i;
//     q_y = sensorValue.un.gameRotationVector.j;
//     q_z = sensorValue.un.gameRotationVector.k;
//     quatNormalize(q_w, q_x, q_y, q_z);

//     uint32_t ts = sensorValue.timestamp;
//     if (!have_prev) {
//       qpw = q_w; qpx = q_x; qpy = q_y; qpz = q_z;
//       ts_prev = ts;
//       have_prev = true;
//       continue;
//     }

//     float dt = dt_from_timestamps(ts, ts_prev);
//     ts_prev = ts;

//     float wx, wy, wz;
//     if (omega_from_quats(qpw, qpx, qpy, qpz, q_w, q_x, q_y, q_z, dt, wx, wy, wz)) {
//       float w_mag = vmag(wx, wy, wz);  // magnitude of angular velocity

//       Serial.print("ω (rad/s): ");
//       Serial.print(wx, 6); Serial.print(", ");
//       Serial.print(wy, 6); Serial.print(", ");
//       Serial.print(wz, 6);
//       Serial.print(" | |ω| = ");
//       Serial.println(w_mag, 6);
//     }

//     // advance previous pose
//     qpw = q_w; qpx = q_x; qpy = q_y; qpz = q_z;
//   }

//   delay(2);
// }

#include <Adafruit_BNO08x.h>
#include <math.h>

#define BNO08X_CS    10
#define BNO08X_INT   9
#define BNO08X_RESET -1

Adafruit_BNO08x bno08x(BNO08X_RESET);
sh2_SensorValue_t sensorValue;

const uint16_t REPORT_US = 10000; // ~100 Hz

// --- Strumming detection params (tune these) ---
static const float   THRESH_ON    = 1.8f;  // rad/s average to turn ON
static const float   THRESH_OFF   = 1.2f;  // rad/s average to turn OFF (hysteresis)
static const uint32_t TAU_MS      = 120;   // EMA time constant (~window length)
static const uint32_t MIN_HOLD_MS = 80;    // min time between state flips

// State
static bool     have_prev = false;
static float    q_w = 1.f, q_x = 0.f, q_y = 0.f, q_z = 0.f;
static float    qpw = 1.f, qpx = 0.f, qpy = 0.f, qpz = 0.f;
static uint32_t ts_prev = 0;

static float    w_filt = 0.f;          // filtered |ω|
static uint8_t  ifStrumming = 0;       // 0/1 output
static uint32_t lastToggleMs = 0;

// --- helpers ---
static inline float vmag3(float x, float y, float z) {
  return sqrtf(x*x + y*y + z*z);
}
static inline void quatNormalize(float &w, float &x, float &y, float &z) {
  float n = sqrtf(w*w + x*x + y*y + z*z);
  if (n > 0.f) { w/=n; x/=n; y/=n; z/=n; }
}
static inline void quatConj(float w, float x, float y, float z,
                            float &cw, float &cx, float &cy, float &cz) {
  cw =  w; cx = -x; cy = -y; cz = -z;
}
static inline void quatMul(float aw, float ax, float ay, float az,
                           float bw, float bx, float by, float bz,
                           float &ow, float &ox, float &oy, float &oz) {
  ow = aw*bw - ax*bx - ay*by - az*bz;
  ox = aw*bx + ax*bw + ay*bz - az*by;
  oy = aw*by - ax*bz + ay*bw + az*bx;
  oz = aw*bz + ax*by - ay*bx + az*bw;
}
static inline float dt_from_timestamps(uint32_t nowTs, uint32_t prevTs) {
  uint32_t d = (nowTs >= prevTs) ? (nowTs - prevTs)
                                 : (0xFFFFFFFFu - prevTs + 1u + nowTs);
  return d * 1e-6f; // seconds
}
static bool omega_from_quats(float qpw, float qpx, float qpy, float qpz,
                             float qnw, float qnx, float qny, float qnz,
                             float dt, float &wx, float &wy, float &wz) {
  if (dt <= 0.f) return false;

  float cw, cx, cy, cz; quatConj(qpw, qpx, qpy, qpz, cw, cx, cy, cz);
  float dw, dx, dy, dz; quatMul(cw, cx, cy, cz, qnw, qnx, qny, qnz, dw, dx, dy, dz);
  quatNormalize(dw, dx, dy, dz);
  if (dw < 0.f) { dw = -dw; dx = -dx; dy = -dy; dz = -dz; }

  float half_angle = acosf(fmaxf(-1.f, fminf(1.f, dw)));
  float sin_half   = sinf(half_angle);
  float theta      = 2.f * half_angle;
  if (theta < 1e-7f || fabsf(sin_half) < 1e-7f) { wx = wy = wz = 0.f; return true; }

  float ax = dx / sin_half, ay = dy / sin_half, az = dz / sin_half;
  float rate = theta / dt; // rad/s
  wx = ax * rate; wy = ay * rate; wz = az * rate;
  return true;
}

static void setReports() {
  if (!bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, REPORT_US)) {
    Serial.println("Could not enable Game Rotation Vector");
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  Serial.println("BNO08x: Strumming detection from |ω| (GameRV)");
  if (!bno08x.begin_I2C()) {
    Serial.println("Failed to find BNO08x chip");
    while (1) delay(10);
  }
  Serial.println("BNO08x Found!");
  setReports();

  Serial.print("Params: THRESH_ON="); Serial.print(THRESH_ON);
  Serial.print(", THRESH_OFF=");      Serial.print(THRESH_OFF);
  Serial.print(", TAU_MS=");          Serial.print(TAU_MS);
  Serial.print(", MIN_HOLD_MS=");     Serial.println(MIN_HOLD_MS);
}

void loop() {
  if (bno08x.wasReset()) {
    Serial.println("Sensor was reset; re-enabling reports");
    setReports();
    have_prev = false;
    w_filt = 0.f;
    ifStrumming = 0;
    lastToggleMs = millis();
  }

  while (bno08x.getSensorEvent(&sensorValue)) {
    if (sensorValue.sensorId != SH2_GAME_ROTATION_VECTOR) continue;

    // Read quaternion
    q_w = sensorValue.un.gameRotationVector.real;
    q_x = sensorValue.un.gameRotationVector.i;
    q_y = sensorValue.un.gameRotationVector.j;
    q_z = sensorValue.un.gameRotationVector.k;
    quatNormalize(q_w, q_x, q_y, q_z);

    uint32_t ts = sensorValue.timestamp; // µs (sensor clock)
    if (!have_prev) {
      qpw = q_w; qpx = q_x; qpy = q_y; qpz = q_z;
      ts_prev = ts;
      have_prev = true;
      continue;
    }

    float dt = dt_from_timestamps(ts, ts_prev);
    ts_prev = ts;

    // Get ω from quats
    float wx, wy, wz;
    if (!omega_from_quats(qpw, qpx, qpy, qpz, q_w, q_x, q_y, q_z, dt, wx, wy, wz)) {
      qpw = q_w; qpx = q_x; qpy = q_y; qpz = q_z;
      continue;
    }

    // Advance prev quat
    qpw = q_w; qpx = q_x; qpy = q_y; qpz = q_z;

    float w_mag = vmag3(wx, wy, wz);

    // ---- EMA filter over ~TAU_MS ----
    // alpha = 1 - exp(-dt/τ), τ in seconds
    float tau_s = TAU_MS / 1000.0f;
    float alpha = 1.0f - expf(-dt / fmaxf(1e-6f, tau_s));
    w_filt += alpha * (w_mag - w_filt);

    // ---- Hysteresis + debounce ----
    uint32_t nowMs = millis();
    if (ifStrumming == 0) {
      if (w_filt >= THRESH_ON && (nowMs - lastToggleMs) >= MIN_HOLD_MS) {
        ifStrumming = 1;
        lastToggleMs = nowMs;
      }
    } else {
      if (w_filt <= THRESH_OFF && (nowMs - lastToggleMs) >= MIN_HOLD_MS) {
        ifStrumming = 0;
        lastToggleMs = nowMs;
      }
    }

    // Output: raw |ω|, filtered, and 0/1 flag
    Serial.print("|w|=");    Serial.print(w_mag, 4);
    Serial.print("  filt="); Serial.print(w_filt, 4);
    Serial.print("  strum=");Serial.println(ifStrumming);
  }

  delay(2);
}
