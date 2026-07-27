# AWR2x44P GPADC - VBAT、MR1、MR2电路与读数复核

## 1. 复核范围与结论

本报告复核以下内容：

- `VBAT_ADC`、`MR1_ADC`、`MR2_ADC`的原理图连接和ADC通道映射；
- MR外部引脚配置为浮空或接地时的电压和GPADC结果；
- `GPADC_startSingleChannelConversion()`返回值是否需要除以255；
- 14.5 V板端电源与`VBAT_ADC`读数的转换关系；
- ADC1、ADC5、ADC6在当前仓库中的实际SysConfig配置；
- 读数61464是否有效。

主要结论：

1. MR1和MR2的检测电路完全对称，外部引脚可以通过“浮空/接地”编码状态。
2. MR浮空时读到800左右、接地时读到100多，符合该电路的工作原理。
3. 当前CAN版本生成配置中，MR1对应ADC5，MR2对应ADC6，两路均为非缓冲模式，适用0～1.8 V、10 bit换算。
4. `GPADC_startSingleChannelConversion()`返回的是255次采样的整数平均值`Avg`，不能再除以255。
5. 61464不是有效的10 bit GPADC平均值。只有明确读取硬件`Sum`时才可能出现大于1023的数。
6. VBAT的理想换算系数约为23.6246，但该系数得到的是`VIN_Q`，不是连接器上的`PWR_IN`。最新实测16 V对应raw=365、8.8 V对应raw=191，两点标定得到`PWR_IN ≈ raw × 0.0413793 + 0.8966 V`，14.5 V预计raw约329。
7. 当前仓库中的ADC1配置并没有和ADC5、ADC6相同：ADC1为缓冲模式且`useLuTable=FALSE`，ADC5/6为非缓冲模式且`useLuTable=TRUE`。对于本SDK中的外部ADC通道，ADC1当前配置存在明确风险。

## 2. 资料与版本限制

工作区中实际存在的原理图是：

- `rcu63ha09.pdf`

工作区中没有找到名为`rcu64ha09`的原理图。因此，本报告中的电阻、二极管、测试点和网络名称均基于`RCU63HA09`。

如果`RCU64HA09`是另一个硬件版本，必须在拿到该图纸后重新做版本差异检查，不能默认两个版本完全相同。

原理图相关页：

- PDF第12页：MR1、MR2输入检测电路；
- PDF第13页：VBAT分压及开关电路；
- PDF第14页：连接器MR1、MR2引脚和保护电路；
- PDF第17页：`PWR_IN`经DS1200生成`VIN_KL15`；
- 芯片连接页及`VBAT.png`：`VBAT_ADC -> ADC1`、`MR1_ADC -> ADC5`、`MR2_ADC -> ADC6`。

## 3. GPADC基础换算和API返回值

### 3.1 ADC规格

AWR2x44P GPADC为10 bit SAR ADC：

- 非缓冲模式输入范围：0～1.8 V；
- 缓冲模式线性输入范围：0.4～1.3 V；
- 超出0.4～1.3 V后，缓冲器输出可能进入非线性区；
- ADC典型输入漏电流：3 uA；
- 分辨率：10 bit。

TI SDK示例使用1024作为10 bit换算分母：

```text
VADC = raw × 1.8 / 1024
raw  = VADC / 1.8 × 1024
```

因此，非缓冲模式下每个码对应：

```text
1 LSB = 1.8 / 1024
      = 1.7578125 mV
```

### 3.2 `GPADC_startSingleChannelConversion()`返回的是平均值

外部通道查找表配置为采集255个样本：

```c
CollectSamples = 255U
```

驱动处理过程是：

```c
sumReg = GPADC硬件累加结果;
gpAdcResult->Sum = sumReg;
gpAdcResult->Avg = sumReg / numSamples;
*gpadcValue = gpAdcResult.Avg;
```

对应源码：

