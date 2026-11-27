"""封装BKBase V4单接口协议。

业务编排、版本选择与资源持久化由业务Service处理。
平台及个人鉴权复用BkApiResource既有机制。
"""
import abc
from contextvars import ContextVar
from time import monotonic

from bk_resource.exceptions import APIRequestError
from bk_resource.settings import bk_resource_settings
from blueapps.utils.request_provider import get_local_request
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from requests.exceptions import Timeout as RequestTimeout
from urllib3.util import Timeout

from api.bk_base_v4.serializers import (
    BatchStatusListRequestSerializer,
    CleanDebugRequestSerializer,
    DataIdTailRequestSerializer,
    DatasetDetailRequestSerializer,
    DatasetListRequestSerializer,
    DirectAuthByResourcesRequestSerializer,
    DirectAuthByResourcesResponseSerializer,
    FlowIdRequestSerializer,
    FlowListRequestSerializer,
    FlowRestartRequestSerializer,
    NamedResourceRequestSerializer,
    NamedResourceWriteRequestSerializer,
    NotifyGetRequestSerializer,
    NotifyUpdateRequestSerializer,
    ObjectResponseSerializer,
    PayloadResponseSerializer,
    RedisAssetCreateRequestSerializer,
    ResourceRefRequestSerializer,
    ResourceWriteRequestSerializer,
    ResultTableInfoRequestSerializer,
    ResultTableRequestSerializer,
    StorageAssetGetRequestSerializer,
    StorageAssetListRequestSerializer,
    TenantRequestSerializer,
    UserCheckRequestSerializer,
    UserScopesRequestSerializer,
    UserTablesRequestSerializer,
)
from api.bk_base_v4.tenant import get_bkbase_v4_tenant
from api.constants import APIProvider
from api.domains import BK_BASE_API_URL
from api.utils import get_endpoint
from core.bk_api_base import AuditBkApiResource
from core.redacted_log import RedactedRequestLogMixin
from core.tenant import TENANT_ID_HEADER

READ_DEADLINE = ContextVar("bkbase_v4_read_deadline", default=None)
INIT_DEADLINE: ContextVar[float | None] = ContextVar("bkbase_v4_init_deadline", default=None)
READ_MAX_TIMEOUT = 30.0


class InitDeadlineBeforeSend(TimeoutError):
    """初始化预算在请求发出前耗尽。"""


def init_deadline_remaining() -> float | None:
    deadline = INIT_DEADLINE.get()
    if deadline is None:
        return None
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise InitDeadlineBeforeSend("BKBase V4 init deadline reached before sending request")
    return remaining


def is_init_deadline_before_send(error: BaseException) -> bool:
    """仅识别本地发送前的证据，不把网络超时当成未下发。"""
    while error is not None:
        if isinstance(error, InitDeadlineBeforeSend):
            return True
        error = error.__cause__
    return False


