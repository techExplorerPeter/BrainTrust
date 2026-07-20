# Bootloader BM/PBL 可编辑图源

本目录保存 Word 设计文档中 5 张图的可编辑 PlantUML 源文件，以及由同一图源生成的 SVG 和 PNG。

## 目录结构

- `src/*.puml`：可编辑图源。
- `src/_wf_style.iuml`：WF 统一颜色、字体和线条样式。
- `svg/*.svg`：适合插入 Word 的矢量图片。
- `png/*.png`：用于旧版 Office 或其他不支持 SVG 的工具。
- `render_diagrams.ps1`：批量重新生成 SVG 和 PNG。

## 图文件

1. `01_bm_pbl_overall_architecture`：BM + PBL 总体架构。
2. `02_function_blocks_and_boundaries`：功能块与责任边界。
3. `03_bm_boot_flow`：BM 启动选择、验证与交接流程。
4. `04_pbl_upgrade_flow`：PBL UDS 升级与 valid 提交流程。
5. `05_external_flash_memory_map`：4 MiB 外部 Flash 分区与访问边界。

## 编辑和重新生成

使用文本编辑器或 VS Code PlantUML 插件修改 `src` 中对应的 `.puml`，然后在本目录执行：

```powershell
.\render_diagrams.ps1
```

只生成一种格式：

```powershell
.\render_diagrams.ps1 -Format svg
.\render_diagrams.ps1 -Format png
```

脚本优先使用环境变量 `PLANTUML_JAR`，其次查找 VS Code PlantUML 插件附带的 `plantuml.jar`。当前机器已具备 Java、PlantUML 和 Graphviz，可离线生成。

SVG 和 PNG 在 Word 中仍作为图片使用；流程内容应在 `.puml` 中修改后重新生成。SVG 放大不失真，推荐作为 Word 中的正式插图。