- `mcu_plus_sdk_awr2x44p_10_00_00_07/source/drivers/gpadc/v0/soc/awr2x44p/gpadc_soc.c`
- `mcu_plus_sdk_awr2x44p_10_00_00_07/source/drivers/gpadc/v0/gpadc.c`

所以：

```text
GPADC_startSingleChannelConversion()输出 = 255次采样的平均值
```

该输出正常范围应为0～1023，不能再除以255。

如果直接读取的是硬件`Sum`，或者读取`GPADC_ResultType.Sum`，才需要除以采样数。必须区分`Avg`和`Sum`。

## 4. MR1和MR2电路复核

### 4.1 通道和代码映射

硬件映射：

| 信号 | 芯片ADC通道 | 当前代码变量 |
|---|---:|---|
| MR1_ADC | ADC5 | `gpadc_result[1]` |
| MR2_ADC | ADC6 | `gpadc_result[0]` |

代码：

```c
GPADC_startSingleChannelConversion(
    GPADC_MEAS_EXT_CH6, &gpadc_result[0]); /* MR2 */

GPADC_startSingleChannelConversion(
    GPADC_MEAS_EXT_CH5, &gpadc_result[1]); /* MR1 */
```

### 4.2 两路电路完全对称

MR1主要器件：

- R600：5.1 kΩ，上拉至3V3_VIO；
- R602：20 kΩ；
- R606：20 kΩ，下拉至GND；
- R604：10 kΩ，串联至ADC5；
- DS600：BAS316-Q，阳极在内部`MR1_IN`，阴极连接外部`MR1_I`。

MR2对应器件：

- R601：5.1 kΩ，上拉至3V3_VIO；
- R603：20 kΩ；
- R607：20 kΩ，下拉至GND；
- R605：10 kΩ，串联至ADC6；
- DS601：BAS316-Q，阳极在内部`MR2_IN`，阴极连接外部`MR2_I`。

连接器侧：

- MR1经过R901（0 Ω）连接到检测电路；
- MR2经过R900（0 Ω）连接到检测电路；
- C900、C901、RNTC900、RNTC905等标记为`Do Not Stuff`，正常装配时不影响直流状态；
- DTVS902用于外部接口保护。

因此，MR1和MR2可以互换使用相同的“浮空/接地”计算，区别仅在ADC通道和软件含义。

### 4.3 外部引脚浮空

外部MR引脚浮空时，BAS316没有形成外部直流回路。忽略ADC输入漏电，内部电路等效为：

```text
3.3 V -- 5.1 kΩ -- 20 kΩ -- ADC节点 -- 20 kΩ -- GND
```

`MRx_IN`节点电压：

```text
VMRx_IN = 3.3 × (20 kΩ + 20 kΩ)
          / (5.1 kΩ + 20 kΩ + 20 kΩ)
        ≈ 2.927 V
```

ADC前分压节点：

```text
VADC_ideal = 3.3 × 20 kΩ
             / (5.1 kΩ + 20 kΩ + 20 kΩ)
           ≈ 1.463 V
```

非缓冲模式理想码值：

```text
raw_ideal = 1.463 / 1.8 × 1024
          ≈ 833
```

考虑ADC典型输入漏电后，10 kΩ串联电阻和前级等效阻抗会产生额外压降。按3～5 uA估算，码值可能下降到约770～800。

因此：

```text
MR浮空读到800左右是正确、合理的结果。
```

例如，raw=826对应ADC引脚电压：

```text
VADC = 826 × 1.8 / 1024
     ≈ 1.452 V
```

这与浮空理论值1.463 V非常接近。

### 4.4 外部引脚接地

外部MR引脚接地时，BAS316正向导通：

```text
内部MRx_IN -> BAS316 -> 外部GND
```

因此`MRx_IN`不会直接等于0 V，而是被钳位在二极管正向压降附近。

BAS316在约0.5 mA电流附近的正向压降通常在约0.55～0.7 V范围。ADC前的两个20 kΩ电阻近似1:1分压：