class BkBaseV4Resource(AuditBkApiResource, abc.ABC):
    """多租户按实例调用 V4，单租户保留原平台认证协议。"""

    module_name = "bkbase_v4"
    platform_authorization = True
    requires_platform_auth = False
    IS_STANDARD_FORMAT = False

    @property
    def base_url(self):
        if self.use_multi_tenant_mode():
            return get_endpoint(settings.BK_BASE_APIGW_NAME, APIProvider.APIGW, stage="prod")
        return BK_BASE_API_URL

    @property
    def use_admin_username(self):
        return self.platform_authorization

    def build_request_data(self, validated_request_data):
        """在构造 URL 之前校验路径租户和资源体中的显式租户引用。"""
        if self.use_multi_tenant_mode():
            tenant = get_bkbase_v4_tenant()
            if validated_request_data.get("tenant") not in (None, tenant):
                raise PermissionDenied("BKBase V4 request does not belong to this tenant")
            metadata = validated_request_data.get("metadata")
            if isinstance(metadata, dict) and "tenant" in metadata and metadata["tenant"] != tenant:
                raise PermissionDenied("BKBase V4 resource metadata does not belong to this tenant")
            refs = [validated_request_data.get("spec"), validated_request_data.get("target")]
            while refs:
                item = refs.pop()
                if isinstance(item, dict):
                    if {"tenant", "namespace", "name"} <= item.keys() and item["tenant"] != tenant:
                        raise PermissionDenied("BKBase V4 resource reference does not belong to this tenant")
                    refs.extend(item.values())
                elif isinstance(item, list):
                    refs.extend(item)
        return super().build_request_data(validated_request_data)

    def add_esb_info_before_request(self, params):
        """单租户平台列表保持原校验；多租户平台身份由审计基类补齐（当前租户管理员）。"""
        if not self.use_multi_tenant_mode() and self.platform_authorization and self.requires_platform_auth:
            username = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
            token = bk_resource_settings.PLATFORM_AUTH_ACCESS_TOKEN
            valid_username = isinstance(username, str) and bool(username.strip())
            valid_token = isinstance(token, str) and bool(token.strip())
            if not bk_resource_settings.PLATFORM_AUTH_ENABLED or not (valid_username or valid_token):
                raise ImproperlyConfigured(
                    "BKBase platform listing requires enabled platform authentication and credentials"
                )
            credentials = self.add_platform_auth_params(
                {"bk_app_code": settings.APP_CODE, "bk_app_secret": settings.SECRET_KEY}
            )
            if not valid_username:
                credentials.pop("bk_username", None)
            if not valid_token:
                credentials.pop("access_token", None)
            return credentials
        return super().add_esb_info_before_request(params)

    def build_header(self, validated_request_data):
        """平台资源不透传操作者Cookie；个人接口保留自己的认证协议。"""
        headers = super().build_header(validated_request_data)
        if self.platform_authorization:
            headers.pop("cookie", None)
        return headers

    def parse_response(self, response):
        """兼容V4原生资源对象和网关标准包裹，不丢弃原生payload。"""
        try:
            payload = super().parse_response(response)
        except APIRequestError as error:
            error.http_status = response.status_code
            raise
        if isinstance(payload, dict) and ("result" in payload or "code" in payload):
            if payload.get("result") is not True or payload.get("code") != "00" or "data" not in payload:
                error = APIRequestError(module_name=self.module_name, url=self.action, result=payload)
                error.resource_not_found = (
                    payload.get("result") is False
                    and "data" in payload
                    and (
                        str(payload.get("code")) == "1558025"
                        or (
                            str(payload.get("code")) == "1500102"
                            and isinstance(payload.get("data"), dict)
                            and payload["data"].get("err") == "resource not exists"
                        )
                    )
                )
                raise error
            return payload["data"]
        return payload

    def before_request(self, kwargs):
        """隔离路径参数，受控初始化和列表请求沿用其剩余预算。"""
        remaining_init = init_deadline_remaining()
        if remaining_init is not None:
            kwargs["timeout"] = Timeout(total=min(self.TIMEOUT, remaining_init))
        deadline = READ_DEADLINE.get()
        if self.method == "GET" and deadline is not None:
            remaining = deadline - monotonic()
            if remaining_init is not None:
                remaining = min(remaining, remaining_init)
            if remaining <= 0:
                raise RequestTimeout("BKBase list read deadline exceeded")
            kwargs["timeout"] = Timeout(total=min(READ_MAX_TIMEOUT, remaining))
        key = "params" if self.method == "GET" else "json"
        if key in kwargs:
            kwargs[key] = {k: v for k, v in kwargs[key].items() if k not in self.url_keys}
        return super().before_request(kwargs)


class DirectAuthByResources(BkBaseV4Resource):
    """以应用身份核对指定用户的 RT 权限，不携带用户凭据或平台账号。"""

    action = "/v4/auth/users/direct_auth_by_resources/"
    method = "POST"
    platform_authorization = False
    RequestSerializer = DirectAuthByResourcesRequestSerializer
    ResponseSerializer = DirectAuthByResourcesResponseSerializer

    def build_request_data(self, validated_request_data):
        data = super().build_request_data(validated_request_data)
        if self.use_multi_tenant_mode():
            data["tenant"] = get_bkbase_v4_tenant()
        return data

    def add_esb_info_before_request(self, params):
        """该接口不做用户认证，前后台均只使用审计应用凭据。"""
        return {"bk_app_code": settings.APP_CODE, "bk_app_secret": settings.SECRET_KEY}

    def build_header(self, validated_request_data):
        """保留语言头，移除与应用认证无关的请求 Cookie。"""
        headers = super().build_header(validated_request_data)
        headers.pop("cookie", None)
        return headers

    def before_request(self, kwargs):
        """禁止将应用凭据转发至重定向目标。"""
        kwargs["allow_redirects"] = False
        return super().before_request(kwargs)

    def parse_response(self, response):
        """权限结果仅接受文档规定的明确成功包裹。"""
        if 300 <= response.status_code < 400:
            raise APIRequestError(module_name=self.module_name, url=self.action, result="Permission check redirected")
        data = super().parse_response(response)
        envelope = response.json()
        if (
            not isinstance(envelope, dict)
            or envelope.get("result") is not True
            or envelope.get("code") != "00"
            or envelope.get("message") is not None
            or envelope.get("errors") is not None
            or "messages" in envelope
        ):
            raise APIRequestError(module_name=self.module_name, url=self.action, result=envelope)
        return data


