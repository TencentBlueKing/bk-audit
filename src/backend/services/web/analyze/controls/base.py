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

from django.utils.module_loading import import_string

from services.web.analyze.models import Control
from services.web.strategy_v2.models import Strategy


class Controller:
    """
    Control Strategy and Event
    """

    def __new__(cls, strategy_id: int, *args, **kwargs) -> "Controller":
        # check child
        if cls.__name__ != Controller.__name__:
            return super().__new__(cls)
        # load control
        control_id = Strategy.objects.get(strategy_id=strategy_id).control_id
        control_type_id = Control.objects.get(control_id=control_id).control_type_id
        # import controller
        controller_path = "services.web.analyze.controls.{}.{}Controller".format(
            control_type_id.lower(), control_type_id
        )
        controller_class = import_string(controller_path)
        # init controller
        return controller_class(strategy_id)

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
