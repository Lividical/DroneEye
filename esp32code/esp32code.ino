const int PWM_PIN = 18;
const int PWM_FREQ = 50;
const int PWM_RES = 16;
const int PWM_MAX = 65535;

String input = "";

void setDuty(float dutyPercent) {
  if (dutyPercent < 0.0) dutyPercent = 0.0;
  if (dutyPercent > 100.0) dutyPercent = 100.0;

  uint32_t dutyCount = (uint32_t)((dutyPercent / 100.0) * PWM_MAX);
  ledcWrite(PWM_PIN, dutyCount);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  ledcAttach(PWM_PIN, PWM_FREQ, PWM_RES);
  setDuty(7.5);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (input.length() > 0) {
        setDuty(input.toFloat());
        input = "";
      }
    } else {
      input += c;
    }
  }
}