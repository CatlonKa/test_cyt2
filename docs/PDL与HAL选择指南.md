# PDL 与 HAL 选择指南（CYT2BL3 / TARGET_CYT2BL3）

> 行号与结论于 2026-11-26 对照 `mtb-hal-t2gbe4m v1.0.0` + `mtb-pdl-cat1 v3.25.0` 核实；升库后需重查。

---

## 0. 两层是什么

| 层 | 前缀 | 来源 | 特点 |
|---|---|---|---|
| **PDL** | `Cy_*` / `CY_*` | `mtb-pdl-cat1` | 器件专用，直接写寄存器；`Init` → `Enable` → (TriggerStart) |
| **HAL** | `mtb_hal_*` | `mtb-hal-t2gbe4m` | 薄封装 + 跨器件统一接口，**不是 PDL 的上层驱动** |

⛔ 本工程没有 `cyhal_*`：编译宏无 `CY_USING_HAL`，`main.c` 里那段是死代码。`cyhal_*` 是 PSOC 6 / `mtb-hal-cat1` 的命名，写进来编不过。

---

## 1. 结论

| 场景 | 用 |
|---|---|
| 精确时序（µs 级、I2C/SPI 时序）、高频 ISR、1 kHz+ 控制环 | **PDL** |
| DMA 搬运、tickless 低功耗、跨器件可移植 | **HAL** |
| 想要「外设 + DMA」开箱即用 | ⛔ 只有 UART 有胶水，且需 `COMPONENT_MW_ASYNC_TRANSFER`（本工程未装） |
| 延时 | 裸机 `Cy_SysLib_Delay()`；RTOS 用 `mtb_hal_system_delay_ms()` |

逐外设：

| 外设 | 推荐 | 理由 |
|---|---|---|
| GPIO | PDL | HAL 只省一个结构体，丢掉「宏名对应引脚」的可读性 |
| UART | PDL | `PutString` 够用；数组/异步写要先装 `COMPONENT_MW_ASYNC_TRANSFER` |
| I2C | 先 PDL | 唯一在 `mtb_hal_i2c_configure()` 里真调 `Cy_SCB_I2C_Init` 的外设，但无 DMA |
| SPI | PDL | `mtb_hal_spi.c` 26.7 KB 里 `dma` 出现 0 次，大块传输一点没省 |
| TCPWM PWM | PDL 初始化 + 运行期 `SetCompare` | `set_period` 走虚表，`set_compare_count` 零开销 |
| TCPWM Timer | PDL | HAL `setup` 不 Init；`start` 只做 `Counter_Enable` + `TriggerStart` |
| ADC (SAR) | PDL | HAL 多一层适配，收益小 |
| DMA | **HAL** | `Cy_DMA_*`(DW) 与 `Cy_DMAC_*` 是两套完全不同的 API，HAL 统一成 `mtb_hal_dma_*` |
| SysPm | **HAL** | `mtb_hal_syspm_tickless_*` 已串好「设唤醒源 → 进低功耗 → 算补偿」 |
| NVM / RTC / LPTimer | HAL | 带策略的复杂逻辑，PDL 样板太多 |

**用 HAL 前必须知道的三件事**

1. **`setup()` 不初始化硬件**：uart / spi / pwm / timer / gpio 的 setup 全是 `memset` + 存指针；全库只有 `mtb_hal_i2c_configure()` 会调 `Cy_SCB_I2C_Init`。启动仍得自己调 `Cy_*_Init` + `Enable`。
2. **外设 + DMA 的胶水只有 UART**：`mtb_hal_uart.c` 里 43 处 `dma`，全在 `MTB_HAL_DRIVER_AVAILABLE_DMA` 与 `COMPONENT_MW_ASYNC_TRANSFER` 下。
3. **SysPm 回调不会自动注册**：SCB UART / TCPWM 的 DeepSleep 回调在 `syspm-callbacks-t2gbe4m`（如 `mtb_syspm_scb_uart_deepsleep_callback`），HAL 自身 0 处引用，要自己挂到 `Cy_SysPm`。

---

## 2. 开销三档

### 第一档：零开销（`__STATIC_INLINE` 转发）

| HAL 函数 | 实际做的事 | 位置 |
|---|---|---|
| `mtb_hal_gpio_write` / `read` / `toggle` | → `Cy_GPIO_Write` / `Read` / `Inv` | `mtb_hal_gpio_impl.h:66` / `:77` / `:88` |
| `mtb_hal_uart_put` | → `Cy_SCB_UART_Put` + 重试 | `mtb_hal_uart_impl.h:117` |
| `mtb_hal_uart_write_string` | → `Cy_SCB_UART_PutString` | 同上 `:139` |
| `mtb_hal_pwm_set_compare_count` | → `Cy_TCPWM_PWM_SetCompare0Val` | `mtb_hal_pwm_mxtcpwm_v2.h:161` |
| `mtb_hal_pwm_start` | → `Cy_TCPWM_TriggerStart_Single` | `mtb_hal_pwm_impl.h:90` |
| `mtb_hal_system_delay_us` | 纯宏 → `Cy_SysLib_DelayUs` | `mtb_hal_system_impl.h:47` |

差别只在 HAL 要先 `LDR` 一次 `obj->port_addr`：≈2 周期 ≈12.5 ns @160 MHz，10 kHz 环里可忽略。

### 第二档：真实函数调用

