/*
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
*/
import type {
  AiAttachmentOutputData,
  AiFieldStatisticsOutput,
} from './types';

const asRecord = (output?: AiAttachmentOutputData | null): Record<string, any> | null => {
  if (!output || typeof output !== 'object' || Array.isArray(output)) return null;
  return output as Record<string, any>;
};

/** output_data 按类型可能是原文字符串或统计语义包，取 markdown 前先收窄成对象 */
export const attachmentMarkdown = (output?: AiAttachmentOutputData | null): string => {
  const record = asRecord(output);
  return typeof record?.markdown === 'string' ? record.markdown : '';
};

/** AI_STATISTICS 的标签内原文；后端保证非空，拿不到就按解析失败处理 */
export const attachmentStatisticsContent = (output?: AiAttachmentOutputData | null): string => {
  const record = asRecord(output);
  return typeof record?.content === 'string' ? record.content : '';
};

/** FIELD_STATISTICS 固定语义包；缺三大块之一视为产物不可用 */
export const asFieldStatisticsOutput = (
  output?: AiAttachmentOutputData | null,
): AiFieldStatisticsOutput | null => {
  const record = asRecord(output);
  if (!record) return null;
  const hasPackage = Boolean(record.overview) && Boolean(record.distribution) && Boolean(record.time_series);
  return hasPackage ? record as unknown as AiFieldStatisticsOutput : null;
};
