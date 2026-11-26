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

type ManualEventField = {
  field_name?: string;
  display_name?: string;
  is_show?: boolean;
  map_config?: {
    source_field?: string;
    target_value?: string;
  };
};

const fieldKey = (value?: string) => (value || '').trim();

const referencedByBasicInfo = (basicFields: ManualEventField[] = []) => {
  const names = new Set<string>();
  basicFields.forEach((item) => {
    const source = fieldKey(item.map_config?.source_field);
    if (source) names.add(source);
  });
  return names;
};

export const selectManualEventFields = <T extends ManualEventField>(
  dataFields: T[] = [],
  basicFields: ManualEventField[] = [],
): T[] => {
  const referenced = referencedByBasicInfo(basicFields);
  const seen = new Set<string>();
  return dataFields.filter((field) => {
    const name = fieldKey(field.field_name);
    const displayName = fieldKey(field.display_name);
    const included = Boolean(field.is_show)
      || (name !== '' && referenced.has(name))
      || (displayName !== '' && referenced.has(displayName));
    if (!included) return false;
    const key = name || displayName;
    if (key && seen.has(key)) return false;
    if (key) seen.add(key);
    return true;
  });
};
