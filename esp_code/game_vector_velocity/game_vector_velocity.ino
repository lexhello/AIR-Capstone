// Combined Strummer with fused velocity - integrated.ino

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <Adafruit_BNO08x.h>
#include <math.h>

// new uuid
#define SERVICE_UUID        "c8b8f3c0-7c72-4cf2-8d1f-59fb7a5e4a1b"
#define CHARACTERISTIC_UUID "f1a7d8b3-2c44-4c51-9f44-bad597c893c7"

// original uuid
// #define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
// #define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

const int FSR_PIN  = A1; // 3.3V -> FSR -> Node -> 10kΩ -> GND, Node -> A1

const int FSR_PRESS_ON  = 500;
const int FSR_PRESS_OFF = 350;

BLECharacteristic *pCharacteristic;

// ===================== IMU =====================
#define BNO08X_CS    10
#define BNO08X_INT   9
#define BNO08X_RESET -1

Adafruit_BNO08x bno08x(BNO08X_RESET);
sh2_SensorValue_t sensorValue;
const uint16_t REPORT_US = 10000; // ~100 Hz

// ---- Strumming thresholds ----
static const float    THRESH_ON     = 1.2f;
static const float    THRESH_OFF    = 0.8f;
static const uint32_t TAU_MS        = 120;
static const uint32_t MIN_HOLD_MS   = 80;
static const uint32_t PULSE_MS      = 40;
static const uint32_t REFRACTORY_MS = 200;
static const float    A_SPIKE_REL   = 5.0f;
static const uint32_t A_TAU_MS      = 80;

// ---- Linear velocity estimation ----
static float vel_x=0.f, vel_y=0.f, vel_z=0.f;
static const float G_MS2 = 9.80665f;
static const float VELOCITY_TAU_S = 0.8f; // leakage
static const float ZUPT_ACCEL_THRESH = 0.15f;
static const uint32_t ZUPT_HOLD_MS = 120;
static uint32_t zupt_since_ms = 0;

// ---- State ----
static bool have_prev = false;
static float q_w=1.f,q_x=0.f,q_y=0.f,q_z=0.f;
static float qpw=1.f,qpx=0.f,qpy=0.f,qpz=0.f;
static uint32_t ts_prev = 0;

static float w_filt=0.f, a_filt=0.f;
static float w_mag=0.f, a_mag=0.f;
static float wx=0.f, wy=0.f, wz=0.f;
static float ax=0.f, ay=0.f, az=0.f;

static bool haveRot=false, haveAccel=false;

static uint8_t  ifStrumming=0;
static uint8_t  prevStrumming=0;
static uint32_t lastToggleMs=0;

static uint8_t  strumPulse=0;
static uint32_t pulseEndMs=0;
static uint32_t lastPulseMs=0;

static bool imu_inited=false;
static uint32_t ts_prev_accel=0;

// ===================== HELPERS =====================
static inline float vmag3(float x,float y,float z){ return sqrtf(x*x+y*y+z*z); }

static inline void quatNormalize(float &w,float &x,float &y,float &z){
  float n=sqrtf(w*w+x*x+y*y+z*z); if(n>0.f){ w/=n; x/=n; y/=n; z/=n; }
}
static inline void quatConj(float w,float x,float y,float z,float &cw,float &cx,float &cy,float &cz){
  cw=w; cx=-x; cy=-y; cz=-z;
}
static inline void quatMul(float aw,float ax,float ay,float az,float bw,float bx,float by,float bz,
                           float &ow,float &ox,float &oy,float &oz){
  ow=aw*bw-ax*bx-ay*by-az*bz;
  ox=aw*bx+ax*bw+ay*bz-az*by;
  oy=aw*by-ax*bz+ay*bw+az*bx;
  oz=aw*bz+ax*by-ay*bx+az*bw;
}
static inline float dt_from_timestamps(uint32_t nowTs,uint32_t prevTs){
  uint32_t d=(nowTs>=prevTs)?(nowTs-prevTs):(0xFFFFFFFFu-prevTs+1u+nowTs);
  return d*1e-6f;
}
static bool omega_from_quats(float qpw,float qpx,float qpy,float qpz,
                             float qnw,float qnx,float qny,float qnz,
                             float dt,float &wx,float &wy,float &wz){
  if(dt<=0.f) return false;
  float cw,cx,cy,cz; quatConj(qpw,qpx,qpy,qpz,cw,cx,cy,cz);
  float dw,dx,dy,dz; quatMul(cw,cx,cy,cz,qnw,qnx,qny,qnz,dw,dx,dy,dz);
  quatNormalize(dw,dx,dy,dz);
  if(dw<0.f){ dw=-dw; dx=-dx; dy=-dy; dz=-dz; }
  float half_angle=acosf(fmaxf(-1.f,fminf(1.f,dw)));
  float sh=sinf(half_angle);
  float theta=2.f*half_angle;
  if(theta<1e-7f||fabsf(sh)<1e-7f){ wx=wy=wz=0.f; return true; }
  float axn=dx/sh, ayn=dy/sh, azn=dz/sh;
  float rate=theta/dt;
  wx=axn*rate; wy=ayn*rate; wz=azn*rate;
  return true;
}

