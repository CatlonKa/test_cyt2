# CYT2BL3 学习路线（64-LQFP · CYT2BL3CAS）

> 目标：用 **CYT2BL3** 学会「Device Configurator 配置引脚 → PDL 写外设 → 调试」这套通用流程
> 定位：**打基础**。摄像头、双核、Cache、SMIF/ETH 等"两板差异大"的内容留到 CYT4BB7
> 器件：`TARGET=CYT2BL3` / `DEVICE=CYT2BL3CAS` / 64-LQFP / 单 Cortex-M4 @160 MHz
>
> 本文引脚数据全部取自 `mtb-pdl-cat1/release-v3.25.0/devices/COMPONENT_CAT1A/include/gpio_tviibe4m_64_lqfp.h`（64 脚真实 AF 表）

---

## 0. ✅ 前置检查（两项均已核实通过，无需处理）

| # | 检查项 | 现状（2026-11-25 核实） |
|---|---|---|
| 1 | `cycfg_notices.h` 里那句 `#error "Unexpected MPN; expected DEVICE:=CYT2BL3CAS"` 会不会报 | ✅ **不会**。它被 `#if !defined(CYT2BL3CAS)` 包着，而 build 实际带了 `-DCYT2BL3CAS` → 条件为假 |
| 2 | P23.4 / P23.5 / P23.6 有没有被配成 GPIO（会毁掉调试口） | ✅ **没有**。`cycfg_pins.h` 里虽有三者的 entry，但 `cycfg_routing.h` 给的 HSIOM 仍是 `P23_4_CPUSS_SWJ_SWO_TDO` / `P23_5_...SWCLK_TCLK` / `P23_6_...SWDIO_TMS` → 上电后依旧是调试功能 |

**两个名字别混**：`design.modus` 的 `mpn="CYT2BL3CAS"` 是**料号**，`Makefile` 的 `TARGET=CYT2BL3` 是**BSP 名**。
build 从 BSP 映射出料号宏，所以两者对得上。只有「DC 改了型号、Makefile 没跟着改」时才真会撞上那个 `#error`。

> ✅ 真正的判据只有一个：`python .github/skills/mtb-tools/scripts/run_make.py --args build` 能过。

> 参考：`docs/工程配置流程.md`、`docs/编译烧录排障手册.md`、`.github/skills/mtb-device-configurator/SKILL.md`

---

## 1. 本型号实测资源（从 `cyt2bl3cas.h` 读出）

| 资源 | 数量 | 说明 |
|---|---|---|
| 内核 | **1× Cortex-M4F** @160 MHz | CM0+ 为预编译 `CM0P_SLEEP` 镜像（约 3.8 KB） |
| Flash / SRAM | 4160 KB / 512 KB | |
| TCPWM | **63×16-bit（GRP0）+ 12×16-bit（GRP1 电机）+ 8×32-bit（GRP2）** | 与 CYT4BB7 完全一致 |
| SCB（UART/I²C/SPI） | **7 个：SCB0~SCB5 + SCB7** | |
| ADC | **2× SAR**（SAR0、SAR1）+ 电机专用 `P11.0/1/2` | |
| DMA | **DW0、DW1** | |
| 其他 | CAN-FD、LIN、CXPI、SmartIO、EVTGEN | ⚠ **CXPI 只有 CYT2B 有** |
| **没有** | SMIF、SDHC、I²S、ETH、D-Cache、ITCM/DTCM | 这些都是 CYT4BB7 才有的 |

> ⚠ 芯片内部数量 ≠ 你能用的数量。**64 脚封装只有约 50 个 IO**，请按下表规划。

---

## 2. 64-LQFP 引脚地图（✅ 已验证）

### 2.1 🔴 保留引脚（绝对不要占）

| 引脚 | 功能 | 说明 |
|---|---|---|
| **P23.4** | `CPUSS_SWJ_SWO_TDO` | **调试口** |
| **P23.5** | `CPUSS_SWJ_SWCLK_TCLK` | **调试口** |
| **P23.6** | `CPUSS_SWJ_SWDIO_TMS` | **调试口** |
| **P23.7** | `CPUSS_SWJ_SWDOE_TDI` | **调试口** |
| **P2.0** | `CPUSS_SWJ_TRSTN` | 调试相关，建议保留 |
| P21.0 / P21.1 | `SRSS_WCO_IN` / `WCO_OUT` | 32.768 kHz 晶振（若用 RTC） |
| P21.2 / P21.3 | `SRSS_ECO_IN` / `ECO_OUT` | 主晶振 |

