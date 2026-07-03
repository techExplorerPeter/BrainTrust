# CR60 Light BYD BM 详细设计文档

本文基于 `D_CR60_Light_BM.elf` 的静态反汇编结果整理。BM 指 Boot Manager，负责上电后的初始化、有效性标志读取、启动目标选择，以及将控制权交给 App / FBL / PBL。

分析对象：

| 项目 | 内容 |
| --- | --- |
| ELF | `D_CR60_Light_BM.elf` |
| 架构 | ARM32 little-endian |
| ELF 入口 | `0x20000` |
| 分析时间 | 2026-07-03 |

地址说明：ELF 符号表中的 Thumb 函数地址最低位会带 `1`，例如 `Boot_Logic` 显示为 `0x10204961`。本文函数地址统一写为去掉 Thumb bit 后的实际指令起始地址，例如 `0x10204960`。

## 1. 模块定位

BM 是系统上电后的启动管理模块。它本身不负责 OTA 数据接收和刷写，而是根据 NvM 中保存的状态标志决定启动哪个软件实体。

BM 管理的目标软件包括：

| index | 目标 | 镜像地址 |
| --- | --- | --- |
| 0 | App / CustApp | `0x00090000` |
| 1 | FBL | `0x00050000` |
| 2 | PBL | `0x00020000` |

其中 `0x20000 / 0x50000 / 0x90000` 是 BM 选择的镜像起始地址 / appimage 地址，不一定等于最终 CPU 的 PC。FBL / PBL 被加载后会重定位向量表到 `0x0`，再执行 `blx 0`。

## 2. 总体启动流程

BM 的主流程非常短，`main` 中先初始化，再选择并启动目标软件，之后进入死循环。

关键函数：

| 功能 | 函数 | 地址 |
| --- | --- | --- |
| 主入口 | `main` | `0x102124e6` |
| 初始化 | `BootM_Init` | `0x1020a8ac` |
| 启动目标软件 | `BootM_BootTargetSoftware` | `0x1020941c` |
| 启动选择主逻辑 | `Boot_Logic` | `0x10204960` |
| valid 判断 | `Is_FLAG_Valid` | `0x1020d94c` |
| 镜像加载 | `ImageM_LoadCpu` | `0x10208670` |
| 向量表重定位 | `BootM_RelocateVectortable` | `0x10211808` |

伪代码：

```c
int main(void)
{
    BootM_Init();
    BootM_BootTargetSoftware();

    while (1) {
    }
}
```

## 3. 初始化设计

`BootM_Init()` 的核心职责是完成启动前状态恢复和底层初始化。

反汇编确认的关键调用：

```text
BootM_Init
  -> NvM_Integration_ReadAll
  -> rbSecFls_Init_MainFunction_BM
```

设计含义：

1. BM 上电后会先从 NvM / 安全 Flash 相关区域读取启动状态。
2. App / FBL / PBL 的 valid flag 在启动选择之前已经被加载到 BM 可访问的全局变量中。
3. OTA 中途断电后的结果，最终就是由这些 valid flag 决定下次上电走向。

## 4. 启动状态变量

BM 中与启动决策相关的全局符号如下：

| 符号 | 地址 | 含义 |
| --- | --- | --- |
| `Fbl_Valid_Flag` | `0x10216f68` | FBL 有效标志 |
| `Pbl_Valid_Flag` | `0x10216f6c` | PBL 有效标志 |
| `Application_Valid_Flag` | `0x10216f9f` | App 有效标志 |
| `Reprogramming_Request_Flag` | `0x10216f74` | 重编程请求标志 |
| `StayInBootFlag` | `0x10216ab8` | 启动选择 / 停留状态 |
| `APP_IMAGE_Addr` | `0x10216abc` | App 镜像地址 |
| `CurrentBoot_Address` | `0x10216ac0` | 当前选择的启动地址 |

## 5. Valid Flag 判断规则

BM 通过 `Is_FLAG_Valid()` 判断目标是否可启动。

反汇编得到的规则：

```text
index 0: App
  Application_Valid_Flag != 0x55 认为有效

index 1: FBL
  Fbl_Valid_Flag == 0xAAAAAAAA 认为有效

index 2: PBL
  Pbl_Valid_Flag == 0xAAAAAAAA 认为有效
```

这里需要特别注意：BM 对 App 的判断不是 `Application_Valid_Flag == 0xAA`，而是 `Application_Valid_Flag != 0x55`。PBL 侧写 App valid 时使用 `0xAA` 表示有效、`0x55` 表示无效；两边逻辑可以匹配。

实现时应严格保持 BM 侧判断为 `!= 0x55`。如果将 BM 实现成 `== 0xAA`，会改变当前 ELF 的启动行为，例如 erased/default 状态值不为 `0x55` 时，原 BM 会认为 App 可尝试启动，而新实现会拒绝启动。

## 6. 普通启动选择策略

普通启动路径下，BM 按固定优先级选择目标：

```text
App -> FBL -> PBL
```

对应地址：

```text
App  index 0 -> 0x00090000
FBL  index 1 -> 0x00050000
PBL  index 2 -> 0x00020000
```

启动选择伪代码：

```c
if (Is_FLAG_Valid(APP_INDEX)) {
    CurrentBoot_Address = 0x90000;
    boot App;
} else if (Is_FLAG_Valid(FBL_INDEX)) {
    CurrentBoot_Address = 0x50000;
    boot FBL;
} else if (Is_FLAG_Valid(PBL_INDEX)) {
    CurrentBoot_Address = 0x20000;
    boot PBL;
} else {
    stay in BM;
}
```

