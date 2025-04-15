# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc
import time
from functools import cached_property

from bk_resource import api
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext

from apps.notice.handlers import ErrorMsgHandler
from core.lock import lock
from services.web.analyze.constants import (
    BKBASE_FLOW_CONSUMING_MODE,
    BaseControlTypeChoices,
    FlowNodeStatusChoices,
    FlowStatusToggleChoices,
)
from services.web.analyze.models import Control
from services.web.analyze.tasks import (
    call_controller,
    check_flow_status,
    toggle_monitor,
)
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.exceptions import StrategyStatusUnexpected
from services.web.strategy_v2.models import Strategy


class BaseControl(abc.ABC):
    def __init__(self, strategy_id: int):
        self.strategy: Strategy = Strategy.objects.get(strategy_id=strategy_id)

    @abc.abstractmethod
    def create(self) -> None:
        """
        create real bkm strategy / bkbase flow
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def update(self) -> None:
        """
        update real bkm strategy / bkbase flow
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def delete(self) -> None:
        """
        delete real bkm strategy / bkbase flow
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def enable(self) -> None:
        """
        enable real bkm strategy / bkbase flow
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def disabled(self) -> None:
        """
        disable real bkm strategy / bkbase flow
        """

        raise NotImplementedError()


class Controller(BaseControl, abc.ABC):
    """
    Control Strategy and Event
    """

    @classmethod
    def get_typed_controller(cls, strategy_id: int, *args, **kwargs) -> "Controller":
        # load control
        control_id = Strategy.objects.get(strategy_id=strategy_id).control_id
        control_type_id = Control.objects.get(control_id=control_id).control_type_id
        # import controller
        controller_path = "services.web.analyze.controls.{}.{}Controller".format(
            control_type_id.lower(), control_type_id
        )
        controller_class = import_string(controller_path)
        # init controller
        return controller_class(strategy_id, *args, **kwargs)