class BatchStatusList(BkBaseV4Resource):
    """读取正式离线作业历史页，保留原始行和错误。"""

    action = "/v4/dataflow/batch/jobs/{job_id}/status_list/"
    method = "GET"
    url_keys = ["job_id"]
    RequestSerializer = BatchStatusListRequestSerializer
    ResponseSerializer = ObjectResponseSerializer

    def before_request(self, kwargs):
        """正式 Batch 查询要求 URL 布尔参数为小写。"""
        kwargs = super().before_request(kwargs)
        value = kwargs.get("params", {}).get("is_data_time")
        if isinstance(value, bool):
            kwargs["params"]["is_data_time"] = "true" if value else "false"
        return kwargs


class ResultTable(BkBaseV4Resource):
    """读取已知RT的MCP元数据。"""

    action = "/v4/mcp/result_tables/{result_table_id}/"
    method = "GET"
    url_keys = ["result_table_id"]
    RequestSerializer = ResultTableRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DatasetResource(BkBaseV4Resource, abc.ABC):
    """Dataset的企业空间来自Service上下文，不能透传前端任意请求头。"""

    def build_header(self, validated_request_data):
        """把校验后的tenant移入请求头，避免落入业务查询参数。"""
        tenant = validated_request_data.pop("tenant")
        headers = super().build_header(validated_request_data)
        if not self.use_multi_tenant_mode():
            headers[TENANT_ID_HEADER] = tenant
        return headers


class ResultTableInfo(DatasetResource):
    """按逻辑 ID 查询正式结果表，错误不代表允许创建或接管资源。"""

    action = "/v4/result_tables/{result_table_id}/"
    method = "GET"
    url_keys = ["result_table_id"]
    RequestSerializer = ResultTableInfoRequestSerializer
    ResponseSerializer = ObjectResponseSerializer

    def parse_response(self, response):
        """1558025 同时可能表示绑定目标缺失，必须保留失败语义。"""
        try:
            return super().parse_response(response)
        except APIRequestError as error:
            error.resource_not_found = False
            raise


class DatasetDetail(DatasetResource):
    """读取指定项目数据集详情。"""

    action = "/v4/databus/dataset/{namespace}/detail/{dataset_name}/"
    method = "GET"
    url_keys = ["namespace", "dataset_name"]
    RequestSerializer = DatasetDetailRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DatasetList(DatasetResource):
    """读取项目数据集的一页，分页在Service推进。"""

    action = "/v4/databus/dataset/{namespace}/dataset_list/"
    method = "GET"
    url_keys = ["namespace"]
    RequestSerializer = DatasetListRequestSerializer
    ResponseSerializer = ObjectResponseSerializer
    requires_platform_auth = True


class StorageAssetCreate(RedactedRequestLogMixin, DatasetResource):
    """登记Redis存储资产；受理返回asset_name，不冒充正式Ref或连通成功。"""

    action = "/v4/res_manage/assets/storage/"
    method = "POST"
    RequestSerializer = RedisAssetCreateRequestSerializer
    ResponseSerializer = ObjectResponseSerializer

    def before_request(self, kwargs):
        """禁止重定向重发注册请求。"""
        kwargs["allow_redirects"] = False
        return super().before_request(kwargs)

    def parse_response(self, response):
        """保留结构化错误码，供登记续跑判断请求是否到过 BKBase。"""
        if 300 <= response.status_code < 400:
            raise APIRequestError(module_name=self.module_name, url=self.action, result="Redis registration redirected")
        try:
            return super().parse_response(response)
        except APIRequestError as error:
            # bk_resource 会将 HTTP 错误压成消息。只提取原始错误码，不解析异常文本或保存响应体。
            if response.status_code != 200:
                try:
                    failure = response.json()
                except ValueError:
                    failure = None
                error.gateway_error_code = str(failure.get("code", "")) if isinstance(failure, dict) else ""
            raise


