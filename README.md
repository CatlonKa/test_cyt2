# test_cyt2

**22 届智能车竞赛**的测试工程，基于 TRAVEO™ T2G **CYT2BL3CAS**（Cortex®-M4，cat1a 单核）。

> 仅供个人学习验证，非正式比赛工程。完整竞赛工程另行开发。

## 硬件

| 项目 | 值 |
| --- | --- |
| MCU | CYT2BL3CAS（64-LQFP，约 50 个 GPIO） |
| BSP | `TARGET_CYT2BL3` |
| 工具 | ModusToolbox 3.9 / `GCC_ARM` / `Debug` |
| 调试串口 | P0.0 = `SCB0_UART_RX`，P0.1 = `SCB0_UART_TX` |

## 目录结构

```
test_cyt2/
├── User/                       # 应用代码（新增 .c/.h 放这里）
│   ├── main.c                  # 入口：BSP 初始化 + 主循环
│   └── config.h                # 应用级配置
├── bsps/TARGET_CYT2BL3/config/ # design.modus + GeneratedSource/（勿手改）
├── deps/                       # 直接依赖 *.mtb
├── libs/                       # getlibs 生成的间接依赖，不入库
├── docs/                       # 工程文档
├── scripts/                    # flash.ps1 等
└── Makefile                    # 顶层构建文件
```

## 构建与烧录

**全新克隆后必须先 `getlibs`**，否则 `build` 会报
`Libraries: "bsp core-make recipe-make" not found`。

`libs/` 与 `GeneratedSource/` 都被 git 忽略，但均可自动重建：
`getlibs` 依据 `bsps/TARGET_CYT2BL3/deps/*.mtbx` + `deps/assetlocks.json` 重建 `libs/`，
`build` 依据 `design.modus` 重新生成 `GeneratedSource/`。

```powershell
# 1. 仅首次、或增删 .mtb 依赖后
python .github/skills/mtb-tools/scripts/run_make.py --args getlibs

# 2. 日常循环
python .github/skills/mtb-tools/scripts/run_make.py --args build
python .github/skills/mtb-tools/scripts/run_make.py --args program
```

VS Code 任务：`Ctrl+Shift+B` 构建，`Program` 烧录。

⚠️ 烧录读取 `build/last_config/*.hex`，克隆后先 build 一次再烧。

## 版本控制

入库：`User/`、`bsps/`、`deps/`、`.vscode/`、`openocd.tcl`、`scripts/`、`design.modus`。

忽略：`libs/`、`build/`、`GeneratedSource/`、`.cache/`、`.modustoolbox/mtb_env.*`、`*.code-workspace`
—— 全部可由 `getlibs` 或工具自动重建。

## 工程约定

- **新增源文件**：放 `User/` 下任意子目录，构建系统递归搜索 `*.c/*.h` 并自动加 include 路径，**无需改 `Makefile`**。
- **`main.c` ≤150 行**：只做初始化和主循环，功能拆分到模块文件。
- **外设/时钟/引脚**：只在 Device Configurator 改 `design.modus`，不手写 `cy_stc_*_config_t`。
- **HAL 用 `mtb_hal_*`**：本工程未定义 `CY_USING_HAL`，`cyhal_*` 不可用。
- **`GeneratedSource/` 不入库**：克隆后需在 Device Configurator 里 Save & Generate。
- **P23.4/23.5/23.6 是 SWD 调试脚**，禁止配成 GPIO（会失去调试连接）。

## 文档

- [`docs/工程配置流程.md`](docs/工程配置流程.md) — 引脚 → 外设 → 时钟 → 生成 → 构建
- [`docs/编译烧录排障手册.md`](docs/编译烧录排障手册.md) — 烧录配方、探针限制、速度优化、踩坑记录

## 来源

基于 Infineon `mtb-example-empty-app` 模板（Apache-2.0）。
