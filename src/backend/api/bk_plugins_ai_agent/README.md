# Agent ChatCompletion 调用约定

本模块封装 AIDev `/bk_plugin/openapi/agent/chat_completion/`。`agent_code` 选择智能体路由，`user` 转换为 `X-BKAIDEV-USER` 请求头；两者不作为业务消息发送。认证由 API 层完成。

## 首轮：注入系统提示词并固定会话

调用前生成并保存 `thread_id`。首轮把系统提示词与第一问放入 `chat_history`，不要再同时传同一份 `input`：

```json
{
  "chat_history": [
    {"role": "role", "content": "你是业务助手，请依据提供的信息回答问题。"},
    {"role": "user", "content": "本次问题及上下文"}
  ],
  "execute_kwargs": {"stream": true, "thread_id": "task-123"}
}
```

这里 `role` 字段的值 **就是 `role`**，是当前 AIDev 接口的人设消息约定，不要替换成其他厂商协议的 `system`。
按当前服务端会话约定，用户、智能体及 `thread_id` 共同确定 session_code（`MD5(用户:智能体:thread_id)`），首轮 role/user 写入该会话后执行模型。因此不应依赖每次调用临时生成的服务端会话，也不应在应用间任意复用会话标识。

## 后续轮：复用会话，只提交新问题

```json
{
  "input": "那根因是什么？",
  "execute_kwargs": {"stream": true, "thread_id": "task-123"}
}
```

保持相同 `user`、`agent_code` 和 `thread_id`，不用重复发送人设和已处理的历史。新用户、新独立任务或需要隔离的重新执行使用新 thread_id。超时不表示服务端一定没有执行，不能把新 thread_id 当作服务端幂等键。

## 流式消费

`on_event` 是本地回调，不发送上游；传入回调时消费完整流并返回 `None`，调用方负责提取最终产物。不传回调时接口返回最终正文。

thread_id 只放非敏感标识，不放提示词、凭据或业务正文。