> ⚠ **P23.4 同时是 `PERI_TR_IO_INPUT31`**，看起来"能当触发输入"，但它是 SWO。别被 AF 表骗了。

### 2.2 可直接用于学习的自由引脚

```
P0.0  P0.1  P0.2  P0.3
P2.1
P5.0  P5.1
P6.0  P6.1  P6.2  P6.3  P6.4  P6.5  P6.6
P7.0  P7.1  P7.2
P8.0  P8.1
P11.0 P11.1 P11.2      ← 电机 ADC 专用，学习 ADC 时正好用
P12.0 P12.1
P13.0 P13.1 P13.2 P13.3
P14.0 P14.1 P14.2
P18.0 P18.1 P18.3 P18.4 P18.5 P18.6 P18.7
P22.0
P23.3
```

### 2.3 外设可用引脚速查

#### UART（SCB，已验证）

| SCB | RX | TX |
|---|---|---|
| **SCB0**（推荐做 debug 口） | **P0.0** | **P0.1** |
| SCB1 | P18.0 | P18.1 |
| SCB2 | P14.0 | P14.1 |
| SCB3 | P13.0 | P13.1 |
| SCB4 | P6.0 | P6.1 |
| SCB5 | P7.0 | P7.1 |
| SCB7 | P2.0 ⛔ | P2.1 |

#### I²C（SCB，已验证）

| SCB | SDA | SCL | 备注 |
|---|---|---|---|
| **SCB3**（推荐） | **P13.1** | **P13.2** | |
| SCB4 | P6.1 | P6.2 | |
| SCB5 | P7.1 | P7.2 | |
| SCB2 | P14.1 | P14.2 | |
| **SCB0** | **P0.3** | **P0.2** | ✅ **可在 Deep Sleep 下工作** |
| SCB7 | P0.0 | P0.1 | 与 UART0 冲突，别混用 |

#### ADC 输入（PASS/SAR，已验证）

| SAR | 引脚 |
|---|---|
| **PADS0~6** | **P6.0, P6.1, P6.2, P6.3, P6.4, P6.5, P6.6**（连续 7 个，做扫描最方便） |
| PADS8~10 | P7.0, P7.1, P7.2 |
| PADS16 | P8.1 |
| PADS36~37 | P12.0, P12.1 |
| PADS44~47 | P13.0, P13.1, P13.2, P13.3 |
| PADS52~54 | P14.0, P14.1, P14.2 |
| PADS64~71 | P18.0, P18.1, P18.3~P18.7 |
| **电机专用** | **P11.0 = MOTOR0，P11.1 = MOTOR1，P11.2 = MOTOR2** |

#### 可作硬件触发的引脚（`PERI_TR_IO_INPUT`，已验证）

| 引脚 | 触发编号 | 可用性 |
|---|---|---|
| P2.0 | INPUT2 | ⛔ SWJ_TRSTN |
| **P2.1** | **INPUT3** | ✅ |
| **P6.6** | **INPUT8** | ✅ |
| **P8.1** | **INPUT14** | ✅ |
| **P12.0** | **INPUT20** | ✅ |
| **P12.1** | **INPUT21** | ✅ |
| **P23.3** | **INPUT30** | ✅ |
| P23.4 | INPUT31 | ⛔ SWO |

> `PERI_TR_IO_INPUT` 是 DMA/TCPWM 硬件触发的入口，学 ADC+DMA 定时采样时会用到。

---

## 3. 学习路线表（按顺序做，每项打勾）

### 阶段〇 · 环境与工具链（必须先过）

| # | 学习项 | 关键点 | 参考路径 |
|---|---|---|---|
| 0.1 | [x] 跑通空工程（`#error` 无需处理，见 §0） | MPN 与 BSP 名不是同一个东西 | `docs/工程配置流程.md` |
| 0.2 | [ ] 学会用 `run_make.py`（build / clean / program / getlibs） | ⚠ 用 `python` 不是 `python3` | `.github/skills/mtb-tools/SKILL.md` |
| 0.3 | [ ] 学会 F5 调试 / attach（J-Link） | 探针能力决定能不能调试 | `docs/调试配置.md` |
| 0.4 | [ ] 学会用 Device Configurator 保存+生成，看懂 `GeneratedSource/` 产出 | **永不手改 GeneratedSource** | `.github/instructions/mtb-generated-source-protection.instructions.md` |

