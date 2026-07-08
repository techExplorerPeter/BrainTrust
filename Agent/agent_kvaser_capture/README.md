# Standalone Kvaser Capture Kit

本目录是已测试通过的独立 Kvaser CAN FD 录制工具包。它可以从 FlexFlowFlash 工程中剥离出来使用，agent 只需要持有整个 `agent_kvaser_capture` 文件夹，不需要再依赖工程根目录。

## 目录内容

- `capture_kvaser_asc.py`：录制 Kvaser CAN/CAN FD 报文到 ASC，可选发送 Tx。
- `stop_kvaser_capture.py`：通过 ready JSON 或 stop file 优雅停止录制。
- `capture.bat`：从任意工作目录启动录制的 Windows 包装器。
- `stop_capture.bat`：从任意工作目录停止录制的 Windows 包装器。
- `can\`：随包携带的 python-can/Kvaser 后端依赖。
- `logs\`：默认输出目录。
- `configs.example.ini`：可选配置模板。
- `DESIGN_AND_USAGE.md`：完整设计与使用说明。

## 环境要求

- Windows。
- Python 可通过 `python` 命令启动。
- 已安装 Kvaser Driver/CANlib。
- Kvaser 设备可被系统识别。

当前已验证雷达配置：

```text
channel = 0
mode = CAN FD
bitrate = 500000
data_bitrate = 2000000
sample point = 80% by Kvaser predefined CAN FD bitrate
```

## 启动录制

从任意目录调用：

```powershell
D:\path\to\agent_kvaser_capture\capture.bat --fd --channel 0 --bitrate 500000 --data-bitrate 2000000 --test-name "case01" --output-dir logs --ready-file logs\case01.ready.json --stop-file logs\case01.stop --print-every 0 --timeout 0.2
```

`logs\case01.ready.json` 会记录本次 ASC 路径和 stop file 路径。相对路径会按 `agent_kvaser_capture` 目录解析。

## 停止并保存

从任意目录调用：

```powershell
D:\path\to\agent_kvaser_capture\stop_capture.bat --ready-file logs\case01.ready.json --wait 10
```

返回码为 `0` 时，录制脚本已经写入结束 marker、flush ASC、关闭 Kvaser bus，并清理 stop file。agent 此时可以读取 ready JSON 中的 `output` 字段并分析 ASC。

## Agent 推荐流程

1. 为每个测试生成唯一 `test-name`，例如 `radar_powercycle_case01`。
2. 启动 `capture.bat`，同时传入 `--ready-file` 和 `--stop-file`。
3. 等待 ready JSON 出现。
4. 执行测试动作，例如重启雷达、烧录、触发报文。
5. 调用 `stop_capture.bat --ready-file <ready.json> --wait 10`。
6. stop 返回 `0` 后，分析 ready JSON 中的 ASC 文件。

更多参数、Tx 发送格式和排错说明见 [DESIGN_AND_USAGE.md](DESIGN_AND_USAGE.md)。