```text
VADC_ideal ≈ VF / 2
           ≈ 0.275～0.35 V
```

忽略输入漏电时：

```text
raw_ideal ≈ 156～200
```

考虑ADC输入漏电以及ADC前10 kΩ串联电阻，实际电压还可能降低约0.06～0.10 V，因此实际码值可以下降到约100～170。

所以：

```text
MR接地时读到100多是合理的。
MR接地不应被预期为ADC读数0。
```

前面对话中给出的“MR2约160～215”只是未考虑ADC输入漏电的理想估算。更完整、合理的工程预期是约100～200，具体值随温度、二极管压降、3.3 V电源、ADC漏电和元件误差变化。

### 4.5 MR判定阈值

当前代码使用：

```c
#define RAISE_EDGE 400U
```

对应ADC引脚电压：

```text
Vthreshold = 400 × 1.8 / 1024
           ≈ 0.703 V
```

典型状态：

| MR外部状态 | 典型码值 | 与400比较 |
|---|---:|---|
| 浮空 | 约770～833 | 高于400 |
| 接地 | 约100～200 | 低于400 |

两种状态之间余量较大，400作为逻辑识别阈值是合理的。

若ICD规定：

- MR1浮空；
- MR2接地；

则预期结果就是：

```text
MR1 / ADC5：800左右，高于400
MR2 / ADC6：100多，低于400
```

这与当前实测一致。

## 5. VBAT输入电路复核

### 5.1 完整信号路径

板端电源检测路径为：

```text
PWR_IN
  -> DS1200（BAS21-Q）
  -> VIN_KL15
  -> Q701高边开关
  -> VIN_Q
  -> R701 / R702分压
  -> VBAT_ADC_BUFF
  -> R707
  -> VBAT_ADC_O
  -> 芯片ADC1
```

其中：

- DS1200：BAS21-Q串联二极管；
- Q701：PUMD2-Q内部PNP/NPN组合形成受`SWITCH_CTL`控制的高边开关；
- R700：`Do Not Stuff`，不构成VIN_KL15到VIN_Q的直连旁路；
- R701：68.1 kΩ；
- R702：3.01 kΩ；
- R707：10 kΩ；
- C203：0.1 uF，从ADC1输入到GND，用于滤波，不是电阻；
- `VBAT_ADC_O`连接芯片ADC1。

只有Q701打开时，VIN_Q和VBAT检测结果才有效。

### 5.2 分压关系

忽略ADC输入漏电和R707上的直流压降：

```text
VBAT_ADC_BUFF = VIN_Q × R702 / (R701 + R702)
```

代入电阻值：

```text
分压比 α = 3.01 / (68.1 + 3.01)
         ≈ 0.0423288

反向倍率 K = 1 / α
           = (68.1 + 3.01) / 3.01
           ≈ 23.6246
```

因此：

```text
VIN_Q = VADC × 23.6246
```

结合10 bit ADC：

```text
VADC  = raw × 1.8 / 1024

VIN_Q = raw × 1.8 / 1024 × 23.6246
      ≈ raw × 0.0415276 V
```

也就是：

```text
VBAT检测每个ADC码约对应VIN_Q的41.53 mV。
```

### 5.3 14.5 V对应多少ADC值

必须区分`VIN_Q=14.5 V`和连接器`PWR_IN=14.5 V`。

如果直接测得：

```text
VIN_Q = 14.5 V
```

那么：

```text
VADC = 14.5 / 23.6246
     ≈ 0.6138 V

raw  = 0.6138 / 1.8 × 1024
     ≈ 349
```

所以349只对应`VIN_Q`约14.5 V。

如果连接器输入是：

```text
PWR_IN = 14.5 V
```

则：

```text
VIN_Q ≈ PWR_IN - VF(DS1200) - VCE(Q701)
```

