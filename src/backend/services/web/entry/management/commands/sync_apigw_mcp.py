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

from apigw_manager.apigw.command import SyncCommand


class Command(SyncCommand):
    """同步 APIGW Stage MCP Server 配置，支持 --stage 过滤"""

    default_namespace = "stages"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--stage", nargs="+", default=[], help="只同步指定 stage 的 MCP 配置")

    def handle(self, *args, **kwargs):
        self._allowed_stages = kwargs.pop("stage", [])
        super().handle(*args, **kwargs)

    def get_definition(self, define, file, namespace, **kwargs):
        definition = self.load_definition(define, file, **kwargs)
        if definition is None:
            return {}
        if definition.spec_version != 2:
            raise ValueError("sync apigw_stage_mcp_servers only support spec_version: 2")
        return super().get_definition(define, file, namespace, **kwargs)

    def do(self, manager, definition, *args, **kwargs):
        for stage_definition in definition:
            if self._allowed_stages and stage_definition.get("name") not in self._allowed_stages:
                continue
            result = manager.sync_stage_mcp_servers(**stage_definition)
            for mcp_sync_result in result.get("data", []):
                print(
                    "API gateway stage mcp servers synchronization completed [ id:%s,name:%s,action:%s ]"
                    % (mcp_sync_result["id"], mcp_sync_result["name"], mcp_sync_result["action"])
                )
