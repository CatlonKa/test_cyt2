#ifndef BSP_UART_H
#define BSP_UART_H

#include <stdint.h>

void     uart_init(void);
void     uart_send(const uint8_t *data, uint32_t len);
void     uart_print(const char *s);
uint32_t uart_available(void);
int      uart_getc(void);

#endif