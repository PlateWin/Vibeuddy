# 阶段实施文档：Vibe Coding 后总结项目并主动提问

## 1. 阶段目标

本阶段要实现一个最小但完整的“回到思考”闭环：

```text
用户在 Claude Code / Vibe Coding 中提交一次输入
→ Vibeuddy 监听到本次输入
→ 读取项目上下文并总结当前项目内容
→ 调用模型生成一个项目理解问题
→ 用户通过选择题或简短回答作答
→ 判断回答是否命中项目理解点
→ 答对播放 correct 动作
→ 答错播放 wrong 动作
```

这一阶段的重点不是做完整评分系统，而是证明 Vibeuddy 最核心的差异点成立：

> 宠物不是沉默执行工具，而是会在 Vibe Coding 之后主动提问，把用户拉回项目思考。

## 2. 本阶段范围

### 必须完成

- 监听 Claude Code 的 `UserPromptSubmit` 事件。
- 记录用户本次 prompt。
- 读取当前项目的轻量上下文。
- 生成项目摘要。
- 生成一道问题，优先为选择题。
- 将问题展示给用户。
- 用户回答后判断对错。
- 调用桌宠动作：
  - 答对：`correct`
  - 答错：`wrong`
- 将本轮问答记录保存到本地。

### 暂不做

- 不做完整五维评分系统。
- 不做长期记忆复杂建模。
- 不做真实 VS Code 插件。
- 不做多轮问答链。
- 不做复杂 UI 面板。
- 不做自动修改项目代码。

## 3. 技术栈与模型

### 监听入口

使用 Claude Code hook：

```text
UserPromptSubmit
```

当前项目已有：

```text
.claude/settings.json
.claude/hooks/vibeuddy_listen.py
```

下一步在现有监听基础上增加“触发提问任务”的逻辑。

### 模型服务

内部使用硅基流动，采用 OpenAI-compatible Chat Completions API。

Base URL：

```text
https://api.siliconflow.cn/v1
```

Chat Completions endpoint：

```text
POST https://api.siliconflow.cn/v1/chat/completions
```

模型名：

```text
deepseek-ai/DeepSeek-V4-Flash
```

官方文档参考：

```text
https://docs.siliconflow.cn/cn/api-reference/chat-completions/chat-completions
```

### API Key 管理

不要把 API key 写入代码、README 或阶段文档。

本阶段统一使用环境变量：

```powershell
$env:SILICONFLOW_API_KEY="你的硅基流动 key"
```

Python 读取：

```python
os.environ["SILICONFLOW_API_KEY"]
```

如果缺少该环境变量，程序应给出明确错误提示：

```text
Missing SILICONFLOW_API_KEY. Please set it before running Vibeuddy question loop.
```

## 4. 系统数据流

```text
Claude Code submit prompt
        │
        ▼
UserPromptSubmit hook
        │
        ▼
.claude/hooks/vibeuddy_listen.py
        │
        ├─ 写入监听日志
        │
        └─ 触发 question loop
              │
              ▼
        收集项目上下文
              │
              ▼
        调用 DeepSeek-V4-Flash
              │
              ▼
        生成项目摘要 + 问题
              │
              ▼
        桌宠气泡展示问题
              │
              ▼
        用户回答
              │
              ▼
        判断 correct / wrong
              │
              ▼
        桌宠播放对应动作
```

## 5. 项目上下文收集

本阶段只收集轻量上下文，避免拖慢 hook。

建议读取：

```text
README.md
docs/project-core-design.md
最近一次 UserPromptSubmit prompt
.vibeuddy/question-loop/history.jsonl 最近 3 条
项目文件列表摘要
```

可选读取：

```text
git diff --stat
git diff --name-only
```

上下文长度控制：

- README：最多 3000 字。
- 核心设计文档：最多 5000 字。
- 最近 prompt：完整保留。
- 历史问答：最多 3 条。

不要把整个项目源码塞给模型。

## 6. 模型输出协议

模型必须返回严格 JSON，方便程序解析。

### 请求目标

让模型完成三件事：

1. 总结当前项目正在做什么。
2. 找出一个值得用户思考的问题。
3. 生成标准答案和判分规则。

### 输出 JSON Schema

