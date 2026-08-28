"""日志工具专用 QuerySync Resource，隔离远端错误正文和 SDK 请求日志。

服务层 catch 已经晚于 Resource.parse_response：默认实现会将远端 message/content
写入日志和 OTel 异常状态。该 Resource 只保留安全状态码与 request_id，并关闭 SDK
按调用记录请求体的机制，避免 SQL、条件和原始行进入观测链路。
"""

from collections.abc import Mapping
from typing import Any

from bk_resource.exceptions import APIRequestError
from requests.exceptions import HTTPError

from api.bk_base.default import QuerySyncResource


class SafeQuerySyncResource(QuerySyncResource):
    """保持 QuerySync 成功数据契约，同时将失败统一为不含远端正文的 APIRequestError。"""

    support_data_collect = False
    _ERROR_MESSAGE = "query sync request failed"

    def parse_response(self, response) -> Any:
        """自行解析响应，绝不委托默认实现处理失败正文或输出日志。"""

        try:
            result = response.json()
        except Exception:  # noqa: BLE001
            raise self._safe_error(response) from None

        try:
            response.raise_for_status()
        except HTTPError:
            raise self._safe_error(response) from None

        if not isinstance(result, dict):
            raise self._safe_error(response)
        if not result.get("result", True) and result.get("code") != 0:
            raise self._safe_error(response)
        return result.get("data")

    def _safe_error(self, response) -> APIRequestError:
        """仅保留低敏的 HTTP 状态和请求关联号，不能携带远端 message/content。"""

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            status_code = None
        headers = getattr(response, "headers", {})
        request_id = headers.get("x-bkapi-request-id", "") if isinstance(headers, Mapping) else ""
        result = {"message": self._ERROR_MESSAGE}
        if isinstance(request_id, str) and request_id:
            result["request_id"] = request_id
        return APIRequestError(
            module_name=self.module_name,
            url=self.action,
            status_code=status_code,
            result=result,
        )


safe_query_sync = SafeQuerySyncResource()