// Rotate vector by quaternion
static void rotateVectorByQuat(float qw,float qx,float qy,float qz,
                               float vx,float vy,float vz,
                               float &out_x,float &out_y,float &out_z){
  float iw=-qx*vx-qy*vy-qz*vz;
  float ix=qw*vx+qy*vz-qz*vy;
  float iy=qw*vy+qz*vx-qx*vz;
  float iz=qw*vz+qx*vy-qy*vx;
  out_x=ix*qw-iw*-qx-iy*-qz+iz*-qy;
  out_y=iy*qw-iw*-qy-iz*-qx+ix*-qz;
  out_z=iz*qw-iw*-qz-ix*-qy+iy*-qx;
}

// ===================== BLE =====================
void sendBLE(int strum, float lin_speed, float rot_speed){
  if(pCharacteristic){
    char buf[48];
    float average = (lin_speed + rot_speed)/2.0;
    snprintf(buf,sizeof(buf),"%d,%.3f",strum,average);
    pCharacteristic->setValue(buf);
    pCharacteristic->notify();
    Serial.println(buf);
  }
}

// ===================== VELOCITY INTEGRATION =====================
static void integrateAccelToVelocity(float dt, bool fsrPressed){
  float wx_,wy_,wz_;
  rotateVectorByQuat(q_w,q_x,q_y,q_z,ax,ay,az,wx_,wy_,wz_);
  float axw=wx_, ayw=wy_, azw=wz_-G_MS2;
  vel_x+=axw*dt; vel_y+=ayw*dt; vel_z+=azw*dt;
  float leak=expf(-dt/fmaxf(1e-9f,VELOCITY_TAU_S));
  vel_x*=leak; vel_y*=leak; vel_z*=leak;
  float a_mag_world=sqrtf(axw*axw+ayw*ayw+azw*azw);
  if(a_mag_world<ZUPT_ACCEL_THRESH){
    if(zupt_since_ms==0) zupt_since_ms=millis();
    else if((millis()-zupt_since_ms)>=ZUPT_HOLD_MS){ vel_x=vel_y=vel_z=0.f; }
  } else { zupt_since_ms=0; }
}

static float getLinearSpeed(){ return sqrtf(vel_x*vel_x+vel_y*vel_y+vel_z*vel_z); }

// ===================== STRUM CHECK =====================
static inline void try_pulse_and_send(uint32_t nowMs){
  if((nowMs-lastPulseMs)>=REFRACTORY_MS){
    strumPulse=1;
    pulseEndMs=nowMs+PULSE_MS;
    lastPulseMs=nowMs;
    sendBLE(1,getLinearSpeed(),w_filt);
  }
}

static inline void checkStrum(uint32_t nowMs,bool fsrPressed){
  bool rotationTrigger=false;
  bool accelTrigger=false;
  if(haveRot){
    prevStrumming=ifStrumming;
    if(ifStrumming==0){
      if(w_filt>=THRESH_ON&&(nowMs-lastToggleMs)>=MIN_HOLD_MS&&fsrPressed){
        ifStrumming=1;
        lastToggleMs=nowMs;
        rotationTrigger=true;
      }
    } else {
      if(w_filt<=THRESH_OFF&&(nowMs-lastToggleMs)>=MIN_HOLD_MS) { ifStrumming=0; lastToggleMs=nowMs; }
    }
    if(prevStrumming==0&&ifStrumming==1&&fsrPressed) rotationTrigger=true;
  }
  if(haveAccel){
    if((a_mag-a_filt)>=A_SPIKE_REL&&fsrPressed) accelTrigger=true;
  }
  if((rotationTrigger||accelTrigger)&&fsrPressed) try_pulse_and_send(nowMs);
  if(strumPulse&&nowMs>=pulseEndMs) strumPulse=0;
}

