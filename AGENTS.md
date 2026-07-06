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
  draw.py            Canvas：语义色 + 最终像素坐标的绘图原语（tile/pill/ring/dotsicon/wrap…）
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
3. **预抖动图像只能贴 ss=1 画布**（`Canvas.paste` 有断言）。照片风格整个用 `Canvas(panel, ss=1)`；
   纯文本/矢量风格用默认 ss（bw=1 保 Doto 点阵锐利，e6=2 保中文平滑）。
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

- Space Mono / Doto 无 CJK 和下标字符（₂、℃ 部分变体）：中文用 `c.sans/serif`，
  写 "CO2" 不写 "CO₂"；混排用 `c.text_mixed`。
- `Image.convert("1")` 默认带抖动，文本导出要的是阈值 —— 已封装在 `BWPanel.export`，别绕过。
- HA SSH add-on 没有 SFTP：deploy 的 paramiko 路径走 `cat > file` exec 通道，别改成 sftp。
- `mode "1"` 图像用 ImageChops.invert 会产生 254/255 脏值，反色永远在 L 空间做。
- codex `exec` 需要 `--skip-git-repo-check`；生图时用 `-s workspace-write` 且 cwd 指向输出目录。
