# API 工具执行器设计方案

## 1. 概述
本文档详细描述了 API 工具执行器 (`ApiToolExecutor`) 的设计与实现方案。该执行器负责解析前端传入参数、处理变量格式化与拆分、进行认证处理，并最终发起 HTTP 请求。

## 2. 核心类与职责

### 2.1 执行参数模型 (Model)
位于 `services/web/tool/executor/model.py`

*   **`APIToolExecuteVariable`**: 定义单个执行变量。
    *   `raw_name`: 变量名
    *   `value`: 变量值 (`Any` 类型，支持 List/String/Int)
    *   `position`: 参数位置 (`QUERY`, `BODY`, `PATH`)
*   **`APIToolExecuteParams`**: 执行参数集合，包含 `tool_variables` 列表。

### 2.2 异常处理 (Exception)
位于 `services/web/tool/exceptions.py`

*   **`ApiToolExecuteError`**: 统一封装 API 请求过程中的异常（如网络错误、非 200 响应）。返回 400 状态码，避免 500。

### 2.3 认证处理 (Auth)
位于 `services/web/tool/executor/auth.py`

采用策略模式：
*   **`BaseAuthHandler`**: 基类接口。
*   **`BkAppAuthHandler`**: 蓝鲸应用认证，负责注入 `X-Bkapi-Authorization` 头。
*   **`NoAuthHandler`**: 无认证。
*   **`AuthHandlerFactory`**: 工厂类，根据 `auth_method` 返回对应的 Handler。

### 2.4 变量解析 (Parser)
位于 `services/web/tool/executor/parser.py`

将原有的 `VariableValueParser` 拆分为继承体系：
*   **`BaseVariableParser`**: 通用格式化逻辑（如 String, Number, 单个 Time 转换）。
*   **`SqlVariableParser`**: SQL 专用逻辑（如 List 转 SQL `IN` 字符串）。
*   **`ApiVariableParser`**: API 专用逻辑（如 List 保持原样，由 requests 库处理序列化）。

### 2.5 执行器 (Executor)
位于 `services/web/tool/executor/tool.py`

**`ApiToolExecutor`** 继承自 `BaseToolExecutor`。

#### 核心流程：

1.  **参数解析 (`_parse_params`)**:
    *   将前端 JSON 转换为 `APIToolExecuteParams` 对象。
    *   仅做结构转换，不做业务逻辑处理。

2.  **请求构建与渲染 (`_render_request_params`)**:
    *   遍历前端传入的 `tool_variables`。
    *   根据 `config.input_variable` 进行校验。
    *   **变量格式化**：调用 `ApiVariableParser.parse(value)`。
    *   **时间范围拆分**：
        *   若变量为 `TIME_RANGE_SELECT` 且配置了 `split_config`。
        *   将解析后的 `[start, end]` 值拆分为两个独立参数：
            *   `{name: start_field, value: start, pos: original_pos}`
            *   `{name: end_field, value: end, pos: original_pos}`
    *   返回扁平化的请求参数列表。

3.  **执行请求 (`_execute`)**:
    *   调用 `_render_request_params` 获取最终参数。
    *   **参数分类**：按 `position` (PATH, QUERY, BODY) 分组。
    *   **认证**：调用 `AuthHandler` 获取认证头。
    *   **发送**：使用 `requests.request` 发起调用。
    *   **异常**：捕获 `RequestException`，抛出 `ApiToolExecuteError`。
    *   **结果**：直接返回 `response.json()`。

## 3. 注意事项
*   **代码规范**：所有枚举值使用 `Enum` 常量，保持代码简洁。
*   **复用性**：最大化利用 `BaseVariableParser` 避免重复代码。
*   **安全性**：认证信息直接从配置读取，不通过前端透传。
