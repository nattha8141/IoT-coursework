#include <DHT.h>
#include <Wire.h>
#include <RTClib.h>
#include <WiFi.h>
#include <HTTPClient.h>

// WiFi credentials (I'll star this one in github because it's confidential)
const char* ssid = "*******";
const char* password = "********";

// Google Sheets URL
const char* googleScriptURL = "https://script.google.com/macros/s/AKfycbyZQFjU6S4rIOnj34hEShhRu_Pv_MYP1Unw1eJx6PxyiIDrumC_VUXr07WNJt5ap5M_/exec";

// Photo Resistors
const int PHOTO_GREEN = 1;
const int PHOTO_BLUE = 2;
const int PHOTO_CONTROL = 4;

// RGB LEDs
const int RED_PIN = 20;
const int BLUE_PIN = 47;
const int GREEN_PIN = 48;

// DHT11
const int DHT_PIN = 5;
DHT dht(DHT_PIN, DHT11);

// RTC
const int SDA_PIN = 6;
const int SCL_PIN = 7;
RTC_DS1307 rtc;

// LED brightness (I adjust the value here to make sure the luminousity come out the same)
int redBrightness = 180;
int greenBrightness = 50;
int blueBrightness = 255;

// Timing — 15 minute cycle
unsigned long cycleStart = 0;
const unsigned long CYCLE_LENGTH = 900000; // 15 minutes, use 60000 for debugging, 900000 for experiment
const unsigned long RED_ON_TIME = 895000; // Red ON at 14 min 55 sec, use 55000 for debugging, 895000 for experiment
const unsigned long SENSOR_READ_TIME = 897000; // Read sensors at 14 min 57 sec, use 57000 for debugging, 897000 for experiment
bool redIsOn = false;
bool sensorReadDone = false;

void setup() {
  Serial.begin(115200);

  // LED pins
  pinMode(RED_PIN, OUTPUT);
  pinMode(BLUE_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);

  // Start with red OFF, green and blue ON
  analogWrite(RED_PIN, 0);
  analogWrite(GREEN_PIN, greenBrightness);
  analogWrite(BLUE_PIN, blueBrightness);

  // DHT11
  dht.begin();

  // RTC
  Wire.begin(SDA_PIN, SCL_PIN);
  if (!rtc.begin()) {
    Serial.println("ERROR: RTC not found!");
    while (1);
  }

  // This one to set time the time according to our timezone, after it sets out correctly the code below will be commented
  // rtc.adjust(DateTime(2026, 2, 26, 19, 30, 0));

  // Connect to WiFi
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" Connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  Serial.println("Bean Sprout Experiment - Google Sheets Logging");
  Serial.println("Cycle: 14m55s dark → 5s red ON (read at 2s) → repeat");
  Serial.println("Green and Blue LEDs: always ON");
  Serial.println("--------------------------------------------");

  cycleStart = millis();
}

void loop() {
  unsigned long elapsed = millis() - cycleStart;

  // PHASE 1: 0 to 14:55 — Red OFF
  if (elapsed < RED_ON_TIME) {
    if (redIsOn) {
      analogWrite(RED_PIN, 0);
      redIsOn = false;
    }
  }

  // PHASE 2: 14:55 to 15:00 — Red ON
  if (elapsed >= RED_ON_TIME && elapsed < CYCLE_LENGTH) {
    if (!redIsOn) {
      analogWrite(RED_PIN, redBrightness);
      redIsOn = true;
      Serial.println("Red LED ON — waiting 2 sec for sensor read...");
    }
  }

  // PHASE 3: 14:57 — Read all sensors
  if (elapsed >= SENSOR_READ_TIME && !sensorReadDone) {
    sensorReadDone = true;

    // Get timestamp
    DateTime time = rtc.now();
    char timestamp[20];
    sprintf(timestamp, "%04d-%02d-%02d %02d:%02d:%02d",
            time.year(), time.month(), time.day(),
            time.hour(), time.minute(), time.second());

    // Read sensors
    int greenValue = analogRead(PHOTO_GREEN);
    int blueValue = analogRead(PHOTO_BLUE);
    int controlValue = analogRead(PHOTO_CONTROL);
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();

    // Print to Serial Monitor (for debugging)
    Serial.print(timestamp);
    Serial.print(" | Green: ");
    Serial.print(greenValue);
    Serial.print(" | Blue: ");
    Serial.print(blueValue);
    Serial.print(" | Ctrl: ");
    Serial.print(controlValue);
    Serial.print(" | Temp: ");
    Serial.print(temperature, 1);
    Serial.print(" | Humid: ");
    Serial.println(humidity, 1);

    // Send to Google Sheets via GET request
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);

      String url = String(googleScriptURL) +
                   "?timestamp=" + String(timestamp) +
                   "&green=" + String(greenValue) +
                   "&blue=" + String(blueValue) +
                   "&control=" + String(controlValue) +
                   "&temperature=" + String(temperature, 1) +
                   "&humidity=" + String(humidity, 1);

      // To replace spaces in timestamp with %20
      url.replace(" ", "%20");

      http.begin(url);
      int httpCode = http.GET();

      Serial.print("HTTP code: ");
      Serial.println(httpCode);
      Serial.print("Response: ");
      Serial.println(http.getString());

      http.end();
    } else {
      Serial.println("WiFi disconnected! Attempting reconnect");
      WiFi.begin(ssid, password);
    }
  }

  // PHASE 4: 15:00 — Reset cycle
  if (elapsed >= CYCLE_LENGTH) {
    analogWrite(RED_PIN, 0);
    redIsOn = false;
    sensorReadDone = false;
    cycleStart = millis();
    Serial.println("--New cycle (15 min)--");
  }
}