class StorageAssetGet(DatasetResource):
    """读取权威resource_ns；连接口令可能为遮罩，仅供元数据查看。"""

    action = "/v4/res_manage/assets/{project_name}/{sub_type}/{asset_name}/"
    method = "GET"
    url_keys = ["project_name", "sub_type", "asset_name"]
    RequestSerializer = StorageAssetGetRequestSerializer
    ResponseSerializer = ObjectResponseSerializer

    def before_request(self, kwargs):
        """资产存在性只信任原始租户与项目的详情端点，不跟随重定向。"""
        kwargs["allow_redirects"] = False
        return super().before_request(kwargs)

    def parse_response(self, response):
        """区分查询失败和确认资产不存在，避免把网关 404 当成查无资产。"""
        if 300 <= response.status_code < 400:
            raise APIRequestError(module_name=self.module_name, url=self.action, result="Redis asset lookup redirected")
        try:
            return super().parse_response(response)
        except APIRequestError as error:
            payload = error.data
            # 详情接口仅以 HTTP 200 / 业务码 1553002 / data=null 表示资源确实不存在。
            error.asset_not_found = (
                response.status_code == 200
                and payload.get("result") is False
                and str(payload.get("code")) == "1553002"
                and "data" in payload
                and payload["data"] is None
            )
            raise


class StorageAssetList(DatasetResource):
    """按可信项目视角分页读取存储资产，保留本地与共享归属的上游区分。"""

    action = "/v4/res_manage/assets/"
    method = "GET"
    RequestSerializer = StorageAssetListRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class NamespacesList(BkBaseV4Resource):
    """按平台身份枚举当前租户可访问的正式项目。"""

    action = "/v4/tenants/{tenant}/namespaces"
    method = "GET"
    url_keys = ["tenant"]
    RequestSerializer = TenantRequestSerializer
    ResponseSerializer = PayloadResponseSerializer
    requires_platform_auth = True

    def build_header(self, validated_request_data):
        """项目列表路径及租户头采用同一校验上下文。"""
        headers = super().build_header(validated_request_data)
        if not self.use_multi_tenant_mode():
            headers[TENANT_ID_HEADER] = validated_request_data["tenant"]
        return headers


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
        user_tenant = getattr(user, "tenant_id", "")
        if self.use_multi_tenant_mode() and user_tenant and user_tenant != get_bkbase_v4_tenant():
            raise PermissionDenied("BKBase V4 user does not belong to this tenant")
        params.update(bk_app_code=settings.APP_CODE, bk_app_secret=settings.SECRET_KEY, bk_username=username)
        params.update(self.build_auth_args(request))
        return params


class UserNamespacesList(UserBkBaseV4Resource, NamespacesList):
    """以当前请求身份读取该租户的有权项目，不使用旧 MCP scopes。"""


class UserDatasetList(UserBkBaseV4Resource, DatasetList):
    """复用正式 Dataset 列表协议与租户头，认证固定为当前请求用户。"""


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


class _SnapshotResource(BkBaseV4Resource):
    """快照续跑使用的直达证据；同一 SDK 端点的其他调用方也不会跟随重定向。"""

    snapshot_write = False

    @property
    def snapshot_request(self):
        """名称详情由 URL 参数限定，写端必须逐个显式启用。"""
        return self.snapshot_write or (self.method == "GET" and "name" in self.url_keys)

    def before_request(self, kwargs):
        """只信任原始端点，不跟随重定向查询或重发写入。"""
        if self.snapshot_request:
            kwargs["allow_redirects"] = False
        return super().before_request(kwargs)

    def parse_response(self, response):
        """拒绝重定向链；写端路由错误码只取原始 404 JSON 顶层字段。"""
        if self.snapshot_request and (300 <= response.status_code < 400 or response.history):
            raise APIRequestError(module_name=self.module_name, url=self.action, result="Snapshot request redirected")
        try:
            return super().parse_response(response)
        except APIRequestError as error:
            if self.snapshot_request:
                error.http_status = response.status_code
            if self.snapshot_write and response.status_code == 404:
                try:
                    failure = response.json()
                except ValueError:
                    failure = None
                error.gateway_error_code = str(failure.get("code", "")) if isinstance(failure, dict) else ""
            raise


class DataSourceList(BkBaseV4Resource):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datasources/"
    method = "GET"
    url_keys = ["tenant", "namespace"]
    RequestSerializer = ResourceRefRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class DataSourceGet(_SnapshotResource, DataSourceList):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datasources/{name}/"
    url_keys = ["tenant", "namespace", "name"]
    RequestSerializer = NamedResourceRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DataSourceCreate(_SnapshotResource, DataSourceList):
    """创建 DataSource；受理不代表 DataId 已就绪。"""

    method = "POST"
    snapshot_write = True
    RequestSerializer = ResourceWriteRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DataConnCreate(DataSourceCreate):
    """创建独立 DataConn；连接可用状态须另行观察。"""

    action = "/v4/tenants/{tenant}/namespaces/{namespace}/dataconns/"