class BkbaseFlowController(BaseControl, abc.ABC):
    """
    Control Bkbase Flow
    """

    @property
    @abc.abstractmethod
    def base_control_type(self) -> BaseControlTypeChoices:
        """
        基础控件类型
        """

        raise NotImplementedError()

    @cached_property
    def flow_name(self) -> str:
        return f"{self.strategy.strategy_type}-{self.strategy.strategy_id}-{str(time.time_ns())}"

    def check_flow_status(self, strategy_id: int, success_status: str, failed_status: str, other_status: str):
        """
        check bkbase flow status
        """

        return check_flow_status.delay(strategy_id, success_status, failed_status, other_status)

    def build_update_flow_params(self) -> dict:
        """
        构建更新流参数
        """

        return {
            "flow_id": self.strategy.backend_data.get("flow_id"),
            "consuming_mode": BKBASE_FLOW_CONSUMING_MODE,
            "resource_sets": {
                "stream": settings.BKBASE_STREAM_RESOURCE_SET_ID,
                "batch": settings.BKBASE_BATCH_RESOURCE_SET_ID,
            },
        }

    def _toggle_strategy(self, status: str, force: bool = False) -> None:
        # update flow
        params = self.build_update_flow_params()
        if not force and (
            not params["flow_id"]
            or self.strategy.status
            in [
                StrategyStatusChoices.STARTING.value,
                StrategyStatusChoices.STOPPING.value,
                StrategyStatusChoices.UPDATING.value,
                StrategyStatusChoices.FAILED.value,
            ]
        ):
            return
        match status:
            case FlowStatusToggleChoices.START.value:
                api.bk_base.start_flow(**params)
                self.strategy.status = StrategyStatusChoices.STARTING
                self.strategy.save(update_record=False, update_fields=["status"])
                toggle_monitor.delay(strategy_id=self.strategy.strategy_id, is_active=True)
                self.check_flow_status(
                    strategy_id=self.strategy.strategy_id,
                    success_status=StrategyStatusChoices.RUNNING,
                    failed_status=StrategyStatusChoices.START_FAILED,
                    other_status=StrategyStatusChoices.STARTING,
                )
            case FlowStatusToggleChoices.RESTART.value:
                api.bk_base.restart_flow(**params)
                self.strategy.status = StrategyStatusChoices.UPDATING
                self.strategy.save(update_record=False, update_fields=["status"])
                toggle_monitor.delay(strategy_id=self.strategy.strategy_id, is_active=True)
                self.check_flow_status(
                    strategy_id=self.strategy.strategy_id,
                    success_status=StrategyStatusChoices.RUNNING,
                    failed_status=StrategyStatusChoices.UPDATE_FAILED,
                    other_status=StrategyStatusChoices.UPDATING,
                )
            case FlowStatusToggleChoices.STOP.value:
                api.bk_base.stop_flow(**params)
                self.strategy.status = StrategyStatusChoices.STOPPING
                self.strategy.save(update_record=False, update_fields=["status"])
                toggle_monitor.delay(strategy_id=self.strategy.strategy_id, is_active=False)
                self.check_flow_status(
                    strategy_id=self.strategy.strategy_id,
                    success_status=StrategyStatusChoices.DISABLED,
                    failed_status=StrategyStatusChoices.STOP_FAILED,
                    other_status=StrategyStatusChoices.STOPPING,
                )
            case _:
                raise StrategyStatusUnexpected()

    def _describe_flow_status(self) -> str:
        """
        获取Flow运行状态
        """

        flow_id = self.strategy.backend_data.get("flow_id")
        if not flow_id:
            return FlowNodeStatusChoices.NO_START
        data = api.bk_base.get_flow_deploy_data(flow_id=flow_id)
        if data:
            return data["flow_status"]
        return FlowNodeStatusChoices.NO_START

    def delete(self) -> None:
        """
        delete bkbase flow: 实际上是停止
        """

        flow_status = self._describe_flow_status()
        if flow_status in [FlowNodeStatusChoices.RUNNING, FlowNodeStatusChoices.FAILED]:
            self._toggle_strategy(FlowStatusToggleChoices.STOP)

    def enable(self, force: bool = False) -> None:
        """
        enable bkbase flow
        """

        flow_status = self._describe_flow_status()
        if flow_status in [FlowNodeStatusChoices.NO_START]:
            self._toggle_strategy(FlowStatusToggleChoices.START, force=force)
        else:
            self._toggle_strategy(FlowStatusToggleChoices.RESTART, force=force)

    def disabled(self, force: bool = False) -> None:
        flow_status = self._describe_flow_status()
        if flow_status in [FlowNodeStatusChoices.RUNNING, FlowNodeStatusChoices.FAILED]:
            self._toggle_strategy(FlowStatusToggleChoices.STOP, force=force)

    def create(self) -> None:
        """
        create bkbase flow
        """

        self.update_or_create(StrategyStatusChoices.STARTING)

    def update(self) -> None:
        """
        update bkbase flow
        """

        self.update_or_create(StrategyStatusChoices.UPDATING)

    def update_or_create(self, status: str):
        self.strategy.status = status
        self.strategy.save(update_record=False, update_fields=["status"])
        call_controller.delay(
            func_name=self._update_or_create.__name__,
            strategy_id=self.strategy.strategy_id,
            base_control_type=self.base_control_type,
            status=status,
        )

    @abc.abstractmethod
    def _update_or_create_bkbase_flow(self) -> bool:
        """
        update or create bkbase flow
        """

        raise NotImplementedError()

    @lock(load_lock_name=lambda self, status: f"{self.__class__.__name__}.update_or_create_{self.strategy.strategy_id}")
    def _update_or_create(self, status: str) -> None:
        try:
            self._update_or_create_bkbase_flow()
            self.enable(force=True)
        except Exception as err:
            if status == StrategyStatusChoices.STARTING:
                self.strategy.status = StrategyStatusChoices.START_FAILED
            elif status == StrategyStatusChoices.UPDATING:
                self.strategy.status = StrategyStatusChoices.UPDATE_FAILED
            else:
                self.strategy.status = StrategyStatusChoices.FAILED
            self.strategy.status_msg = str(err)
            self.strategy.save(update_record=False, update_fields=["status", "status_msg"])
            logger.error("[CreateOrUpdateFlowFailed]\nStrategy ID => %s\nError => %s", self.strategy.strategy_id, err)
            ErrorMsgHandler(
                title=gettext("Create or Update Flow Failed"),
                content=gettext("Strategy ID:\t%s") % self.strategy.strategy_id,
            ).send()