**验收**：能改一个引脚配置 → 重新生成 → 编译 → 烧录 → 看到现象。

---

### 阶段一 · 基础（单外设，无中断）

| # | 学习项 | Device Configurator 要点 | PDL API | 建议引脚 | 参考路径 |
|---|---|---|---|---|---|
| 1.1 | [ ] **GPIO 输出**（点灯） | Pin 配 `Digital Output` / `Strong Drive` | `Cy_GPIO_Write/Inv`<br>或 `CYBSP_LED_*` | P5.0 | `.github/skills/mtb-device-configurator/references/pin-assignment.md` |
| 1.2 | [ ] **GPIO 输入**（读按键） | `Digital Input` / `High-Z`；上下拉按硬件选 | `Cy_GPIO_Read` | P5.1 | `.../references/pin-assignment.md` |
| 1.3 | [ ] **时钟体系**：CLKHF、PERI 分频器 | Clocks 页；GUI 值 N → 生成 `N-1U`（**这是正常的**） | `Cy_SysClk_Peri*Divider` | — | `.../references/device-configurator-gotchas.md` |
| 1.4 | [ ] **UART + retarget-io**（printf） | SCB0 配 UART；波特率 115200 | `cy_retarget_io_init()` | **P0.0=RX / P0.1=TX** | `.github/skills/mtb-retarget-io/SKILL.md`<br>`.../references/uart-runtime-patterns.md` |
| 1.5 | [ ] **GPIO 外部中断**（按键/编码器） | Pin 勾 `Interrupt`；选 Rising/Falling | `Cy_SysInt_Init` + `NVIC_EnableIRQ` | **P2.1** 或 **P8.1**（带触发能力） | `.../references/gpio-interrupt-patterns.md` |

**验收**：串口能打印自己写的变量，按键能触发中断并在串口打印计数。

> ⛔ 三条铁律（会伴随你整个学习过程）：
> 1. 所有 `cy_stc_*_context_t` **必须文件级 `static`**（PDL 保留指针，放栈上会 HardFault）
> 2. ISR 注册 + `NVIC_EnableIRQ` **必须在 `__enable_irq()` 之前**
> 3. `cybsp_init()` 已经做了生成代码的初始化，**不要**再调 `Cy_PDL_Init()` / `init_cycfg_all()`

---

### 阶段二 · 定时与模拟（重点）

| # | 学习项 | Device Configurator 要点 | 运行时必须补的一步 | 建议引脚 | 参考路径 |
|---|---|---|---|---|---|
| 2.1 | [ ] **TCPWM 定时器**（周期中断） | Peripheral → TCPWM → **Timer** 模式 | `Cy_TCPWM_*_Init` → `_Enable` → **`Cy_TCPWM_TriggerStart`** | 任意 `TCPWM0_LINE` 脚 | `.../references/timer-counter-patterns.md` |
| 2.2 | [ ] **TCPWM PWM**（呼吸灯） | PWM 模式，设 period/compare | 同上（**Enable 不等于开始计数！**） | 任意 `TCPWM0_LINE` 脚 | `.../references/pwm-runtime-patterns.md` |
| 2.3 | [ ] **PWM 互补 + 死区** | PWM 模式 + `deadTime`；GRP1 支持更好 | 同上 | 两个相邻 `TCPWM0_LINE` | `.../references/pwm-runtime-patterns.md` |
| 2.4 | [ ] **ADC 单通道**（读电位器） | PASS → SAR0 → 使能一个通道 | `Cy_ADC_Init` → `_Enable` → 校准 → `_Start` | **P6.0**（PADS0） | `.../references/autanalog-sampling-patterns.md` |
| 2.5 | [ ] **ADC 多通道扫描** | 使能多个通道，配 sequencer | 同上 + 读每通道结果 | **P6.0~P6.5**（连续 6 个） | `.../references/autanalog-sampling-patterns.md` |
| 2.6 | [ ] **ADC 读电机专用引脚** | 用 `ADC[0/1/2]_M` 通道 | 3 个 ADC **同步采样** | **P11.0 / P11.1 / P11.2** | `.../references/autanalog-sampling-patterns.md` |
| 2.7 | [ ] **I²C 主机**（读 EEPROM/传感器） | SCB3 → I²C，开 Master | `Cy_SCB_I2C_Init` → `_Enable` | **P13.1=SDA / P13.2=SCL** | `.../references/i2c-bus-patterns.md` |
| 2.8 | [ ] **I²C 从机（EZI2C）** | SCB3 → EZI2C | 同上 | 同上 | `.../references/i2c-bus-patterns.md` |
| 2.9 | [ ] **SPI 主机**（读 SPI 传感器/屏） | SCB4 → SPI | `Cy_SCB_SPI_Init` → `_Enable` | P6.0=MISO / P6.1=MOSI / P6.2=SCLK / P6.3=SS | `.../references/spi-transfer-patterns.md` |

