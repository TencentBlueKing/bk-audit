"""封装BKBase V4单接口协议。

业务编排、版本选择与资源持久化由业务Service处理。
平台及个人鉴权复用BkApiResource既有机制。
"""
import abc

from bk_resource import BkApiResource
from bk_resource.exceptions import APIRequestError
from blueapps.utils.request_provider import get_local_request
from django.conf import settings
from django.core.exceptions import PermissionDenied

from api.bk_base_v4.serializers import (
    CleanDebugRequestSerializer,
    DataIdTailRequestSerializer,
    DatasetDetailRequestSerializer,
    DatasetListRequestSerializer,
    FlowIdRequestSerializer,
    FlowListRequestSerializer,
    FlowRestartRequestSerializer,
    NamedResourceRequestSerializer,
    NamedResourceWriteRequestSerializer,
    ObjectResponseSerializer,
    PayloadResponseSerializer,
    QuerySyncRequestSerializer,
    QuerySyncResponseSerializer,
    ResourceRefRequestSerializer,
    ResourceWriteRequestSerializer,
    ResultTableRequestSerializer,
    UserCheckRequestSerializer,
    UserScopesRequestSerializer,
    UserTablesRequestSerializer,
)
from api.domains import BK_BASE_API_URL, BK_BASE_DEBUG_API_URL


class BkBaseV4Resource(BkApiResource, abc.ABC):
    """平台操作默认使用当前配置的平台身份。"""

    module_name = "bkbase_v4"
    base_url = BK_BASE_API_URL
    platform_authorization = True
    IS_STANDARD_FORMAT = False

    def parse_response(self, response):
        """兼容V4原生资源对象和网关标准包裹，不丢弃原生payload。"""
        try:
            payload = super().parse_response(response)
        except APIRequestError as error:
            error.http_status = response.status_code
            raise
        if isinstance(payload, dict) and "data" in payload and ("result" in payload or "code" in payload):
            if payload.get("result") is False:
                error = APIRequestError(module_name=self.module_name, url=self.action, result=payload)
                error.resource_not_found = str(payload.get("code")) == "1558025" or (
                    str(payload.get("code")) == "1500102"
                    and isinstance(payload.get("data"), dict)
                    and payload["data"].get("err") == "resource not exists"
                )
                raise error
            return payload["data"]
        return payload

    def before_request(self, kwargs):
        """路径参数只进入URL，不混入业务JSON。"""
        key = "params" if self.method == "GET" else "json"
        if key in kwargs:
            kwargs[key] = {k: v for k, v in kwargs[key].items() if k not in self.url_keys}
        return super().before_request(kwargs)


class QuerySyncResource(BkBaseV4Resource):
    """以平台用户权限执行同步SQL，保留现有五分钟超时。"""

    action = "/v4/queryengine/user/query_sync/"
    method = "POST"
    TIMEOUT = 300
    RequestSerializer = QuerySyncRequestSerializer
    ResponseSerializer = QuerySyncResponseSerializer

    def build_request_data(self, validated_request_data):
        """省略未选择的存储，让上游按默认规则选择。"""
        data = super().build_request_data(dict(validated_request_data))
        if not data.get("prefer_storage"):
            data.pop("prefer_storage", None)
        return data


class DebugQuerySyncResource(QuerySyncResource):
    """调试使用独立地址，其余协议与普通查询相同。"""

    base_url = BK_BASE_DEBUG_API_URL


class ResultTable(BkBaseV4Resource):
    """读取已知RT的MCP元数据。"""

    action = "/v4/mcp/result_tables/{result_table_id}/"
    method = "GET"
    url_keys = ["result_table_id"]
    RequestSerializer = ResultTableRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DatasetDetail(BkBaseV4Resource):
    """读取指定项目数据集详情。"""

    action = "/v4/databus/dataset/{namespace}/detail/{dataset_name}/"
    method = "GET"
    url_keys = ["namespace", "dataset_name"]
    RequestSerializer = DatasetDetailRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DatasetList(BkBaseV4Resource):
    """读取项目数据集的一页，分页在Service推进。"""

    action = "/v4/databus/dataset/{namespace}/dataset_list/"
    method = "GET"
    url_keys = ["namespace"]
    RequestSerializer = DatasetListRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class UserBkBaseV4Resource(BkBaseV4Resource, abc.ABC):
    """个人接口显式携带真实请求身份，后台线程也不得借用平台账号。"""

    platform_authorization = False

    def add_esb_info_before_request(self, params):
        request = params.pop("_request", None) or get_local_request()
        params.pop("_is_backend", None)
        user = getattr(request, "user", None)
        username = getattr(user, "bk_username", None) or getattr(user, "username", None)
        if not username or not getattr(user, "is_authenticated", False):
            raise PermissionDenied("Authenticated BKBase user required")
        params.update(bk_app_code=settings.APP_CODE, bk_app_secret=settings.SECRET_KEY, bk_username=username)
        params.update(self.build_auth_args(request))
        return params


