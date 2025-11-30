// code to test the FSR newton threshold

const int FSR_PIN        = A1;   // 3.3V -> FSR -> node -> 10k -> GND, node -> A1
const int FSR_PRESS_ON   = 500;  // same thresholds as your main code
const int FSR_PRESS_OFF  = 400;

void setup() {
  Serial.begin(115200);
  delay(500);

  // Match your 0–1023 range (10-bit)
  analogReadResolution(10);

  Serial.println("FSR calibration: add weights and watch FSR/pressed");
}

void loop() {
  static bool fsrPressed = false;

  int fsrValue = analogRead(FSR_PIN);

  // same hysteresis logic you already use
  if (!fsrPressed && fsrValue >= FSR_PRESS_ON) {
    fsrPressed = true;
  } else if (fsrPressed && fsrValue <= FSR_PRESS_OFF) {
    fsrPressed = false;
  }

  // 👇 this is the line you liked
  Serial.printf("FSR=%d pressed=%d\n", fsrValue, fsrPressed);

  delay(50);  // ~20Hz updates, adjust if you want
}