```json
{
  "project_summary": "一句话总结当前项目",
  "thinking_focus": "本轮最值得思考的点",
  "question": {
    "type": "multiple_choice",
    "text": "问题文本",
    "choices": [
      {
        "id": "A",
        "text": "选项 A"
      },
      {
        "id": "B",
        "text": "选项 B"
      },
      {
        "id": "C",
        "text": "选项 C"
      }
    ],
    "correct_choice": "B",
    "explanation": "为什么这个选项更能体现项目理解"
  },
  "pet_prompt": "给桌宠气泡展示的一句话",
  "difficulty": "easy"
}
```

### 问题原则

问题必须围绕“项目理解”，而不是代码细节考试。

优先问：

- 用户是谁？
- 这个功能为什么必要？
- MVP 应该保留什么？
- 当前最大风险是什么？
- 这个改动让项目更清晰，还是更复杂？

不要问：

- 某个函数叫什么。
- 某行代码做了什么。
- 依赖版本号是多少。
- 太学术或太宽泛的问题。

## 7. Prompt 模板

### System Prompt

```text
你是 Vibeuddy，一只会陪用户 Vibe Coding 的项目思考教练。

你的任务不是审查代码，而是在用户提交一次 Vibe Coding 输入后，帮助用户重新理解自己的项目。

你需要基于项目上下文：
1. 总结当前项目正在做什么。
2. 找出一个最值得用户思考的问题。
3. 生成一道选择题，帮助用户判断自己是否真的理解项目。

问题应该聚焦项目定位、功能取舍、MVP 范围、用户价值或技术风险。
不要考察琐碎代码细节。
不要替用户做决定，要通过问题把决策权还给用户。

必须只返回 JSON，不要输出 Markdown，不要输出额外解释。
```

### User Prompt

```text
项目上下文：
<PROJECT_CONTEXT>

用户刚刚在 Claude Code 中提交的输入：
<LATEST_PROMPT>

最近问答记录：
<RECENT_QA_HISTORY>

请生成一个项目理解问题。
返回格式必须严格符合：
{
  "project_summary": "...",
  "thinking_focus": "...",
  "question": {
    "type": "multiple_choice",
    "text": "...",
    "choices": [
      {"id": "A", "text": "..."},
      {"id": "B", "text": "..."},
      {"id": "C", "text": "..."}
    ],
    "correct_choice": "A|B|C",
    "explanation": "..."
  },
  "pet_prompt": "...",
  "difficulty": "easy|medium"
}
```

## 8. 判题逻辑

### 选择题 MVP

第一版优先实现选择题。

流程：

```text
模型生成 correct_choice
→ 用户输入 A/B/C
→ 本地直接比对
→ 正确播放 correct
→ 错误播放 wrong
```

优点：

- 判题稳定。
- 不需要二次调用模型。
- 适合黑客松现场演示。

### 简答题后续版本

后续可以支持简答题：

```text
用户输入一句回答
→ 调用模型判断是否命中理解点
→ 返回 correct / wrong / partial
```

简答题判分 JSON：

```json
{
  "result": "correct",
  "reason": "用户明确说明了目标用户和功能必要性",
  "pet_reply": "答对啦，你开始抓住项目核心了。"
}
```

## 9. 与桌宠联动协议

桌宠需要暴露一个本地事件接口，或先通过文件轮询实现。

### MVP 推荐：文件事件

先不引入 HTTP server，用文件通信更简单。

问题输出：

```text
.vibeuddy/question-loop/current_question.json
```

用户回答记录：

```text
.vibeuddy/question-loop/current_answer.json
```

结果输出：

```text
.vibeuddy/question-loop/latest_result.json
```

桌宠监听 `latest_result.json`：

```json
{
  "result": "correct",
  "pet_action": "correct",
  "bubble_text": "答对啦，你抓住了项目核心！"
}
```

或：

```json
{
  "result": "wrong",
  "pet_action": "wrong",
  "bubble_text": "再想想：这个功能真的服务核心用户吗？"
}
```

### 后续版本：本地 HTTP

桌宠可提供：

```text
POST http://127.0.0.1:8765/event
```

请求：

```json
{
  "type": "question_result",
  "result": "correct",
  "bubble_text": "答对啦！",
  "action": "correct"
}
```

## 10. 本地文件目录

新增目录：

```text
.vibeuddy/question-loop/
```

建议文件：

```text
current_question.json
current_answer.json
latest_result.json
history.jsonl
errors.log
```

历史记录格式：

```json
{
  "created_at": "2026-05-16T00:00:00Z",
  "source_prompt": "...",
  "project_summary": "...",
  "question": "...",
  "choices": ["A ...", "B ...", "C ..."],
  "correct_choice": "B",
  "user_answer": "B",
  "result": "correct"
}
```