class UserResultTables(UserBkBaseV4Resource):
    action = "/v4/mcp/result_tables/mine/"
    method = "GET"
    RequestSerializer = UserTablesRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class UserScopes(UserBkBaseV4Resource):
    action = "/v4/mcp/auth/users/scopes/"
    method = "GET"
    RequestSerializer = UserScopesRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class UserCheck(UserBkBaseV4Resource):
    action = "/v4/mcp/auth/users/check/"
    method = "POST"
    RequestSerializer = UserCheckRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class DataSourceList(BkBaseV4Resource):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datasources/"
    method = "GET"
    url_keys = ["tenant", "namespace"]
    RequestSerializer = ResourceRefRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class DataSourceGet(DataSourceList):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datasources/{name}"
    url_keys = ["tenant", "namespace", "name"]
    RequestSerializer = NamedResourceRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class UserDataSourceList(UserBkBaseV4Resource, DataSourceList):
    """同一路由使用用户身份，列表范围由上游控制。"""


class UserDataSourceGet(UserBkBaseV4Resource, DataSourceGet):
    """同一路由个人详情，Service先验证可见范围。"""


class DataSourceUpdate(DataSourceGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datasources/{name}/"
    method = "PUT"
    RequestSerializer = NamedResourceWriteRequestSerializer


class DataIdTail(BkBaseV4Resource):
    action = "/v4/namespaces/{namespace}/dataids/{name}/tail_kafka/"
    method = "GET"
    url_keys = ["namespace", "name"]
    RequestSerializer = DataIdTailRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class CleanDebug(BkBaseV4Resource):
    """执行无资源副作用的V4清洗预览，业务层检查内层执行状态。"""

    action = "/v4/databus/clean/debug/"
    method = "POST"
    RequestSerializer = CleanDebugRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class CleanGet(BkBaseV4Resource):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/cleans/{name}/"
    method = "GET"
    url_keys = ["tenant", "namespace", "name"]
    RequestSerializer = NamedResourceRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class CleanCreate(CleanGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/cleans/"
    method = "POST"
    url_keys = ["tenant", "namespace"]
    RequestSerializer = ResourceWriteRequestSerializer


class CleanUpdate(CleanGet):
    method = "PUT"
    RequestSerializer = NamedResourceWriteRequestSerializer


class CleanDelete(CleanGet):
    method = "DELETE"
    ResponseSerializer = None


class DataStorageGet(BkBaseV4Resource):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/{name}/"
    method = "GET"
    url_keys = ["tenant", "namespace", "name"]
    RequestSerializer = NamedResourceRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DataStorageCreate(DataStorageGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/"
    method = "POST"
    url_keys = ["tenant", "namespace"]
    RequestSerializer = ResourceWriteRequestSerializer


class DataStorageUpdate(DataStorageGet):
    method = "PUT"
    RequestSerializer = NamedResourceWriteRequestSerializer


class FlowGet(BkBaseV4Resource):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/flows/{name}/"
    method = "GET"
    url_keys = ["tenant", "namespace", "name"]
    RequestSerializer = NamedResourceRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class FlowCreate(FlowGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/flows/"
    method = "POST"
    url_keys = ["tenant", "namespace"]
    RequestSerializer = ResourceWriteRequestSerializer


class FlowUpdate(FlowGet):
    method = "PUT"
    RequestSerializer = NamedResourceWriteRequestSerializer


class Flows(BkBaseV4Resource):
    action = "/v4/mcp/flows/"
    method = "GET"
    RequestSerializer = FlowListRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class FlowStatus(BkBaseV4Resource):
    action = "/v4/mcp/flows/{flow_id}/status/"
    method = "GET"
    url_keys = ["flow_id"]
    RequestSerializer = FlowIdRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class FlowLatestDeploy(FlowStatus):
    action = "/v4/mcp/flows/{flow_id}/latest_deploy_data/"


class FlowRestart(FlowStatus):
    action = "/v4/mcp/flows/{flow_id}/restart/"
    method = "POST"
    RequestSerializer = FlowRestartRequestSerializer
    ResponseSerializer = PayloadResponseSerializer
