# Kvaser ASC Capture 设计与使用说明

## 目标

`agent_kvaser_capture` 是给 agent 使用的独立 CAN FD 报文录制工具包。它负责打开 Kvaser 设备，录制雷达发送到 CAN 总线上的 Rx 报文，并保存为 Vector ASC 格式。录制过程中也可以发送 Tx 触发报文，Tx 和 Rx 会写入同一个 ASC，方便后续按时间线分析。

## 设计原则

- 独立运行：工具包内置 `can\` 依赖，不要求从 FlexFlowFlash 工程目录启动。
- 可控停止：agent 不需要按 `Ctrl+C`，通过 stop file 让录制进程自己收尾。
- 可追踪输出：ready JSON 记录 pid、ASC 输出路径、stop file 路径。
- 自动化稳定：默认建议关闭逐帧打印，周期 flush，避免长时间运行时 stdout 堵塞或数据未及时落盘。

## 路径行为

使用 `capture.bat` 和 `stop_capture.bat` 时，可以从任意工作目录调用。以下相对路径都会按 `agent_kvaser_capture` 目录解析：

- `logs\*.asc`
- `logs\*.ready.json`
- `logs\*.stop`
- `configs.example.ini`

因此 agent 不需要 `cd` 到工具包目录。

## 开始录制

推荐命令：

```powershell
D:\path\to\agent_kvaser_capture\capture.bat --fd --channel 0 --bitrate 500000 --data-bitrate 2000000 --test-name "case01" --output-dir logs --ready-file logs\case01.ready.json --stop-file logs\case01.stop --print-every 0 --timeout 0.2
```

启动成功后会看到：

```text
Recording Kvaser CAN FD: channel=0, fd=True, bitrate=500000, data_bitrate=2000000, output=...\logs\case01_YYYYMMDD_HHMMSS.asc
Ready file: ...\logs\case01.ready.json
Stop condition: Ctrl+C or create stop file: ...\logs\case01.stop.
```

## 停止录制并保存

推荐命令：

```powershell
D:\path\to\agent_kvaser_capture\stop_capture.bat --ready-file logs\case01.ready.json --wait 10
```

成功输出示例：

```text
Stop requested: ...\logs\case01.stop
Capture output: ...\logs\case01_YYYYMMDD_HHMMSS.asc
Capture stopped and stop file was cleaned up.
```

`--wait 10` 表示最多等待 10 秒确认录制进程完成清理。返回码为 `0` 时，ASC 文件已经关闭，可以进入分析阶段。

## Ready JSON 格式

ready 文件内容示例：

```json
{
  "pid": 12345,
  "output": "D:\\path\\to\\agent_kvaser_capture\\logs\\case01_20260708_093000.asc",
  "stop_file": "D:\\path\\to\\agent_kvaser_capture\\logs\\case01.stop",
  "started_at": "2026-07-08T09:30:00"
}
```

agent 应读取 `output` 获取本次 ASC 路径，读取 `stop_file` 或直接调用 `stop_capture.bat` 停止录制。

## 发送触发报文

Tx 显式格式：

```text
--tx CAN_ID,can|canfd,LEN,DATA[,brs|no-brs]
```

示例：录制同时发送一帧 CAN FD 触发报文：

```powershell
D:\path\to\agent_kvaser_capture\capture.bat --fd --channel 0 --bitrate 500000 --data-bitrate 2000000 --test-name "tx_case01" --output-dir logs --ready-file logs\tx_case01.ready.json --stop-file logs\tx_case01.stop --tx "0x123,canfd,64,01020304,brs" --print-every 0 --timeout 0.2
```

周期发送示例，每 1 秒发送一次，共 10 次：

```powershell
D:\path\to\agent_kvaser_capture\capture.bat --fd --channel 0 --bitrate 500000 --data-bitrate 2000000 --tx "0x123,canfd,64,01020304,brs" --tx-period 1 --tx-count 10
```

Tx 会写入同一个 ASC 文件，方向为 Tx。

## Agent 自动化流程

1. 生成唯一测试名，例如 `radar_powercycle_case01`。
2. 启动 `capture.bat`，传入唯一 ready/stop 文件名。
3. 等待 ready JSON 出现。
4. 执行测试动作，例如烧录、重启雷达、发送触发帧。
5. 调用 `stop_capture.bat --ready-file <ready.json> --wait 10`。
6. 确认 stop 返回码为 `0`。
7. 读取 ready JSON 的 `output`，分析 ASC。

## 稳定性建议

24 小时自动化推荐参数：

```text
--print-every 0 --timeout 0.2 --flush-every 100 --flush-period 5
```

如果担心单个 ASC 文件过大，可以增加：

```text
--max-file-size 524288000
```

`--fsync` 会在 flush 后强制落盘，抗异常断电更强，但会降低吞吐，只在确实需要时启用。

## 常见问题

- ready 文件不存在：录制命令没有传 `--ready-file`，或录制进程还没有启动成功。
- stop 无法停止：录制命令没有传 `--stop-file`，ready JSON 中没有 stop 文件路径。
- 控制台打印 RX：这是 `--print-every` 控制的正常行为；关闭打印使用 `--print-every 0`。
- ASC 只有 ErrorFrame 或没有报文：优先确认使用 `--fd --channel 0 --bitrate 500000 --data-bitrate 2000000`。
- 多行命令失败：PowerShell 换行必须用反引号；CMD 建议使用一整行命令。