因此VIN_Q必然低于PWR_IN，实际ADC值也应低于349。由于DS1200压降随电流和温度变化、Q701也有导通压降，不能只凭原理图给出唯一精确值；工程上应直接测量TP703/TP704处的VIN_Q并进行标定。

板端电压的更完整表达式为：

```text
PWR_IN ≈ raw × 1.8 / 1024 × 23.6246
         + VF(DS1200)
         + VCE(Q701)
         + ADC漏电误差修正
```

根据最新两点实测标定，14.5 V板端输入预计raw约为329，详见下一节。

### 5.4 最新实测数据和两点标定

最新实测结果（记录日期：2026-07-27）：

| PWR_IN实测电压 | ADC1平均值raw | ADC1引脚换算电压 | 按理想分压反算VIN_Q |
|---:|---:|---:|---:|
| 16.0 V | 365 | 0.6416 V | 15.1576 V |
| 8.8 V | 191 | 0.3357 V | 7.9318 V |

ADC引脚电压按下式计算：

```text
VADC = raw × 1.8 / 1024
```

`VIN_Q`按理想电阻倍率反算：

```text
VIN_Q = raw × 0.0415276 V
```

由此得到从`PWR_IN`到`VIN_Q`的综合压降：

```text
16.0 V测试点：
ΔVfront = 16.0 - 365 × 0.0415276
        ≈ 0.8424 V

8.8 V测试点：
ΔVfront = 8.8 - 191 × 0.0415276
        ≈ 0.8682 V
```

两个测试点得到的综合压降只相差约26 mV，平均约为：

```text
ΔVfront_avg ≈ 0.8553 V
```

这说明：

1. R701/R702分压倍率分析正确；
2. 实际误差主要表现为近似固定的前级偏移；
3. 该偏移包含DS1200正向压降、Q701导通压降、ADC漏电及元件误差的综合效果；
4. 两点之间的线性关系很好。

直接对两个实测点做线性标定：

```text
斜率 A = (16.0 - 8.8) / (365 - 191)
       ≈ 0.0413793 V/count

截距 B = 16.0 - 365 × A
       ≈ 0.8966 V
```

因此，在当前测试板、当前硬件和相近温度下，建议使用：

```text
PWR_IN(V) ≈ raw × 0.0413793 + 0.8966
```

反向换算为：

```text
raw ≈ (PWR_IN - 0.8966) / 0.0413793
```

14.5 V对应：

```text
raw ≈ (14.5 - 0.8966) / 0.0413793
    ≈ 328.75
```

即实际应读到约：

```text
raw ≈ 329
```

用原理图理论斜率和平均前级压降计算：

```text
raw ≈ (14.5 - 0.8553) / 0.0415276
    ≈ 328.57
```

同样得到约329，说明理论电路模型与实测数据吻合。

标定公式当前只由8.8 V和16 V两个点得到，推荐适用范围暂限定为8.8～16 V。若要覆盖汽车电源完整工作范围和温度范围，至少还应增加低压、中间电压、高压以及高低温测试点，再决定使用一次线性标定还是分段标定。

还需要注意：

- raw=191对应ADC引脚约0.336 V；
- 如果测试固件中的ADC1仍为缓冲模式，该电压低于缓冲模式0.4 V的线性范围下限；
- 如果ADC1已经按ADC5/6改成非缓冲模式，则0.336 V处于0～1.8 V有效范围内，当前两点标定更可信；
- 因此应确认实际测试镜像的最终生成配置，而不能只根据测试结果推断配置已经生效。

### 5.5 ADC输入漏电造成的VBAT误差

VBAT分压网络在ADC侧的戴维南等效阻抗约为：

```text
RTH = R707 + (R701 || R702)
    ≈ 10 kΩ + 2.883 kΩ
    ≈ 12.883 kΩ
```

若ADC输入漏电流按典型3 uA估算：

```text
ΔVADC ≈ 3 uA × 12.883 kΩ
      ≈ 38.6 mV
```

该误差折算到VIN_Q约为：

