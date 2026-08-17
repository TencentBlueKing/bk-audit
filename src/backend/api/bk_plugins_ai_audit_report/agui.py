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

import re


class AuditReportFinalAnswerExtractor:
    """审计报告专用：从完整 AG-UI assistant 正文提取 <final_answer>。"""

    final_answer_pattern = re.compile(r"<final_answer>(.*?)</final_answer>", re.DOTALL)
    final_answer_tag_pattern = re.compile(r"</?\s*final_answer\b[^>]*>")

    def extract(self, content: str) -> tuple[str, str]:
        matches = list(self.final_answer_pattern.finditer(content))
        tag_count = len(self.final_answer_tag_pattern.findall(content))
        if tag_count != len(matches) * 2:
            return "", "最终 assistant 消息包含不完整的 <final_answer>"
        if tag_count:
            final_content = matches[-1].group(1).strip()
            if not final_content:
                return "", "<final_answer> 正文为空"
            return final_content, ""
        if "<final_answer" in content or "</final_answer>" in content:
            return "", "最终 assistant 消息不包含完整的 <final_answer>"
        if not content.strip():
            return "", "最终 assistant 消息正文为空"
        return content, ""
