#include <Wire.h>
#include "max86150.h"
#include <SoftwareSerial.h>
MAX86150 max86150Sensor;

uint16_t ppgunsigned16, irunsigned16, redunsigned16;
int16_t ecgsigned16;
int status;

#define DATA_LEN 6
const char DataPacketHeader[5] = {0x0A, 0xFA, DATA_LEN, 0, 0x02};
const char DataPacketFooter[2] = {0, 0x0B};
SoftwareSerial BT(10, 11);
void setup() {
    Serial.begin(57600);
    BT.begin(57600);
    pinMode(13, OUTPUT);  // 将数字引脚13设置为输出模式
    digitalWrite(13, HIGH); // 将数字引脚13设置为高电平
    pinMode(12, INPUT); 

    // Initialize sensor
    if (!max86150Sensor.begin(Wire, I2C_SPEED_FAST)) {
        Serial.println("MAX86150 was not found. Please check wiring/power.");
        while (1);  // Halt if sensor not found
    }

    Serial.println("MAX86150 detected!");
    Serial.print("Part ID: ");
    Serial.println(max86150Sensor.readPartID());  // Output the part ID

    max86150Sensor.setup(); // Configure sensor with default settings
    Serial.println("Sensor setup complete.");
}

void loop() {

  status = digitalRead(12);  // 读取12号引脚的电平状态
  
    if (max86150Sensor.check() > 0) {
        irunsigned16  = (uint16_t) (max86150Sensor.getFIFOIR() >> 2);  // Read IR data
        redunsigned16 = (uint16_t) (max86150Sensor.getFIFORed() >> 2);  // Read Red LED data
        ecgsigned16   = (int16_t)  (max86150Sensor.getFIFOECG() >> 2);  // Read ECG data

        sendDataPacket(irunsigned16, redunsigned16, ecgsigned16);
    }
}

void sendDataPacket(uint16_t ir, uint16_t red, int16_t ecg) {
 
  for(int i = 0; i < sizeof(DataPacketHeader); i++) {
      Serial.write(DataPacketHeader[i]);
  }

  // Send ECG data (2 bytes)
  Serial.write((uint8_t)(ecg & 0xFF));
  Serial.write((uint8_t)((ecg >> 8) & 0xFF));

  // Send IR data (2 bytes)
  Serial.write((uint8_t)(ir & 0xFF));
  Serial.write((uint8_t)((ir >> 8) & 0xFF));

  // Send Red data (2 bytes)
  Serial.write((uint8_t)(red & 0xFF));
  Serial.write((uint8_t)((red >> 8) & 0xFF));

  // Send packet footer
  for(int i = 0; i < sizeof(DataPacketFooter); i++) {
      Serial.write(DataPacketFooter[i]);
  }

    for(int i = 0; i < sizeof(DataPacketHeader); i++) {
        BT.write(DataPacketHeader[i]);
    }

    // Send ECG data (2 bytes)
    BT.write((uint8_t)(ecg & 0xFF));
    BT.write((uint8_t)((ecg >> 8) & 0xFF));

    // Send IR data (2 bytes)
    BT.write((uint8_t)(ir & 0xFF));
    BT.write((uint8_t)((ir >> 8) & 0xFF));

    // Send Red data (2 bytes)
    BT.write((uint8_t)(red & 0xFF));
    BT.write((uint8_t)((red >> 8) & 0xFF));

    // Send packet footer
    for(int i = 0; i < sizeof(DataPacketFooter); i++) {
        BT.write(DataPacketFooter[i]);
    }

}




