# CAN FD Clock And Bit Timing Configuration

## Source Files

- MCAN clock configuration:
  `mmwave_mcuplus_sdk_04_07_00_01/ti/demo/awr2x44P/mmw_ddm/mss/mssgenerated/ti_power_clock_config.c`
- MCAN bit timing configuration:
  `mmwave_mcuplus_sdk_04_07_00_01/ti/demo/awr2x44P/mmw_ddm/mss/mssgenerated/ti_drivers_config.c`
- MSS/R5 clock definitions:
  `mcu_plus_sdk_awr2x44p_10_00_00_07/source/drivers/hw_include/awr2x44p/cslr_soc_defines.h`

## Clock Configuration

| Clock | Frequency | Notes |
| --- | ---: | --- |
| MCAN functional clock | 80 MHz | Used by MCANA and MCANB bit timing calculation |
| MSS SYS_VCLK | 200 MHz | `MSS_SYS_VCLK` |
| R5F CPU clock | 400 MHz | `R5F_CLOCK_MHZ` |

The MCAN functional clock is configured as 80 MHz for both CAN instances:

```c
{ SOC_RcmPeripheralId_MSS_MCANA, SOC_RcmPeripheralClockSource_DPLL_CORE_HSDIV0_CLKOUT2, 80000000 },
{ SOC_RcmPeripheralId_MSS_MCANB, SOC_RcmPeripheralClockSource_DPLL_CORE_HSDIV0_CLKOUT2, 80000000 },
```

## Effective CAN FD Configuration

The current CAN FD configuration is:

| Phase | Bitrate | Sample Point |
| --- | ---: | ---: |
| Arbitration phase | 500 kbit/s | 80% |
| Data phase | 2 Mbit/s | 80% |

## Bit Timing Values

The generated MCAN bit timing values are register-encoded. The effective physical value is:

```text
effective value = register value + 1
```

### Arbitration Phase

| Item | Register Value | Effective Value |
| --- | ---: | ---: |
| Prescaler | `nomRatePrescalar = 0x3` | 4 |
| TSEG1 | `nomTimeSeg1 = 0x1E` | 31 |
| TSEG2 | `nomTimeSeg2 = 0x7` | 8 |
| SJW | `nomSynchJumpWidth = 0x0` | 1 |
| BTL | `1 + TSEG1 + TSEG2` | 40 |

Calculation:

```text
Bitrate = 80 MHz / 4 / 40 = 500 kbit/s
Sample point = (1 + 31) / 40 = 80%
```

### Data Phase

| Item | Register Value | Effective Value |
| --- | ---: | ---: |
| Prescaler | `dataRatePrescalar = 0x7` | 8 |
| TSEG1 | `dataTimeSeg1 = 0x2` | 3 |
| TSEG2 | `dataTimeSeg2 = 0x0` | 1 |
| SJW | `dataSynchJumpWidth = 0x0` | 1 |
| BTL | `1 + TSEG1 + TSEG2` | 5 |

Calculation:

```text
Bitrate = 80 MHz / 8 / 5 = 2 Mbit/s
Sample point = (1 + 3) / 5 = 80%
```

## Comparison With CAN FD Tool Screenshots

The screenshots under `C:\Users\Administrator\Pictures\CANFD` show:

- Arbitration phase: 500 kbit/s, 80%, prescaler 32, BTL 5, TSEG1 3, TSEG2 1, SJW 1
- Data phase: 2 Mbit/s, 80%, prescaler 8, BTL 5, TSEG1 3, TSEG2 1, SJW 1

Current project status:

| Phase | Matches Bitrate And Sample Point | Matches Exact Bit Timing Row |
| --- | --- | --- |
| Arbitration phase | Yes | No. Current project uses prescaler 4, BTL 40, TSEG1 31, TSEG2 8, SJW 1 |
| Data phase | Yes | Yes. Current project uses prescaler 8, BTL 5, TSEG1 3, TSEG2 1, SJW 1 |

