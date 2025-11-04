#include <Adafruit_BNO08x.h>
#include <math.h>  // sqrtf

#define BNO08X_CS    10
#define BNO08X_INT   9
#define BNO08X_RESET -1

Adafruit_BNO08x bno08x(BNO08X_RESET);
sh2_SensorValue_t sensorValue;

enum PrintMode : uint8_t { PRINT_ACCEL = 0, PRINT_GAME_RV = 1 };
volatile PrintMode g_mode = PRINT_ACCEL;  // default: print acceleration

void setup(void) {
  Serial.begin(115200);
  while (!Serial) delay(10);

  Serial.println("BNO08x: Accel + Game RV (type 0 or 1 to switch)");

  // I2C init (use begin_SPI / begin_UART if desired)
  if (!bno08x.begin_I2C()) {
    Serial.println("Failed to find BNO08x chip");
    while (1) delay(10);
  }
  Serial.println("BNO08x Found!");

  setReports();

  Serial.println("Reading events...");
  Serial.println("Mode: 0=Accel, 1=GameRV. Current=0");
  delay(100);
}

// Enable both reports (about ~100 Hz)
void setReports(void) {
  Serial.println("Enabling reports: Linear Accel + Game Rotation Vector");

  if (!bno08x.enableReport(SH2_LINEAR_ACCELERATION, 10000)) {
    Serial.println("Could not enable linear acceleration");
  }
  if (!bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, 10000)) {
    Serial.println("Could not enable game rotation vector");
  }
}

void handleSerialInput() {
  while (Serial.available()) {
    int c = Serial.read();
    if (c == '0') {
      g_mode = PRINT_ACCEL;
      Serial.println("Switched mode -> Linear Accel (0)");
    } else if (c == '1') {
      g_mode = PRINT_GAME_RV;
      Serial.println("Switched mode -> Game Rotation Vector (1)");
    }
  }
}

void loop() {
  handleSerialInput();

  if (bno08x.wasReset()) {
    Serial.println("Sensor was reset; re-enabling reports");
    setReports();
  }

  // Poll one event at a time (library queues internally)
  if (!bno08x.getSensorEvent(&sensorValue)) {
    delay(1);
    return;
  }

  // Print only the currently selected stream
  switch (sensorValue.sensorId) {
    case SH2_LINEAR_ACCELERATION:
      if (g_mode == PRINT_ACCEL) {
        float ax = sensorValue.un.linearAcceleration.x;
        float ay = sensorValue.un.linearAcceleration.y;
        float az = sensorValue.un.linearAcceleration.z;
        float mag = sqrtf(ax * ax + ay * ay + az * az);

        // Units: m/s^2
        Serial.print("LinAcc x,y,z (m/s^2): ");
        Serial.print(ax, 4); Serial.print(", ");
        Serial.print(ay, 4); Serial.print(", ");
        Serial.print(az, 4);
        Serial.print(" | |a|: ");
        Serial.println(mag, 4);
      }
      break;

    case SH2_GAME_ROTATION_VECTOR:
      if (g_mode == PRINT_GAME_RV) {
        // Quaternion (unit, approximately; gravity removed, magnetic ignored)
        float r = sensorValue.un.gameRotationVector.real;
        float i = sensorValue.un.gameRotationVector.i;
        float j = sensorValue.un.gameRotationVector.j;
        float k = sensorValue.un.gameRotationVector.k;

        Serial.print("GameRV quat r,i,j,k: ");
        Serial.print(r, 6); Serial.print(", ");
        Serial.print(i, 6); Serial.print(", ");
        Serial.print(j, 6); Serial.print(", ");
        Serial.println(k, 6);
      }
      break;

    default:
      // Ignore other events (if any)
      break;  
  }

  // Small delay to keep output tidy
  delay(2);
}
