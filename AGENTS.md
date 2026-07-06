# AGENTS.md — coding agent 复现与改造指南

本文件面向在这个仓库里干活的 coding agent（Claude Code / Codex 等）。
人类向导览请看 README.md；这里只讲不变量、地图和常见任务的正确做法。

## 仓库地图

```
firmware/            ESPHome 设备配置（bw = Waveshare 7.5v2, e6 = GDEP073E01）
fonts/               渲染字体（Doto 点阵数字 / Space Mono / Noto Sans+Serif SC / Cormorant）
renderer/
  config.py          env、HA ENTITIES 实体表、天气映射、路径 —— 换环境先改这里
  panels.py          面板抽象：BWPanel / E6Panel（量化、抖动、导出、preview）
  draw.py            Canvas：语义色 + 最终像素坐标的绘图原语（tile/pill/ring/dotsicon/hatch/wrap…）
  datasources.py     HA REST states、天气摘要、FreshRSS 新闻（全部优雅降级）
  imagesource.py     照片源 bing/nas/picsum/ai → (PIL RGB, 标题提示)
  ai.py              claude/codex CLI 封装：text/caption_image/generate_image + 文件缓存
  styles/            每个风格一个模块：render(panel, ctx) -> PIL.Image (800×480 RGB)
  render.py          CLI 单帧渲染；rotate.py cron 轮换入口；deploy.py SSH 推送到 HA
config/crontab.example
out/                 渲染产物 + AI 缓存（gitignored）
```

## 必守不变量

1. **风格代码只用语义色**（"black"/"white"/"red"/"green"/"blue"/"yellow" 字符串），
   不要写裸 RGB。黑白面板把彩色全部折叠成黑 —— 在深色底上用彩色高亮时必须
   `panel.is_color` 分支（见 gallery.py 的处理），否则黑白屏上会隐形。
2. **E6 设备图必须是六个纯 INK 色**。`E6Panel.export()` 逐像素镜像 ESPHome
   `epaper_spi color_to_hex()`（灰差阈值 50 + 原色角点测试）。改调色板前先确认新 RGB
   落进正确的颜色桶。preview PNG 用 PANEL_RGB（面板真实暗淡观感），给人看的一律看 preview。
3. **预抖动图像和像素字体都只能落在 ss=1 画布**（`Canvas.paste`/`pixel` 有断言）。
   两个面板 default_ss 均为 1（Doto 点阵与像素中文都要求像素对齐；超采样+降采样正是
   之前中文发虚的原因），除非某风格完全不用像素字体且确有曲线平滑需求，才显式传 ss=2。
4. **黑白面板的反色**：TRMNL 固件显示时会把 PNG 反色，`EINK_INVERT=1` 让 export 预反色抵消。
   不要在风格层自己反色。
5. **AI 调用必须缓存 + 降级**：走 `ai.try_cached_text()` 或自建内容哈希缓存（gallery 示例）；
   任何 AI/网络失败不允许让渲染崩溃 —— 屏幕内容永远要能退到无 AI 版本。
6. **风格函数不允许抛异常导致空帧**：照片类风格失败回退 `nothing.render(panel, ctx)`；
   rotate.py 还有最后一道 nothing 兜底。
7. E6 全刷 ~18 秒且损耗面板：固件 `interval` 不要低于 10min。
8. 自动化/实体等标识符一律 ASCII slug；HA 侧规范沿用主仓 `/root/ha/.claude/CLAUDE.md`。

## 常见任务

**换到新家庭 / 新 HA**：改 `.env`（HA_URL/HA_TOKEN/HA_SSH_*）+ `config.py` 的 `ENTITIES`。
缺失实体自动显示 `--`，可以先跑起来再逐个补。

**表达灰度**：照片抖动模式 `EINK_DITHER=fs|bayer|bluenoise`（panels.py `_threshold_map`，
蓝噪声纹理是 `tools/gen_bluenoise.py` 预生成的 `renderer/assets/bluenoise64.png`）；
UI 区块的"灰色"用 `c.hatch(x,y,w,h, style=diag|cross|lines|dots, spacing=密度)` 排线，
不要试图画真灰色（会被量化成纯黑/白）。

**加一种风格**：
```python
# renderer/styles/mystyle.py
def render(panel, ctx):           # ctx: .now .states .news
    c = Canvas(panel)             # 照片风格改 Canvas(panel, ss=1)
    ...
    return c.finish()
```
注册进 `styles/__init__.py` 的 `STYLES`，然后
`python -m renderer.render --panel e6 --style mystyle`，用 Read 工具看 `out/*_preview.png`
自查两种面板的效果（黑白也要跑一遍，检查隐形元素）。

**加新面板硬件**：`panels.py` 里新建 Panel 子类（`color/prepare_photo/export` +
`remote_png/default_ss/is_color`），注册进 `PANELS`；固件仿照 `firmware/*.yaml`
（`online_image` 拉 `/local/eink/<remote_png>` + interval 刷新）。

**调 AI 输出**：prompt 在各风格模块（`poster._daily_line` / `journal._brief` /
`gallery._caption`）。改完删掉 `out/cache/` 对应当日文件再渲染，否则命中缓存看不到变化。
claude 后端必须用 `--output-format json` 取 `.result`（裸 stdout 会混入噪音行，已封装在
`ai._claude`）。

**测试命令**（渲染依赖真实 HA，token 在 `.env`）：
```bash
cd /root/epaper-dashboard && set -a && . ./.env && set +a
.venv/bin/python -m renderer.render --panel bw --style nothing   # 快速冒烟
.venv/bin/python -m renderer.rotate --panel e6 --no-deploy      # 轮换逻辑
.venv/bin/python -m renderer.render --panel e6 --style journal --deploy  # 真机上屏
```
上屏后无需等待：屏端每 10 分钟自拉。渲染结果自查一律看 `_preview.png` 而不是设备图
（bw 设备图是反色的，e6 设备图是饱和纯色的）。

## 已知坑

- **中文正文用加粗平滑字体，标题/标签用像素字体**：正文（新闻、导语、整句）用
  `c.sans(15+, 600+)` 或 `c.serif(18, 620)` —— 细字重经 AA→阈值/量化会断笔画，这是
  中文发虚的头号原因，加粗即解；400/500 字重不要用于 <20px 中文。标题、磁贴标签、
  天气词等短点缀用 `c.ptext()`（Fusion Pixel，原生 12px 整数倍、ss=1、关抗锯齿）。
  用户反馈：全像素正文不好看，像素体只留标题（2026-07）。
- Space Mono / Doto 无 CJK 和下标字符（₂、℃ 部分变体）：写 "CO2" 不写 "CO₂"；
  混排用 `c.text_mixed`。fusion-pixel-8px 缺 μ（12px 版齐全）。
- `Image.convert("1")` 默认带抖动，文本导出要的是阈值 —— 已封装在 `BWPanel.export`，别绕过。
- HA SSH add-on 没有 SFTP：deploy 的 paramiko 路径走 `cat > file` exec 通道，别改成 sftp。
- `mode "1"` 图像用 ImageChops.invert 会产生 254/255 脏值，反色永远在 L 空间做。
- codex `exec` 需要 `--skip-git-repo-check`；生图时用 `-s workspace-write` 且 cwd 指向输出目录。