**验收**：能用定时器中断做 1 kHz 采样节拍；能读电位器并在串口连打；能用 I²C 读到外设 ID。

> ⚠ TCPWM 最常见的坑：**只 `Enable` 不 `TriggerStart` → 计数器根本不动**，现象是"PWM 没输出/中断不进"。

---

### 阶段三 · 联动（真正体现这颗芯片的价值）

| # | 学习项 | 关键点 | 参考路径 |
|---|---|---|---|
| 3.1 | [ ] **DW DMA 内存→内存** | 描述符配置；`Cy_DMA_Channel_*` | `.../references/dma-patterns.md` |
| 3.2 | [ ] **DMA 内存→外设**（UART 发数组） | 源递增、目的不递增 | `.../references/dma-patterns.md` |
| 3.3 | [ ] **DMA 外设→内存**（UART 收） | 相反方向 | `.../references/dma-patterns.md` |
| 3.4 | [ ] **TCPWM 定时触发 ADC + DMA 搬运** | TrigMux 连接；一次配好 CPU 零参与 | `.../references/dma-patterns.md` + `.../references/autanalog-sampling-patterns.md` |
| 3.5 | [ ] **GPIO 触发 → DMA**（用 `PERI_TR_IO_INPUT`） | `Cy_GPIO_SetHSIOM()` + `Cy_TrigMux_Connect()`<br>⚠ **这两步 GUI 通常配不了，必须写代码** | `.../references/device-configurator-gotchas.md` |
| 3.6 | [ ] **CAN-FD 收发** | `Cy_CANFD_*`；先做回环自测 | `.../references/pdl-apis.md` |
| 3.7 | [ ] **LIN** | SCB 或 LIN 模块 | `.github/skills/mtb-scb-lin-slave/SKILL.md` |
| 3.8 | [ ] **SmartIO**（引脚级逻辑，不占 CPU） | Smart I/O Configurator | `.github/skills/mtb-device-configurator/references/pdl-apis.md` |
| 3.9 | [ ] **EVTGEN**（事件互连，DeepSleep 可唤醒） | | `.../references/pdl-apis.md` |
| 3.10 | [ ] **低功耗**（Sleep / DeepSleep / Hibernate） | 先测电流，再看唤醒源 | `.../references/power-mode-patterns.md` |

**验收**：做一次"定时器触发 ADC → DMA 搬 1000 点 → 全部采完后中断里处理"，全程不轮询。

---

### 阶段四 · 综合小项目（毕业考）

| # | 项目 | 覆盖的能力 | 勾选 |
|---|---|---|---|
| 4.1 | 直流电机调速：PWM + 编码器（TCPWM QuadDec）+ ADC 电流 + 串口上位机 | 阶段一~三 全部 | [ ] |
| 4.2 | 上位机示波器：定时器触发 ADC + DMA 双缓冲 + 串口协议 | DMA + 时序 | [ ] |
| 4.3 | 用 I²C/SPI 接一个外部传感器并做定时上报 | 通信 + 定时器 | [ ] |

---

## 4. 明确"先不学"的（留到 CYT4BB7）

| 项目 | 原因 |
|---|---|
| **并口摄像头（MT9V034）** | 64 脚**没有连续 8 位端口**，两板接线方案完全不同 |
| **D-Cache / ITCM / DTCM** | CYT2BL3 的 M4 **没有**这些 |
| **双核 IPC 分工** | 本型号 CM0+ 是预编译镜像，不跑用户代码 |
| **CM0+ 配 CLK_HF1/2、释放 CM7 复位** | 单核没有这套启动链 |
| **SMIF / SDHC / I²S / ETH** | 本型号**没有**这些外设 |
| **外挂 VCCD 核心稳压器 / PMIC** | 自制板电源设计，见 `docs/CYT4BB7_自制板硬件设计指南.md` |

