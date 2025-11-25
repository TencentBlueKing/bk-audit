import json
import logging
from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, Optional, Generic, TypeVar, ClassVar
from enum import Enum

import requests

# ==================== 类型定义 ====================
T = TypeVar('T')


class ApiAuthTypeEnum(str, Enum):
    BK_AUTH = "BK_AUTH"


class ResponseFormat(Enum):
    """响应格式枚举"""
    JSON = "json"
    TEXT = "text"
    BYTES = "bytes"
    RAW = "raw"  # 返回原始Response对象


class APIConfig(BaseModel):
    """
    API执行器配置类
    定义调用逻辑和行为规范
    """
    model_config = ConfigDict(
        validate_default=True,  # 验证默认值
        extra="forbid"  # 禁止额外字段
    )

    url: str = ""
    bk_app_code: str = ""
    bk_app_secret: str = ""
    auth_type: ApiAuthTypeEnum = ApiAuthTypeEnum.BK_AUTH

    timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_logging: bool = True
    verify_ssl: bool = True
    default_headers: Dict[str, str] = field(default_factory=lambda: {
        "User-Agent": "Python-API-Executor/1.0",
        "Accept": "application/json"
    })

    # 响应处理配置
    default_response_format: ResponseFormat = ResponseFormat.JSON
    auto_parse_json: bool = True
    raise_on_error: bool = False  # 是否在状态码>=400时抛出异常（为True时忽略result的success标记）

    # 连接池配置
    pool_connections: int = 10
    pool_maxsize: int = 10
    pool_max_retries: int = 3

    # 重试策略配置
    retry_on_status_codes: list = field(default_factory=lambda: [500, 502, 503, 504])
    retry_on_exceptions: tuple = field(default_factory=lambda: (
        requests.Timeout,
        requests.ConnectionError,
        requests.HTTPError
    ))


@dataclass
class APIExecuteResult(Generic[T]):
    """
    API执行结果封装类
    统一响应结果格式
    """
    success: bool = False
    status_code: Optional[int] = None
    data: Optional[T] = None
    message: str = ""
    raw_response: Optional[requests.Response] = None
    error: Optional[Exception] = None

    def __post_init__(self):
        """自动判断success状态"""
        if self.status_code is not None:
            if not self.success:
                self.success = 200 <= self.status_code < 400

    @property
    def is_ok(self) -> bool:
        """是否成功"""
        return self.success and self.error is None

    def get_data_or_raise(self) -> T:
        """
        获取数据，如果失败则抛出异常
        :return: 响应数据
        :raises: ApiException
        """
        if self.is_ok:
            return self.data
        raise ApiException(
            message=self.message,
            status_code=self.status_code,
            response=self.raw_response
        ) from self.error


# ==================== 自定义异常 ====================
class ApiException(Exception):
    """API调用异常"""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


# ==================== 执行器基类 ====================
class BaseApiExecutor:
    """API执行器基类"""

    def __init__(self, config: APIConfig):
        if not isinstance(config, APIConfig):
            raise TypeError("config必须是APIConfig实例")
        self.config = config
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """设置日志器"""
        logger = logging.getLogger(self.__class__.__name__)
        if self.config.enable_logging:
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
        return logger

    def _log_request(self, method: str, url: str, **kwargs):
        """记录请求日志"""
        if self.config.enable_logging:
            self.logger.info(f"请求: {method.upper()} {url}")
            if "params" in kwargs and kwargs["params"]:
                self.logger.info(f"参数: {kwargs['params']}")
            if "json" in kwargs and kwargs["json"]:
                self.logger.info(f"数据: {kwargs['json']}")

    def _log_response(self, method: str, url: str, result: APIExecuteResult):
        """记录响应日志"""
        if self.config.enable_logging:
            status_emoji = "success" if result.is_ok else "failed"
            self.logger.info(
                f"{status_emoji} 响应: {method.upper()} {url} -> "
                f"Status: {result.status_code}, Success: {result.is_ok}"
            )
            if result.message:
                self.logger.info(f"消息: {result.message}")