```text
ΔVIN_Q ≈ 38.6 mV × 23.6246
       ≈ 0.91 V
```

漏电方向、温度和器件差异都会影响误差。最新两点实测已经把漏电、DS1200和Q701压降的综合影响包含在约0.8966 V的标定截距中；如果VBAT需要作为跨板卡、跨温度的精确电压量，仍应采用多板、多温度、多点标定，不能只使用单块板的理想电阻倍率或两点结果。

## 6. 当前仓库中的GPADC配置

### 6.1 CAN版本`mss.syscfg`及当前生成代码

当前生成文件：

```text
mmwave_mcuplus_sdk_04_07_00_01/ti/demo/awr2x44P/mmw_ddm/
mss/mssgenerated/ti_drivers_open_close.c
```

关键配置是：

| 通道 | 用途 | isBufferedMode | useLuTable |
|---|---|---|---|
| ADC1 | VBAT | TRUE | FALSE |
| ADC5 | MR1 | FALSE | TRUE |
| ADC6 | MR2 | FALSE | TRUE |

因此，当前仓库的ADC1配置并没有和ADC5、ADC6相同。

ADC5/6为非缓冲模式且使用外部通道LUT，配置合理。外部通道LUT为每次转换配置255个采样。

### 6.2 ADC1当前配置风险

在本工作区的GPADC驱动源码中，`useLuTable=FALSE`分支实际使用：

```c
GPADC_TempSensConfigParamTab
```

即内部温度传感器配置表，而不是外部ADC通道查找表。当前生成的ADC1配置又没有提供有效的自定义采样参数。

因此，对于外部VBAT_ADC通道，当前ADC1的：

```text
isBufferedMode = TRUE
useLuTable     = FALSE
```

不是与ADC5/6相同的可靠配置，可能选择错误的内部MUX/配置值。

如果目标是让ADC1与ADC5/6使用相同的外部通道采样方式，应在对应构建版本中明确配置为：

```text
isBufferedMode = FALSE
useLuTable     = TRUE
```

然后重新生成SysConfig代码、完整清理并重新编译。不能只修改生成文件，因为下一次SysConfig生成会覆盖。

注意：`mss_enet.syscfg`与`mss.syscfg`的GPADC配置不同，CAN和Ethernet版本需要分别检查，不能假设其中一个配置会自动同步到另一个。

当前`mss_enet.syscfg`把ADC1、ADC5、ADC6都显式配置成：

```text
isBufferedMode = TRUE
useLuTable     = FALSE
```

这虽然表面上满足“三个通道配置相同”，但结合本SDK驱动中`useLuTable=FALSE`分支的实际实现，仍不适合作为外部ADC通道的可靠配置。CAN和Ethernet两个SysConfig文件都应分别修正，编译后还应检查最终生成的`ti_drivers_open_close.c`，而不是只检查SysConfig界面。

## 7. 为什么61464不正确

10 bit GPADC平均值的有效范围是：

```text
0～1023
```

61464十六进制为：

```text
0xF018
```

它不可能代表正常的10 bit平均ADC码。

若错误地按有效平均值换算：

```text
VADC = 61464 × 1.8 / 1024
     ≈ 108.0 V
```

显然不符合ADC输入范围。

61464虽然可能落在“255次采样累加和”的数值量级内，但当前API明确把`Avg`写入调用者的`uint16_t`变量，而不是写`Sum`。所以不能用：

```text
61464 / 255
```

来解释`GPADC_startSingleChannelConversion()`的正常返回值。

出现61464时，应优先检查：

1. 是否确实查看了传给API的`uint16_t`变量，而不是硬件SUM寄存器或其他结构字段；
2. `GPADC_startSingleChannelConversion()`返回状态是否为`GPADC_CONV_DONE`；
3. ADC1是否配置为外部通道、非缓冲模式并使用LUT；
4. 当前烧录镜像是否由当前源码和当前生成配置完整重编译；
5. 头文件、驱动库和链接对象是否来自同一SDK版本；
6. 日志格式是否正确，例如使用无符号格式输出`uint16_t`；
7. 变量附近是否发生栈越界或内存覆盖。

