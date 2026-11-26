#include "cycfg.h"
#include "uart.h"

static cy_stc_scb_uart_context_t uart_ctx;

void uart_init(void)
{
    Cy_SCB_UART_Init(UART0_HW, &UART0_config, &uart_ctx);
    Cy_SCB_UART_Enable(UART0_HW);
}

void uart_send(const uint8_t *data, uint32_t len)
{
    Cy_SCB_UART_PutArrayBlocking(UART0_HW, (void *)data, len);
    /* 选对那个 Blocking 的 API，注意 cast */
}