---

## 5. 参考资源索引

### 本工作区文档

| 内容 | 路径 |
|---|---|
| 硬件配置全流程（引脚→外设→时钟→生成→编译） | `docs/工程配置流程.md` |
| 调试配置（F5 / attach / 探针） | `docs/调试配置.md` |
| 编译烧录排障 | `docs/编译烧录排障手册.md` |
| CYT4BB7 自制板硬件 | `docs/CYT4BB7_自制板硬件设计指南.md` |
| CYT4BB7 摄像头 | `docs/CYT4BB7_摄像头开发指南.md` |

### 技能（SKILL）——建议按需加载

| 技能 | 用途 |
|---|---|
| `.github/skills/mtb-device-configurator/SKILL.md` | 配外设/引脚/时钟 |
| `.github/skills/mtb-device-configurator/references/*.md` | **硬件验证过的运行时模式**（UART/PWM/I2C/SPI/DMA/定时器/GPIO中断/低功耗） |
| `.github/skills/mtb-retarget-io/SKILL.md` | printf 输出 |
| `.github/skills/mtb-tools/SKILL.md` | 构建/烧录目标 |
| `.github/skills/mtb-debug-workflow/SKILL.md` | 抓串口、HardFault 分析 |
| `.github/skills/mtb-list-code-examples/SKILL.md` | 找官方例程 |
| `.github/skills/mtb-scb-lin-slave/SKILL.md` | LIN 从机 |

### 官方 PDL API 手册（本机离线）

```
mtb_shared/mtb-pdl-cat1/release-v3.25.0/docs/pdl_api_reference_manual/html/index.html
```

### 逐飞 CYT2BL3 例程（参考，但偏无刷驱动）

```
D:\硬件技术\cyt2_Brushlesss\CYT2BL3_Brushless_Driver_4IN1_Project-master\
  CYT2BL3_Brushless_Driver_4IN1_Project-master\Example\E07_CYT2BL3\
    E02_08_4in1_driver_uart_demo\        ← UART + 定时器
    E02_09_4in1_driver_pwm_demo\         ← PWM + 死区
```

> ⚠ 逐飞库是 **IAR 工程**（`.ewp`），不是 ModusToolbox 工程。看它的**初始化顺序和寄存器用法**有价值，但**不能直接搬进 MTB 工程**（尤其 `zf_device/zf_driver` 里对 PDL 的封装与你用的 PDL 版本可能不一致）。

---

## 6. 学习时的五条通用心法

| # | 心法 | 说明 |
|---|---|---|
| 1 | **先 DC（Device Configurator）后代码** | 引脚/时钟/外设参数尽量在 GUI 里配，代码只写 GUI 表达不了的（HSIOM、TrigMux、中断注册、运行时逻辑） |
| 2 | **Init → Enable → (TriggerStart) 三段式** | 所有 PDL 外设都是这个套路，记住一次通吃 |
| 3 | **DBG 优先于猜** | 先看 `Cy_Xxx_GetStatus()`、先量波形、先 printf，别凭感觉改代码 |
| 4 | **一次只加一个外设** | 同时加两个新外设 = 出问题无法定位。每加一个就 commit 一次 |
| 5 | **永远不手改 `GeneratedSource/`** | 改了下次生成就丢；要改就改 `design.modus` |

---

## 7. 进度一览（复制到自己的笔记里打勾）

```
阶段〇 环境      ■ 空工程(#error 无需修)   □ run_make   □ 调试器   □ DC 生成
阶段一 基础      □ LED  □ 按键  □ 时钟  □ UART+printf  □ EXTI
阶段二 定时/模拟 □ Timer □ PWM □ 死区 □ ADC单 □ ADC扫描 □ ADC电机 □ I2C主 □ I2C从 □ SPI
阶段三 联动      □ DMA M2M □ M2P □ P2M □ 定时+ADC+DMA □ GPIO触发DMA □ CAN
                 □ LIN □ SmartIO □ EVTGEN □ 低功耗
阶段四 综合      □ 电机调速  □ 示波器  □ 传感器上报
```
