# test_cyt2

TRAVEO™ T2G **CYT2BL3CAS**（Cortex®-M4，cat1a 单核）的 ModusToolbox 应用工程。

## 硬件

| 项目 | 值 |
| --- | --- |
| MCU | CYT2BL3CAS（64-LQFP） |
| BSP | `TARGET_CYT2BL3` |
| 工具 | ModusToolbox 3.9，`TOOLCHAIN=GCC_ARM`，`CONFIG=Debug` |
| 调试串口 | P0.0 = `SCB0_UART_RX`，P0.1 = `SCB0_UART_TX` |

## 目录结构

```
test_cyt2/
├── source/                     # 应用代码（新增 .c/.h 放这里）
│   └── main.c                  # 入口：BSP 初始化 + 主循环
├── bsps/TARGET_CYT2BL3/        # BSP（勿改）
│   └── config/
│       ├── design.modus        # 器件配置（用 Device Configurator 打开）
│       └── GeneratedSource/    # 自动生成，不入库，勿手改
├── deps/                       # 直接依赖 *.mtb（版本锁在 assetlocks.json）
├── libs/                       # getlibs 生成的间接依赖，不入库
├── docs/                       # 工程文档
├── scripts/                    # flash.ps1 等脚本
└── Makefile                    # 顶层构建文件
```

## 构建

```powershell
# 完整构建
python .github/skills/mtb-tools/scripts/run_make.py --args build

# 首次拉取依赖（新增/修改 .mtb 后必须先跑）
python .github/skills/mtb-tools/scripts/run_make.py --args getlibs
```

VS Code 里也可以直接用任务：`Ctrl+Shift+B` → `Build`。

## 烧录

```powershell
python .github/skills/mtb-tools/scripts/run_make.py --args program
```

或运行任务 `Program`（调用 `scripts/flash.ps1`）。

## 开发约定

- **新增源文件**：任意放 `source/` 下的子目录即可，构建系统会递归搜索 `*.c/*.h`，头文件所在目录自动加入 include 路径，**不需要改 `Makefile` 的 `SOURCES`/`INCLUDES`**。
- **`main.c` 保持精简**（≤150 行）：只做初始化和主循环，功能按模块拆到 `source/<模块>.c/h`。
- **外设配置只能在 Device Configurator 里改**（`design.modus`），不要手写 `cy_stc_*_config_t` 或直接调 `Cy_GPIO_SetHSIOM()`。
- **`GeneratedSource/` 是生成产物**：不入库，克隆后需在 Device Configurator 里 Save & Generate。
- **HAL 用 `mtb_hal_*`**，本工程不定义 `CY_USING_HAL`，不要用 `cyhal_*`。
- 引脚紧张：CYT2BL3 64-LQFP 只有约 50 个 GPIO，加外设前先规划引脚；**P23.4/23.5/23.6 是 SWD 调试脚，不要配成 GPIO**。

## 文档

- [`docs/工程配置流程.md`](docs/工程配置流程.md) — 引脚 → 外设 → 时钟 → 生成 → 构建的完整流程
- [`.modustoolbox/docs/README.md`](.modustoolbox/docs/README.md) — 工作区与工具链说明

## 来源

基于 Infineon `mtb-example-empty-app` 模板（Apache-2.0）建立，已改为本项目结构。
