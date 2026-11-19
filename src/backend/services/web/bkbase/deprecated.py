"""保留V3模型能力边界，V4不再调用退役的方案接口。"""
from bk_resource import api

from services.web.bkbase.common import get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion
from services.web.bkbase.exceptions import BKBaseCapabilityDeprecated


def model_supported():
    """模型审计不属于V4保留业务。"""
    return get_bkbase_version() == BKBaseVersion.V3


def require_model_support():
    if not model_supported():
        raise BKBaseCapabilityDeprecated()


def check_aiops(*args, **kwargs):
    return api.bk_base.check_aiops(*args, **kwargs) if model_supported() else False


def get_scene_plans(*args, **kwargs):
    require_model_support()
    return api.bk_base.get_scene_plans(*args, **kwargs)


def get_plan_detail(*args, **kwargs):
    require_model_support()
    return api.bk_base.get_plan_detail(*args, **kwargs)
