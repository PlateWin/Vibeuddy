# Vibeuddy

Vibeuddy 是一只会陪你 Vibe Coding 的 AI 项目桌宠。

它不是普通桌宠，也不是普通 AI 编程工具。Vibeuddy 的核心是：在 AI 帮你快速写代码时，它会主动追问“为什么要做这个功能”，把你从“点菜式提需求”拉回到真正的项目思考里。

> 每一次回车，项目都会长成一只更具体的宠物。每一次追问，你都会成为更清醒的创作者。

## Why

Vibe Coding 让编程变得像对话一样快，但也带来一个很隐蔽的问题：用户很容易不断让 AI 加功能。

```text
加登录。加排行榜。加聊天。加分享。加数据库。加 AI。加地图。
```

项目好像越来越完整，但用户可能越来越不清楚：

- 这个功能服务谁？
- 它解决真实痛点吗？
- 它会不会拖慢 MVP？
- 如果删掉它，项目还成立吗？

Vibeuddy 想解决的就是这种“空心化”和“执行者陷阱”。它用一只项目宠物把项目状态可视化，并在关键节点主动提问，帮助用户保留对项目的理解权和决策权。

## Core Idea

Vibeuddy 把一次 Vibe Coding 回车变成一个可感知的项目成长闭环：

```text
用户输入
→ Claude Code / Vibe Coding 提交
→ Hook 监听
→ Agent 评估项目状态
→ 桌宠状态变化
→ 桌宠主动追问
→ 用户重新思考
→ 项目继续进化
```

它最重要的能力不是卖萌，而是提问。

```text
“这个功能解决真实痛点，还是只是看起来很酷？”
“如果明天就要演示，你现在最应该完成哪一个闭环？”
“如果删掉这个功能，项目还成立吗？”
```

## Features

- **Claude Code 监听**：通过 Claude Code `UserPromptSubmit` hook 监听用户每次提交 prompt。
- **像素桌宠**：本地 Tkinter 桌宠，包含站立、答对、答错动作。
- **像素气泡**：桌宠上方显示 8-bit 风格对话气泡。
- **动作反馈**：答对播放 `correct`，答错播放 `wrong`，平时播放 `stand`。
- **项目思考教练**：围绕功能取舍、目标用户、MVP 范围、技术风险进行追问。
- **报告卡/海报方向**：最终可以生成项目宠物成长报告，用于黑客松答辩和传播。

## Current Demo

当前仓库已经实现的部分：

- 桌面像素宠物：[desktop_pet.py](desktop_pet.py)
- Claude Code 监听 hook：[.claude/hooks/vibeuddy_listen.py](.claude/hooks/vibeuddy_listen.py)
- Claude Code hook 配置：[.claude/settings.json](.claude/settings.json)
- 桌宠动作素材：[assets/pet_answer_actions_v3](assets/pet_answer_actions_v3)
- 核心设计文档：[docs/project-core-design.md](docs/project-core-design.md)

## Quick Start

### 1. 安装依赖

桌宠使用 Python Tkinter 和 Pillow。Tkinter 通常随 Python 自带，Pillow 用于素材处理脚本。

```powershell
pip install pillow
```

### 2. 启动桌宠

```powershell
python desktop_pet.py
```

操作：

- 右键：打开菜单
- 双击：播放答对动作
- 鼠标中键：播放答错动作
- 拖拽：移动桌宠
- 菜单中可显示/隐藏气泡

### 3. 验证 Claude Code 监听

Claude Code hook 会把监听事件写入：

```text
.vibeuddy/claude-listener/latest.json
.vibeuddy/claude-listener/events.jsonl
.vibeuddy/claude-listener/event-*.json
```

在 Claude Code 中提交一次 prompt 后，运行：

```powershell
Get-Content .vibeuddy\claude-listener\latest.json
```

如果看到类似内容，说明监听成功：

```json
{
  "source": "claude-code",
  "hook_event": "UserPromptSubmit",
  "prompt_preview": "..."
}
```

## Project Structure

```text
Vibeuddy/
├─ desktop_pet.py                         # 本地桌宠入口
├─ .claude/
│  ├─ settings.json                       # Claude Code hook 配置
│  └─ hooks/
│     └─ vibeuddy_listen.py               # 监听 UserPromptSubmit
├─ .vibeuddy/
│  └─ claude-listener/                    # 监听日志输出
├─ assets/
│  └─ pet_answer_actions_v3/              # 桌宠动作帧
│     ├─ stand/
│     ├─ correct/
│     ├─ wrong/
│     ├─ idle/
│     ├─ happy/
│     └─ confused/
├─ scripts/
│  ├─ build_answer_pet_actions.py         # 动作素材构建脚本
│  ├─ crop_sprite_to_transparent.py
│  ├─ align_pet_frames.py
│  └─ split_pet_actions.py
└─ docs/
   └─ project-core-design.md              # 产品核心设计文档
```

## How It Works

### Claude Code Hook

`.claude/settings.json` 注册了 Claude Code 的 `UserPromptSubmit` hook。

当用户在 Claude Code 中提交 prompt 时，Claude Code 会调用：

```powershell
python .claude/hooks/vibeuddy_listen.py
```

监听脚本会读取 hook 标准输入中的 JSON payload，并写入 `.vibeuddy/claude-listener/`。

当前阶段只做监听和落日志，确保“每次回车可以被捕捉”这件事成立。下一步可以把监听事件发送给桌宠，让桌宠主动弹出问题。

### Desktop Pet

`desktop_pet.py` 直接读取 `assets/pet_answer_actions_v3` 中的动作帧：

- `stand`：待机站立
- `correct`：答对动作
- `wrong`：答错动作

桌宠带有像素风气泡，用于显示提示、追问和反馈。

## Design Principles

### 1. 宠物不是装饰，是思考入口

Vibeuddy 的可爱不是目的。可爱是为了让用户愿意面对那些本来会被忽略的问题。

### 2. 不替用户做决定，而是把决策权还给用户

宠物不会说“不要加排行榜”。

它会问：

```text
排行榜服务的是谁？
如果你的核心用户只是两个人面对面扫码，排行榜真的重要吗？
```

### 3. 反馈让你看见状态，追问让你重新思考

评分和动画只是第一层。真正的产品差异点是主动追问。

## Roadmap

- [x] 像素桌宠基础动作
- [x] 像素气泡对话框
- [x] Claude Code `UserPromptSubmit` 监听
- [ ] 监听事件驱动桌宠气泡
- [ ] 根据 prompt 生成项目追问
- [ ] 用户回答后触发 correct / wrong
- [ ] 项目五维评分与成长记录
- [ ] 生成 2.5D 8-bit 项目报告卡/海报

## Poster Direction

海报视觉重点不是“项目评分表”，而是“宠物正在提问”。

推荐主视觉：

```text
一只 2.5D 8-bit 赛博孵化猫站在像素展台上，
上方弹出巨大像素气泡：

“这个功能，真的必要吗？”

旁边是一叠功能菜单：
加登录、加排行榜、加聊天、加 AI、加地图。

画面表达：
AI 可以帮你做出来，但 Vibeuddy 会问你为什么要做。
```

## License

Hackathon prototype. License TBD.