class UserDataSourceList(UserBkBaseV4Resource, DataSourceList):
    """同一路由使用用户身份，列表范围由上游控制。"""


class UserDataSourceGet(UserBkBaseV4Resource, DataSourceGet):
    """同一路由个人详情，Service先验证可见范围。"""


class DataSourceUpdate(DataSourceGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datasources/{name}/"
    method = "PUT"
    snapshot_write = True
    RequestSerializer = NamedResourceWriteRequestSerializer


class DataConnGet(DataSourceGet):
    """读取Source显式关联的已有PULL连接。"""

    action = "/v4/tenants/{tenant}/namespaces/{namespace}/dataconns/{name}/"


class DataConnUpdate(DataConnGet):
    """全量更新已有连接；密码原文或原密文的保存规则由平台处理。"""

    method = "PUT"
    RequestSerializer = NamedResourceWriteRequestSerializer


class DataSourceNotifies(DatasetResource):
    """读取Source/Flow通知配置；首次GET可能生成对象的默认配置。"""

    action = "/v4/databus/data_source/notifies/"
    method = "GET"
    RequestSerializer = NotifyGetRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DataSourceNotifiesUpdate(DataSourceNotifies):
    """更新完整通知配置，tenant仅进入可信租户请求头。"""

    method = "PUT"
    RequestSerializer = NotifyUpdateRequestSerializer


class DataIdTail(BkBaseV4Resource):
    action = "/v4/namespaces/{namespace}/dataids/{name}/tail_kafka/"
    method = "GET"
    url_keys = ["namespace", "name"]
    RequestSerializer = DataIdTailRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class DataIdGet(BkBaseV4Resource):
    """读取通用资源详情；无tenant路径的使用范围由Service限定。"""

    action = "/v4/namespaces/{namespace}/dataids/{name}/"
    method = "GET"
    url_keys = ["namespace", "name"]
    RequestSerializer = DataIdTailRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class ResultTableResourceGet(DataIdGet):
    """读取正式ResultTable资源，区别于逻辑ID的MCP元数据。"""

    action = "/v4/namespaces/{namespace}/resulttables/{name}/"


class CleanDebug(BkBaseV4Resource):
    """执行无资源副作用的V4清洗预览，业务层检查内层执行状态。"""

    action = "/v4/databus/clean/debug/"
    method = "POST"
    RequestSerializer = CleanDebugRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class CleanGet(_SnapshotResource):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/cleans/{name}/"
    method = "GET"
    url_keys = ["tenant", "namespace", "name"]
    RequestSerializer = NamedResourceRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class CleanList(CleanGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/cleans/"
    url_keys = ["tenant", "namespace"]
    RequestSerializer = ResourceRefRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class CleanCreate(CleanGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/cleans/"
    method = "POST"
    snapshot_write = True
    url_keys = ["tenant", "namespace"]
    RequestSerializer = ResourceWriteRequestSerializer


class CleanUpdate(CleanGet):
    method = "PUT"
    RequestSerializer = NamedResourceWriteRequestSerializer


class CleanDelete(CleanGet):
    method = "DELETE"
    ResponseSerializer = None


class DataStorageGet(_SnapshotResource):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/{name}/"
    method = "GET"
    url_keys = ["tenant", "namespace", "name"]
    RequestSerializer = NamedResourceRequestSerializer
    ResponseSerializer = ObjectResponseSerializer


class DataStorageList(DataStorageGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/"
    url_keys = ["tenant", "namespace"]
    RequestSerializer = ResourceRefRequestSerializer
    ResponseSerializer = PayloadResponseSerializer


class DataStorageCreate(DataStorageGet):
    action = "/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/"
    method = "POST"
    snapshot_write = True
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

    def before_request(self, kwargs):
        """完整写入不跟随重定向，避免307/308在客户端重复发送PUT。"""
        kwargs["allow_redirects"] = False
        return super().before_request(kwargs)

    def parse_response(self, response):
        """仅文档化成功凭证证明保存；重定向、裸对象或矛盾包裹均未决。"""
        if 300 <= response.status_code < 400:
            raise APIRequestError(module_name=self.module_name, url=self.action, result="Flow PUT redirected")
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("result") is not True or payload.get("code") != "00":
            raise APIRequestError(
                module_name=self.module_name, url=self.action, result="Flow PUT receipt is not confirmed"
            )
        return super().parse_response(response)


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