// ===================== SETUP =====================
void setup(){
  Serial.begin(115200);
  Serial.println("Starting BLE + IMU strummer");

  BLEDevice::init("XIAO_ESP32S3");
  BLEServer *pServer=BLEDevice::createServer();
  BLEService *pService=pServer->createService(SERVICE_UUID);
  pCharacteristic=pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ|
    BLECharacteristic::PROPERTY_WRITE|
    BLECharacteristic::PROPERTY_NOTIFY
  );
  pCharacteristic->setValue("ready");
  pService->start();
  BLEAdvertising *pAdvertising=BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();
  Serial.println("BLE ready - connect and enable notifications");
}

// ===================== MAIN LOOP =====================
void loop(){
  static bool fsrPressed=false;

  if(!imu_inited){
    if(!bno08x.begin_I2C()){ Serial.println("Failed to find BNO08x chip"); delay(1000); return; }
    bno08x.enableReport(SH2_GAME_ROTATION_VECTOR,REPORT_US);
    bno08x.enableReport(SH2_LINEAR_ACCELERATION,REPORT_US);
    Serial.println("IMU ready");
    imu_inited=true;
  }

  if(bno08x.wasReset()){
    Serial.println("Sensor reset; re-enabling reports");
    bno08x.enableReport(SH2_GAME_ROTATION_VECTOR,REPORT_US);
    bno08x.enableReport(SH2_LINEAR_ACCELERATION,REPORT_US);
    have_prev=false; w_filt=0.f; a_filt=0.f;
  }

  while(bno08x.getSensorEvent(&sensorValue)){
    int fsrValue=analogRead(FSR_PIN);
    if(!fsrPressed&&fsrValue>=FSR_PRESS_ON) fsrPressed=true;
    else if(fsrPressed&&fsrValue<=FSR_PRESS_OFF){
      fsrPressed=false;
      sendBLE(0, 0, 0);
      continue;
    } 
    
    uint32_t nowMs=millis();

    if(sensorValue.sensorId==SH2_GAME_ROTATION_VECTOR){
      q_w=sensorValue.un.gameRotationVector.real;
      q_x=sensorValue.un.gameRotationVector.i;
      q_y=sensorValue.un.gameRotationVector.j;
      q_z=sensorValue.un.gameRotationVector.k;
      quatNormalize(q_w,q_x,q_y,q_z);
      uint32_t ts=sensorValue.timestamp;
      if(!have_prev){ qpw=q_w;qpx=q_x;qpy=q_y;qpz=q_z; ts_prev=ts; have_prev=true; continue; }
      float dt=dt_from_timestamps(ts,ts_prev); ts_prev=ts;
      float owx,owy,owz;
      if(!omega_from_quats(qpw,qpx,qpy,qpz,q_w,q_x,q_y,q_z,dt,owx,owy,owz)){ qpw=q_w;qpx=q_x;qpy=q_y;qpz=q_z; continue; }
      qpw=q_w;qpx=q_x;qpy=q_y;qpz=q_z;
      wx=owx; wy=owy; wz=owz;
      w_mag=vmag3(wx,wy,wz);
      float tau_s=TAU_MS/1000.f; float alpha=1.f-expf(-dt/fmaxf(1e-6f,tau_s));
      w_filt+=alpha*(w_mag-w_filt); haveRot=true;
      checkStrum(nowMs,fsrPressed);
    } else if(sensorValue.sensorId==SH2_LINEAR_ACCELERATION){
      ax=sensorValue.un.linearAcceleration.x;
      ay=sensorValue.un.linearAcceleration.y;
      az=sensorValue.un.linearAcceleration.z;
      a_mag=vmag3(ax,ay,az);
      float alpha_a=1.f-expf(-(REPORT_US*1e-6f)/fmaxf(1e-6f,A_TAU_MS/1000.f));
      a_filt+=alpha_a*(a_mag-a_filt); haveAccel=true;
      float dt=dt_from_timestamps(sensorValue.timestamp,ts_prev_accel);
      ts_prev_accel=sensorValue.timestamp;
      integrateAccelToVelocity(dt,fsrPressed);
      checkStrum(nowMs,fsrPressed);
    }
    Serial.printf("estimated speed: %.3f, %.3f\n", getLinearSpeed(), w_filt);

  }

  delay(2);
}
