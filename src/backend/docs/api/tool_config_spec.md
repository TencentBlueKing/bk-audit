# 工具配置规范与开发指南

## 1. 概述

本项目支持多种类型的工具配置（API, Data Search, BK Vision）。为了适应不同工具的配置差异，后端采用了多态 Schema 设计。本文档详细说明了各类工具的配置结构、特殊系统行为以及相关开发规范。

## 2. 工具配置结构 (Tool Config)

`config` 字段的结构严格依赖于 `tool_type` 字段的值。

### 2.1 API 工具 (`tool_type="api"`)

对应后端模型：`ApiToolConfig`

API 工具用于对接外部 HTTP 接口，支持复杂的参数处理和结果提取。

**核心字段说明：**

*   **`api_config`**: 定义 HTTP 请求细节。
    *   包含 `url`, `method`, `auth_config` 等。
    *   **权限控制**：此字段包含鉴权敏感信息，**仅对拥有 `manage_tool` 权限的用户可见**。对于无权限用户，接口返回时该字段为 `null`。
*   **`input_variable`**: 输入变量列表。支持多种字段类型。
    *   **`time_range_select` 特性**：新增 `split_config`。允许在执行时将一个时间范围值（列表）拆分为起始和结束两个独立参数。
        ```json
        {
          "field_category": "time_range_select",
          "split_config": {
            "start_field": "start_time", // 拆分后的开始时间参数名
            "end_field": "end_time"      // 拆分后的结束时间参数名
          }
        }
        ```
*   **`output_config`**: 输出结果配置。
    *   `enable_grouping` (bool): 前端展示开关。开启时，前端应按分组展示；关闭时，前端应忽略分组结构平铺展示。
    *   `groups`: 输出分组列表，每个分组包含 `output_fields`。支持嵌套表格结构。

### 2.2 数据查询 (`tool_type="data_search"`)

对应后端模型：`SQLDataSearchConfig`

用于执行 SQL 查询。

**核心字段说明：**

*   `data_search_config_type`: 目前支持 `sql`。
*   `sql`: 待执行的 SQL 语句。
*   `referenced_tables`: 涉及的表列表，用于权限校验。

### 2.3 BK Vision (`tool_type="bk_vision"`)

对应后端模型：`BkVisionConfig`

用于嵌入 BK Vision 图表。

**核心字段说明：**

*   `uid`: BK Vision 的图表唯一标识。

## 3. 系统行为说明

### 3.1 枚举映射 (Enum Mapping)

API 工具的输出字段支持配置枚举值映射。

*   **ID 生成规则**：由于 API 输出结构支持嵌套（表格中套表格）且字段名可能重复，后端采用 MD5 哈希生成唯一的枚举集合 ID：
    > `collection_id = md5(group_name + "-" + json_path + "-" + raw_name)`
*   **自动化处理**：开发者在创建/更新工具时，只需在 `output_fields` 中提供 `enum_mappings` 配置，后端会自动计算 ID 并同步元数据，无需人工干预。

### 3.2 权限与脱敏

*   **工具详情接口 (`GetToolDetail`)**：
    *   后端会注入权限字段 `permission`。
    *   如果用户没有 `manage_tool` 权限，且工具类型为 API，后端会自动将 `config.api_config` 置为 `null`，以保护鉴权凭证。

## 4. 开发指南：OpenAPI 文档

项目已从 `drf-yasg` 迁移至 **`drf-spectacular` (OpenAPI 3.0)**。

### 4.1 查看文档
访问 `/swagger/` 查看实时生成的 API 文档。

### 4.2 多态 Schema 维护
为了在 Swagger 中正确展示 `config` 字段的多态结构（即根据 `tool_type` 显示不同的 JSON 结构），我们在 Serializer 中使用了 `PolymorphicProxySerializer`。

**代码位置**：`services/web/tool/serializers.py`

```python
@extend_schema_field(
    PolymorphicProxySerializer(
        component_name='ToolConfigPoly',
        serializers={
            'data_search': SQLDataSearchConfig,
            'api': ApiToolConfig,
            'bk_vision': BkVisionConfig,
        },
        resource_type_field_name='tool_type',
    )
)
class ToolConfigField(serializers.DictField):
    pass
```

**注意事项**：
*   如果新增工具类型，必须在 `serializers` 字典中添加对应的 Pydantic 模型映射。
*   `drf-spectacular` 已配置为原生支持 Pydantic V2，因此可以直接使用 Pydantic 模型作为 Schema 源。

### 4.3 框架适配 (bk_resource)
项目包含一个自定义适配器 `core/utils/spectacular.py::BKResourceAutoSchema`，它负责：
1.  自动从 `bk_resource` 的 `Resource` 类中提取 `RequestSerializer` 和 `ResponseSerializer`。
2.  从 `docstring` 提取接口描述，并自动修复格式。
3.  推断 `ResourceViewSet` 动态生成方法的 Action 名称。

通常情况下，开发者无需手动编写 `@extend_schema`，只需规范定义 `Resource` 类即可自动生成文档。
