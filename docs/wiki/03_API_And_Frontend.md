# 03 - Web API 与前端交互

## 3.1 路由与页面

- `/`：欢迎页 `templates/welcome.html`（见 [welcome](file:///workspace/app.py#L175-L178)）
- `/chat_page`：对话页 `templates/chat.html`（见 [chat_ui_page](file:///workspace/app.py#L179-L182)）
- `/static/*`：静态资源目录 `static/`（Flask 内置静态目录 + 自定义图片路由）
- `/static/images/<filename>`：图片路由（见 [serve_image](file:///workspace/app.py#L215-L217)）

## 3.2 SSE 接口：/api/chat

### 请求

- 方法：GET
- URL：`/api/chat?query=<URL编码后的文本>`
- 返回：`Content-Type: text/event-stream`
- 核心实现：[handle_chat_api](file:///workspace/app.py#L183-L213)

### 响应（事件格式）

后端通过 SSE 按块输出，每条消息是一个 JSON 对象，形如：

```text
data: {"type":"thinking_step","step":1,"title":"分析问题意图和关键词"}

```

序列化逻辑见 [generate_step_by_step_streaming_response](file:///workspace/app.py#L86-L173)。

### 事件类型

- `thinking_start`
  - 字段：`title`
- `thinking_step`
  - 字段：`step`（数字）、`title`
- `thinking_content`
  - 字段：`step`（对应当前 step）、`content`（字符串，可能是流式 chunk）
- `thinking_end`
- `final_answer_start`
  - 字段：`title`
- `final_answer_content`
  - 字段：`content`（字符串，流式 chunk）
- `final_end`
- `error`
  - 字段：`content`

## 3.3 前端 SSE 消费与渲染

核心逻辑位于 [chat.html](file:///workspace/templates/chat.html#L266-L366)：

- 建立连接：`new EventSource(\`/api/chat?query=${encodeURIComponent(query)}\`)`
- 消息处理：`eventSource.onmessage = (event) => { const data = JSON.parse(event.data); switch (data.type) ... }`
- 思考过程渲染容器：
  - 创建容器：`createThinkingContainer()`
  - 每步容器：在 `thinking_step` 创建 `.thinking-step-content`
  - 内容追加：在 `thinking_content` 将 `data.content` 追加到当前 step
- 最终答案渲染容器：
  - 创建容器：`createFinalAnswerContainer()`
  - 内容追加：在 `final_answer_content` 将 `data.content` 追加到最终区域
- 错误处理：`error` 事件与 `eventSource.onerror`

## 3.4 与后端耦合点（修改时需同步）

- SSE 事件类型与字段：前后端 `switch(data.type)` 必须一致
  - 后端生成见 [app.py](file:///workspace/app.py#L95-L166)
  - 前端消费见 [chat.html](file:///workspace/templates/chat.html#L268-L350)
- Markdown 渲染：前端对 `data.content` 做 `simpleMarkdownToHtml`；若后端输出格式变化（比如改成富文本/结构化 token），需要同时调整前端渲染器。

