"""Agent/MCP 日志工具包。

调用方按职责从 schemas、context、search、aggregation 等子模块显式导入，避免
初始化包时加载完整服务依赖图并制造隐式公共 API。
"""