# ==================== 同步执行器 ====================
class ApiExecutorMixin(BaseApiExecutor):
    """
    同步API执行器
    使用APIConfig定义调用逻辑
    返回APIExecuteResult封装的结果
    """

    def __init__(self, config: APIConfig):
        super().__init__(config)
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建并配置Session"""
        session = requests.Session()
        session.headers.update(self.config.default_headers)

        # 配置连接池和重试
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=self.config.pool_connections,
            pool_maxsize=self.config.pool_maxsize,
            max_retries=requests.adapters.Retry(
                total=self.config.pool_max_retries,
                backoff_factor=self.config.retry_delay,
                status_forcelist=self.config.retry_on_status_codes
            )
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _execute_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        带重试的执行方法
        内部使用，抛出异常以触发重试
        """
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()  # 触发HTTPError
            return response
        except requests.HTTPError as e:
            # 判断状态码是否在重试列表中
            if e.response.status_code in self.config.retry_on_status_codes:
                raise ApiException(
                    f"可重试的HTTP错误 [{e.response.status_code}]",
                    status_code=e.response.status_code,
                    response=e.response
                ) from e
            raise  # 不可重试的错误直接抛出

    def request(
            self,
            method: str,
            endpoint: str,
            params: Optional[Dict] = None,
            data: Any = None,
            json_data: Any = None,
            headers: Optional[Dict] = None,
            response_format: Optional[ResponseFormat] = None,
            **kwargs
    ) -> APIExecuteResult[Any]:
        """
        统一请求入口
        使用APIConfig规定的逻辑执行
        返回APIExecuteResult封装的结果
        """
        # 构建完整URL
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # 合并headers
        request_headers = {}
        request_headers.update(self.config.default_headers)
        if headers:
            request_headers.update(headers)

        # 准备请求参数
        request_kwargs = {
            "params": params,
            "data": data,
            "json": json_data,
            "headers": request_headers,
            "timeout": self.config.timeout,
            "verify": self.config.verify_ssl,
            **kwargs
        }

        # 移除None值
        request_kwargs = {k: v for k, v in request_kwargs.items() if v is not None}

        # 确定响应格式
        fmt = response_format or self.config.default_response_format

        try:
            # 执行请求（可能触发重试）
            response = self._execute_with_retry(method, url, **kwargs)

            # 解析响应数据
            parsed_data = self._parse_response(response, fmt)

            # 构建成功结果
            result = APIExecuteResult(
                success=True,
                status_code=response.status_code,
                data=parsed_data,
                message="请求成功",
                raw_response=response if fmt == ResponseFormat.RAW else None
            )

        except Exception as e:
            # 构建失败结果
            status_code = getattr(e, "status_code", None)
            raw_response = getattr(e, "response", None)

            result = APIExecuteResult(
                success=False,
                status_code=status_code,
                data=None,
                message=str(e),
                raw_response=raw_response,
                error=e
            )

            # 如果config要求抛出异常，则抛出
            if self.config.raise_on_error and status_code and status_code >= 400:
                self._log_response(method, url, result)
                raise e

        self._log_response(method, url, result)
        return result

    def _parse_response(self, response: requests.Response, fmt: ResponseFormat) -> Any:
        """根据格式解析响应"""
        try:
            if fmt == ResponseFormat.JSON:
                return response.json()
            elif fmt == ResponseFormat.TEXT:
                return response.text
            elif fmt == ResponseFormat.BYTES:
                return response.content
            elif fmt == ResponseFormat.RAW:
                return response
            else:
                return response.json() if self.config.auto_parse_json else response.text
        except json.JSONDecodeError:
            self.logger.warning(f"JSON解析失败，返回原始文本: {response.text[:200]}")
            return response.text

    def get(
            self,
            endpoint: str,
            params: Optional[Dict] = None,
            **kwargs
    ) -> APIExecuteResult[Any]:
        """GET请求"""
        return self.request("GET", endpoint, params=params, **kwargs)

    def post(
            self,
            endpoint: str,
            json_data: Any = None,
            **kwargs
    ) -> APIExecuteResult[Any]:
        """POST请求"""
        return self.request("POST", endpoint, json_data=json_data, **kwargs)

    def put(
            self,
            endpoint: str,
            json_data: Any = None,
            **kwargs
    ) -> APIExecuteResult[Any]:
        """PUT请求"""
        return self.request("PUT", endpoint, json_data=json_data, **kwargs)

    def delete(
            self,
            endpoint: str,
            **kwargs
    ) -> APIExecuteResult[Any]:
        """DELETE请求"""
        return self.request("DELETE", endpoint, **kwargs)

    def patch(
            self,
            endpoint: str,
            json_data: Any = None,
            **kwargs
    ) -> APIExecuteResult[Any]:
        """PATCH请求"""
        return self.request("PATCH", endpoint, json_data=json_data, **kwargs)

    def close(self):
        """关闭会话"""
        self.session.close()


# ==================== 使用示例 ====================
def demo():
    """完整示例"""

    # 1. 配置API执行器
    config = APIConfig(
        base_url="https://jsonplaceholder.typicode.com",
        timeout=5.0,
        max_retries=3,
        enable_logging=True,
        default_response_format=ResponseFormat.JSON
    )

    # 2. 创建执行器
    executor = ApiExecutor(config)

    try:
        # 3. GET请求
        result = executor.get("/posts/1")
        print(f"GET成功: {result.is_ok}")
        if result.is_ok:
            print(f"数据: {result.data}")

        # 4. POST请求
        new_post = {"title": "foo", "body": "bar", "userId": 1}
        result = executor.post("/posts", json_data=new_post)
        print(f"\nPOST成功: {result.is_ok}")
        print(f"返回数据: {result.data}")

        # 5. 带参数GET
        result = executor.get("/posts", params={"userId": 1})
        print(f"\n带参数GET: {result.is_ok}, 获取到 {len(result.data)} 条数据")

        # 6. 错误请求示例
        result = executor.get("/posts/999999")
        print(f"\n错误请求: success={result.success}, status={result.status_code}")
        print(f"错误消息: {result.message}")

        # 7. 获取数据或抛出异常
        # result.get_data_or_raise()  # 这会抛出异常

    finally:
        executor.close()


if __name__ == "__main__":
    demo()