| HAL 函数 | 位置 | 注意 |
|---|---|---|
| `mtb_hal_system_delay_ms` | `mtb_hal_system.c:62` | 裸机时就是 `Cy_SysLib_Delay()` |
| `mtb_hal_uart_write` | `mtb_hal_uart.c:750` | 4 个 `CY_ASSERT` + `Cy_SCB_UART_PutArray` |
| `mtb_hal_pwm_set_period` | `mtb_hal_pwm.c:158` | 内部走 `interface->get_frequency_hz` |

### 第三档：间接调用（只有 clock 有虚表）

`mtb_hal_hw_types_clock_srss.h:58~85`：

```c
typedef struct {
    const void*                      clock_ref;
    const mtb_hal_clock_interface_t* interface;   /* ← 虚表 */
} mtb_hal_clock_t;
```

`mtb_hal_pwm_set_period()` → `obj->tcpwm.clock->interface->get_frequency_hz(...)`：两次间接寻址 + 一次 `BLX`，约 10~20 周期。

**结论**：改频率用 `set_period`（低频即可），**每周期改占空比用 `set_compare_count`**。
GPIO / UART / I2C / SPI / PWM 的 `hw_types` 里没有 `interface` 指针，热路径碰不到虚表。

---

## 3. 真正的坑是 HAL 写死的策略

| HAL 行为 | 位置 | 后果 |
|---|---|---|
| `mtb_hal_uart_put` 失败重试 200 次 × 10 µs | `mtb_hal_uart_impl.h:120` | 最坏阻塞 2 ms，期间死等 |
| `mtb_hal_uart_get` 超时用 `delay_ms(1)` | 同上 `:96` | 超时粒度 1 ms，做不到 100 µs |
| 断言失败 → `CY_HALT()` = `bkpt 1` | `cy_utils.h:81` | 接调试器就停住；没调试器 → HardFault；在 ISR 里等于卡死 |

本工程实测：`-DDEBUG` 有、`-DNDEBUG` 无 → `CY_ASSERT` 全活。

`CY_ASSERT`（`cy_utils.h:111`）由 `NDEBUG` **或** `CY_NO_ASSERT` 关。
`CY_ASSERT_LEVEL` 是另一套开关，默认 `CY_ASSERT_CLASS_3`（L1/L2/L3 全开）→
只想砍 L2/L3 时用 `DEFINES += CY_ASSERT_LEVEL=1`，比整个 `NDEBUG` 划算。

---

## 4. 混用规则

**允许混用**，红线一条：**HAL 不替你 Init**（见 §1 三件事 ①）。

```c
/* ✅ 纯 PDL */
Cy_SCB_UART_Init(scb_0_HW, &scb_0_config, &uart_context);
Cy_SCB_UART_Enable(scb_0_HW);

/* ✅ PDL 启动 + HAL 使用 */
Cy_SCB_UART_Init(scb_0_HW, &scb_0_config, &uart_context);
Cy_SCB_UART_Enable(scb_0_HW);
mtb_hal_uart_setup(&uart_obj, &scb_0_hal_config, &uart_context, &scb_0_hal_clock);

/* ❌ 只调 setup：寄存器一个没动，串口不出数据 */
mtb_hal_uart_setup(&uart_obj, &scb_0_hal_config, &uart_context, NULL);
```

- **别名宏别改**：`scb_0_HW` / `scb_0_config` 给 PDL，`scb_0_hal_config` 给 HAL，两套并存。
- **断言策略统一**：全项目 `NDEBUG` 或全留；局部 `CY_NO_ASSERT` 会让人误判。

---

## 5. 本工程现状

| 项 | 状态 |
|---|---|
| HAL 库 | 已装 v1.0.0，`COMPONENT_MTB_HAL` 已定义；20 个 `mtb_hal_*.o` 都参与编译 |
| 已用 HAL | **0 处**，`User/` 下全是 PDL |
| HAL 占 Flash 吗 | 不占。未引用段链接时被丢弃（map 里 `mtb_hal_uart_setup` 地址为 `0x00000000`），`.text` 仅 8.4 KB |
| UART | DC 已配 SCB0（115200/8N1，P0.0/P0.1），`scb_0_*` / `scb_0_hal_config` 都在；**`main.c` 里暂无 UART 代码** |
| GPIO | PDL：`LED_TOGGLE()` → `Cy_GPIO_Inv`（P23.7） |
| retarget-io | 未安装 → 没有 `printf` |
| 时钟 | PLL0 = CLK_HF0 = 160 MHz，CLK_PERI = 80 MHz；SCB0 走 `div_8[0]` 87 分频 = 919.5 kHz（115200 @ ovs8） |
| 断言 | `-DDEBUG` 有、`-DNDEBUG` 无 → 全活；`CY_ASSERT_LEVEL` 未定义 = CLASS_3 |

❗ DC 也常被误以为「生成即可用」：`init_cycfg_peripherals()` 只做
`Cy_SysClk_PeriPclkAssignDivider(PCLK_SCB0_CLOCK, …)`，不含 `Cy_*_Init` / `Enable`。

---

## 6. 自查

```bash
arm-none-eabi-objdump -d --no-show-raw-insn build/CYT2BL3/Debug/mtb-example-empty-app.elf \
  | grep -A 20 "<main>:"
```

| 现象 | 结论 |
|---|---|
| `bl <Cy_GPIO_Write>` | 没内联，多一次调用 |
| 只有 `str` | 已内联，零开销 |
| `ldr r3,[r3]` + `blx r3` | 走了虚表，注意调用频率 |
