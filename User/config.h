#ifndef CONFIG_H
#define CONFIG_H

#define LED_PORT        ioss_0_port_23_pin_7_PORT
#define LED_PIN         ioss_0_port_23_pin_7_PIN
#define LED(x)          Cy_GPIO_Write(LED_PORT, LED_PIN, (!(x)))
#define LED_TOGGLE()    Cy_GPIO_Inv(LED_PORT, LED_PIN)



#endif