反汇编证据：

```text
Boot_Logic:
  0x10204988: r0 = 0x20000
  0x1020498e: r0 = 0x50000
  0x102049fe: r0 = 0x90000
```

## 7. 重编程请求特殊路径

`Boot_Logic()` 会优先检查 `Reprogramming_Request_Flag`。如果该标志匹配特定 magic value，BM 会绕过普通 App 优先启动策略，优先尝试进入 FBL 或 PBL。

反汇编确认的常量：

| `Reprogramming_Request_Flag` | 启动目标 | 地址 |
| --- | --- | --- |
| `0x10021002` | FBL | `0x00050000` |
| `0x10061006` | PBL | `0x00020000` |
| `0x10861086` | PBL | `0x00020000` |
| `0x10821082` | PBL | `0x00020000` |

设计含义：

1. 诊断请求或 OTA 准备阶段可以通过该 flag 请求 BM 进入刷写相关 boot。
2. 如果 flag 指向 PBL，BM 会优先尝试 PBL `0x20000`。
3. 如果 flag 指向 FBL，BM 会优先尝试 FBL `0x50000`。
4. 该路径仍会检查对应 boot 的 valid flag，并调用 `SecBoot_Check_Process`；检查失败时会回退到后续普通启动选择逻辑。

## 8. 目标软件加载与跳转

BM 选择目标后会调用 `ImageM_LoadCpu()` 完成镜像加载。FBL / PBL 与 App 的跳转方式不同。

### 8.1 FBL / PBL 跳转方式

对 index 1 / index 2，即 FBL / PBL：

```text
ImageM_LoadCpu(...)
BootM_RelocateVectortable(0x1021e000, 0x0)
blx 0
```

设计含义：

1. BM 先把目标镜像加载到运行位置。
2. 再将向量表搬移到 `0x0`。
3. 最终通过 `blx 0` 将控制权交给目标镜像入口。

### 8.2 App 跳转方式

App 目标不走固定 `blx 0` 的方式，而是使用 `bootImageInfo` 中保存的 entry point。

```text
ImageM_LoadCpu(...)
blx bootImageInfo.entryPoint
```

## 9. OTA 中断电后的 BM 行为

BM 自身不判断 OTA 过程是否完成，它只看 valid flag。

只升级 CustApp 时，如果 PBL 已经进入擦除 / 写入阶段，PBL 会先将 `Application_Valid_Flag` 写成 `0x55`。如果此时断电，下次上电时 BM 读取到 App invalid。

下次上电流程：

```text
BootM_Init
  -> NvM_Integration_ReadAll
  -> 读取 Application_Valid_Flag / Fbl_Valid_Flag / Pbl_Valid_Flag

Boot_Logic
  -> App flag == 0x55，跳过 App 0x90000
  -> 如果 FBL valid，启动 FBL 0x50000
  -> 如果 FBL invalid 且 PBL valid，启动 PBL 0x20000
  -> 如果 FBL/PBL 都 invalid，停留在 BM / 返回错误路径
```

因此，从 BM 角度看，CustApp OTA 中途断电后的恢复策略是：

```text
优先不启动无效 App；
优先进入 FBL；
FBL 不可用时进入 PBL；
没有可用 boot 时停留在 BM。
```

## 10. 与 PBL 的接口关系

BM 与 PBL 的关键接口不是函数调用，而是持久化状态：

| 接口 | 写入方 | 读取方 | 作用 |
| --- | --- | --- | --- |
| `Application_Valid_Flag` | PBL | BM | 判断 App 是否可启动 |
| `Reprogramming_Request_Flag` | 诊断 / Boot 逻辑 / PBL | BM / PBL | 决定是否强制进入 FBL/PBL |
| `Pbl_Valid_Flag` | 制造 / 更新流程 | BM | 判断 PBL 是否可启动 |
| `Fbl_Valid_Flag` | 制造 / 更新流程 | BM | 判断 FBL 是否可启动 |

PBL 进入后会通过 `BootM_ClearReprogrammingRequestFlag()` 清除重编程请求。因此，如果 PBL 已经启动并进入 OTA，再中途断电，常见情况下下次启动不再靠 reprogramming request 强制进入 PBL，而是走 BM 的普通 valid flag 选择流程。

## 11. 设计结论

BM 的核心设计是一个基于持久化 valid flag 的启动仲裁器：

1. 上电先读取 NvM / 安全 Flash 中的启动状态。
2. 如果存在重编程请求，则优先尝试指定的 FBL 或 PBL，但仍受 valid flag 和 `SecBoot_Check_Process` 约束。
3. 普通路径按 App、FBL、PBL 的顺序选择第一个有效目标。
4. App 是否有效由 `Application_Valid_Flag != 0x55` 决定。
5. CustApp OTA 过程中断电后，只要 PBL 已经把 App flag 清为 `0x55`，BM 就不会继续启动 App。
6. 断电恢复时 BM 优先跳 FBL `0x50000`，FBL 无效才跳 PBL `0x20000`。

实现 Agent 注意事项：

1. 不要把 App valid 判断改成 `== 0xAA`；BM 的实际规则是 `!= 0x55`。
2. 重编程请求路径不是无条件跳转，仍要检查对应 boot valid flag 和 `SecBoot_Check_Process`。
3. FBL / PBL 的 `0x50000 / 0x20000` 是镜像选择地址，加载后通过向量表重定位和 `blx 0` 进入。
