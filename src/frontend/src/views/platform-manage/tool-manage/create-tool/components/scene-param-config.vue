<!--
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
  specific language governing permissions and limitations
  under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the product delivered to anyone in the future.
-->
<template>
  <div
    v-if="configList.length > 0"
    class="scene-param-config">
    <div
      v-for="item in configList"
      :key="item.key"
      class="param-config-block">
      <!-- 区块标题 -->
      <div class="block-title">
        {{ item.name }}
      </div>

      <!-- 覆盖参数默认值 -->
      <div class="form-row">
        <label class="form-label">{{ t('覆盖参数默认值') }}</label>
        <div class="form-control">
          <bk-select
            :clearable="false"
            :model-value="item.override_keys"
            multiple
            :placeholder="t('请选择需要覆盖的参数')"
            @change="(val: string[]) => handleOverrideChange(item, val)">
            <bk-option
              v-for="param in inputVariableList"
              :id="param.raw_name"
              :key="param.raw_name"
              :name="param.display_name || param.raw_name" />
          </bk-select>
        </div>
      </div>

      <!-- 参数表格：仅参数名 + 默认值 两列 -->
      <bk-table
        v-if="getTableData(item).length > 0"
        class="param-table"
        :data="getTableData(item)"
        :header-border="false"
        :outer-border="false">
        <bk-table-column
          :label="t('参数名')"
          min-width="150"
          prop="display_name">
          <template #default="{ row }">
            {{ row.display_name || row.raw_name }}
          </template>
        </bk-table-column>
        <bk-table-column
          :label="t('默认值')"
          min-width="200">
          <template #default="{ row }">
            <bk-input
              :model-value="getOverrideValue(item, row.raw_name)"
              :placeholder="t('请输入默认值')"
              @change="(val: any) => handleDefaultValueChange(item, row.raw_name, val)" />
          </template>
        </bk-table-column>
      </bk-table>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { SceneParamOverride, FormData } from '../types';

  interface ConfigItem {
    key: string;             // scene-{id} 或 system-{id}
    id: number;
    name: string;
    type: 'scene' | 'system';
    override_keys: string[];
    default_values: Record<string, any>;
  }

  interface InputVarItem {
    raw_name: string;
    display_name: string;
    description?: string;
    required?: boolean;
    field_category?: string;
    default_value?: any;
  }

  const props = defineProps<{
    formData: FormData;
    selectedScenes: Array<{ id: number; name: string }>;
    selectedSystems: Array<{ id: number; name: string }>;
    inputVariables: InputVarItem[];
  }>();

  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    (e: 'update:paramOverrides', value: Record<string, SceneParamOverride>): void;
  }>();

  const { t } = useI18n();

  const inputVariableList = computed(() => props.inputVariables || []);

  // 构建配置列表：每个选中的场景/系统对应一个配置区块
  const configList = computed<ConfigItem[]>(() => {
    const list: ConfigItem[] = [];
    const overrides = props.formData.scene_param_overrides || {};

    for (const s of props.selectedScenes) {
      const key = `scene-${s.id}`;
      const existing = overrides[key];
      list.push({
        key,
        id: s.id,
        name: s.name,
        type: 'scene',
        override_keys: existing?.override_param_keys || [],
        default_values: existing?.param_default_values || {},
      });
    }

    for (const s of props.selectedSystems) {
      const key = `system-${s.id}`;
      const existing = overrides[key];
      list.push({
        key,
        id: s.id,
        name: s.name,
        type: 'system',
        override_keys: existing?.override_param_keys || [],
        default_values: existing?.param_default_values || {},
      });
    }

    return list;
  });

  // 获取某个区块的表格数据：只展示已选中覆盖的参数
  const getTableData = (item: ConfigItem) => {
    if (!item.override_keys || item.override_keys.length === 0) return [];
    return item.override_keys.map((key) => {
      const found = inputVariableList.value.find(v => v.raw_name === key);
      return found || { raw_name: key, display_name: key, default_value: '' };
    });
  };

  // 获取某参数在某个区块中的覆盖值
  const getOverrideValue = (item: ConfigItem, rawName: string) => item.default_values[rawName] ?? '';

  // 覆盖参数选择变更
  const handleOverrideChange = (item: ConfigItem, keys: string[]) => {
    /* eslint-disable no-param-reassign */
    item.override_keys = keys;
    // 清理不再选中的参数的默认值
    const newValues: Record<string, any> = {};
    for (const k of keys) {
      if (item.default_values[k] !== undefined) {
        newValues[k] = item.default_values[k];
      }
    }
    item.default_values = newValues;
    /* eslint-enable no-param-reassign */
    emitChange();
  };

  // 默认值输入变更
  const handleDefaultValueChange = (item: ConfigItem, rawName: string, value: any) => {
    /* eslint-disable no-param-reassign */
    item.default_values[rawName] = value;
    /* eslint-enable no-param-reassign */
    emitChange();
  };

  // 向外发出变更事件（仅用户主动操作时触发，避免无限递归）
  const emitChange = () => {
    const result: Record<string, SceneParamOverride> = {};
    for (const item of configList.value) {
      result[item.key] = {
        target_id: item.id,
        target_type: item.type,
        target_name: item.name,
        override_param_keys: [...item.override_keys],
        param_default_values: { ...item.default_values },
      };
    }
    emit('update:paramOverrides', result);
  };
</script>

<style lang="postcss" scoped>
  .scene-param-config {
    margin-top: 16px;
  }

  .param-config-block {
    padding: 16px 20px;
    margin-bottom: 16px;
    background-color: #fafbfd;
    border-radius: 2px;

    .block-title {
      margin-bottom: 12px;
      font-size: 13px;
      font-weight: 600;
      color: #313238;
    }
  }

  .form-row {
    display: flex;
    flex-direction: column;
    margin-bottom: 12px;

    .form-label {
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
      flex-shrink: 0;
    }

    .form-control {
      max-width: 560px;
    }
  }

  .param-config-block .param-table {
    :deep(.bk-table-header th) {
      background-color: #f5f7fa !important;
    }

    :deep(.bk-table-body tr:hover td) {
      background-color: #fff;
    }
  }
</style>