建议在应用层增加基本有效性检查：

```c
uint16_t raw = 0U;
GPADC_ConvResultType status;

status = GPADC_startSingleChannelConversion(
             GPADC_MEAS_EXT_CH1, &raw);

if ((status != GPADC_CONV_DONE) || (raw > 1023U))
{
    /* 配置、构建或内存异常，禁止继续做电压换算 */
}
```

## 8. 推荐实板验证点

### 8.1 MR1浮空

建议测量：

- TP602：`MR1_IN`，预计约2.9 V；
- TP604：`MR1_PREADC`，预计约1.46 V；
- ADC5输入：预计接近1.4～1.46 V；
- GPADC：预计约770～833。

### 8.2 MR2接地

建议测量：

- TP603：`MR2_IN`，预计为BAS316正向压降附近；
- TP605：`MR2_PREADC`，预计约0.28～0.35 V，考虑漏电后ADC脚可能更低；
- GPADC：预计约100～200。

### 8.3 VBAT

在`PWR_IN=14.5 V`、Q701打开时，同时测量：

- TP1200：PWR_IN；
- TP1211：VIN_KL15；
- TP703或TP704：VIN_Q；
- TP705或ADC1脚：VBAT_ADC；
- GPADC1原始平均值和API返回状态。

先验证：

```text
VADC ≈ VIN_Q × 3.01 / 71.11
```

再验证：

```text
raw ≈ VADC / 1.8 × 1024
```

这样可以把问题定位到：

- DS1200/Q701前级压降；
- 电阻分压及ADC漏电；
- GPADC配置；
- 软件读取或内存问题。

## 9. 最终判定

| 项目 | 最终判定 |
|---|---|
| MR1/MR2是否可由外部配置浮空或接地 | 是 |
| MR1/MR2电路是否对称 | 是 |
| MR1浮空读800多是否合理 | 合理 |
| MR2接地读100多是否合理 | 合理 |
| MR接地是否应读0 | 否，BAS316压降和分压使其非零 |
| 阈值400是否能区分浮空/接地 | 典型条件下合理，余量较大 |
| API返回值是否需要除以255 | 不需要，返回的是平均值 |
| 61464是否是有效GPADC平均值 | 不是 |
| 14.5 V是否直接对应349 | 只有VIN_Q=14.5 V时成立；按最新PWR_IN实测标定，14.5 V约对应raw=329 |
| 16 V对应raw=365是否合理 | 合理，反算前级综合压降约0.842 V |
| 8.8 V对应raw=191是否合理 | 合理，反算前级综合压降约0.868 V；但若ADC1仍为缓冲模式则低于0.4 V线性下限 |
| 当前ADC1是否和ADC5/6配置相同 | 不相同 |
| 当前ADC1配置是否适合直接用于VBAT外部通道 | 存在明显风险，应改成外部通道LUT配置并重新生成、编译 |

## 10. 参考资料

- TI AWR2944P/AWR2E44P数据手册，GPADC参数章节：  
  <https://www.ti.com/lit/ds/symlink/awr2944p.pdf>
- Nexperia BAS316-Q数据手册：  
  <https://assets.nexperia.com/documents/data-sheet/BAS316-Q.pdf>
- Nexperia BAS21-Q数据手册：  
  <https://assets.nexperia.com/documents/data-sheet/BAS21-Q.pdf>
- Nexperia PUMD2-Q数据手册：  
  <https://assets.nexperia.com/documents/data-sheet/PUMD2-Q.pdf>
- 项目原理图：`rcu63ha09.pdf`
- TI GPADC驱动源码：  
  `mcu_plus_sdk_awr2x44p_10_00_00_07/source/drivers/gpadc/v0/`