## 11. 实施步骤

### Step 1：增强 hook 监听

在 `.claude/hooks/vibeuddy_listen.py` 中保留现有日志功能。

新增：

- 从 hook payload 中读取 `prompt`。
- 写入 `.vibeuddy/claude-listener/latest.json`。
- 调用 question loop 脚本，或只写入待处理文件。

### Step 2：新增问题生成脚本

新增：

```text
scripts/generate_question.py
```

职责：

- 读取项目上下文。
- 读取最新 prompt。
- 调用硅基流动 API。
- 校验 JSON。
- 写入 `current_question.json`。

### Step 3：新增回答脚本

新增：

```text
scripts/answer_question.py
```

命令示例：

```powershell
python scripts\answer_question.py B
```

职责：

- 读取当前问题。
- 判断用户选择是否正确。
- 写入 `latest_result.json`。
- 写入 `history.jsonl`。

### Step 4：桌宠读取结果

`desktop_pet.py` 增加轮询：

- 每 500ms 检查 `latest_result.json` 更新时间。
- 如果有新结果：
  - `result == correct` → `play_once("correct")`
  - `result == wrong` → `play_once("wrong")`
  - 气泡显示 `bubble_text`

### Step 5：展示问题

第一版可以先不做复杂 UI。

可选方式：

- 写入终端提示。
- 写入桌宠气泡。
- 用 Claude Code 回显问题。
- 后续再做桌宠选择按钮。

MVP 推荐：

```text
桌宠气泡显示问题文本 + A/B/C
用户在终端运行 python scripts\answer_question.py A
桌宠播放 correct/wrong
```

## 12. 错误处理

### API Key 缺失

输出：

```text
Missing SILICONFLOW_API_KEY
```

不生成问题。

### API 调用失败

写入：

```text
.vibeuddy/question-loop/errors.log
```

桌宠气泡显示：

```text
我没想好问题，再试一次?
```

### 模型返回非 JSON

本地尝试提取 JSON。

仍失败则写入错误日志，并生成 fallback 问题：

```json
{
  "question": {
    "type": "multiple_choice",
    "text": "如果明天就要演示，这个项目最需要先保证什么？",
    "choices": [
      {"id": "A", "text": "核心闭环能跑通"},
      {"id": "B", "text": "功能越多越好"},
      {"id": "C", "text": "先做复杂视觉特效"}
    ],
    "correct_choice": "A",
    "explanation": "黑客松演示优先保证核心闭环。"
  }
}
```

## 13. 安全注意事项

- API key 只放环境变量。
- 不提交 `.env`。
- 不把 API key 写入 README、文档、日志。
- `events.jsonl` 中不要记录完整敏感代码。
- 模型请求上下文限制长度，避免上传过多项目内容。
- hook 脚本必须快速返回，不阻塞 Claude Code 正常工作。

## 14. 验收标准

本阶段完成时，必须能演示：

1. 在 Claude Code 中提交一次 Vibe Coding prompt。
2. `.vibeuddy/claude-listener/latest.json` 被刷新。
3. `.vibeuddy/question-loop/current_question.json` 生成一道选择题。
4. 桌宠气泡展示这道题。
5. 用户输入答案。
6. 答对时桌宠播放 correct。
7. 答错时桌宠播放 wrong。
8. `.vibeuddy/question-loop/history.jsonl` 记录本轮问答。

## 15. 演示脚本

现场输入：

```text
给项目加一个排行榜、分享海报、实时地图和多人匹配。
```

预期宠物追问：

```text
如果明天就要演示，这些新增功能里哪个最应该先保留？

A. 排行榜和实时地图都先做完
B. 先保证一个核心互动闭环能跑通
C. 先接入更多 AI 功能
```

正确答案：

```text
B
```

桌宠反馈：

```text
答对啦！先保住核心闭环，项目才不会过载。
```

答对动作：

```text
correct
```

答错反馈：

```text
再想想：功能越多，不一定越适合 MVP。
```

答错动作：

```text
wrong
```

## 16. 下一阶段

下一阶段可以在本阶段基础上继续做：

- 桌宠气泡内直接显示 A/B/C。
- 鼠标点击气泡选项作答。
- 根据历史问答更新项目理解分数。
- 生成最终项目报告卡。
- 将问题触发策略从规则升级为 Agent 判断。
