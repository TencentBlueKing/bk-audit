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
      <div class="block-header">
        {{ item.name }}
      </div>

      <div class="block-body">
        <!-- 覆盖参数默认值：独立一行，宽度与参数名列对齐 -->
        <div class="override-section">
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
                :name="getParamName(param)" />
            </bk-select>
          </div>
        </div>

        <!-- 参数表格：参数名 + 默认值均分剩余宽度 -->
        <div
          v-if="getTableData(item).length > 0"
          class="render-field">
          <div class="field-header-row">
            <div class="field-value col-name">
              {{ t('参数名') }}
            </div>
            <div class="field-value col-default">
              {{ t('默认值') }}
            </div>
            <div class="field-value field-operation col-action" />
          </div>
          <div
            v-for="row in getTableData(item)"
            :key="row.raw_name"
            class="field-row">
            <div class="field-value col-name">
              <span class="param-name-text">{{ getParamName(row) }}</span>
            </div>
            <div class="field-value col-default">
              <bk-input
                :model-value="getOverrideValue(item, row.raw_name)"
                :placeholder="t('请输入')"
                @change="(val: any) => handleDefaultValueChange(item, row.raw_name, val)" />
            </div>
            <div class="field-value field-operation col-action">
              <audit-icon
                class="reduce-fill field-icon"
                type="reduce-fill"
                @click="handleRemoveParam(item, row.raw_name)" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { SceneParamOverride, FormData } from '../types';

  interface ConfigItem {
    key: string;             // scene-{id} 或 system-{id}
    id: number | string;
    name: string;
    type: 'scene' | 'system';
    override_keys: string[];
    default_values: Record<string, any>;
  }

  interface InputVarItem {
    raw_name: string;
    display_name: string;
    var_name?: string;
    description?: string;
    required?: boolean;
    field_category?: string;
    default_value?: any;
    raw_default_value?: any;
  }

  const props = defineProps<{
    formData: FormData;
    selectedScenes: Array<{ id: number; name: string }>;
    selectedSystems: Array<{ id: string; name: string }>;
    inputVariables: InputVarItem[];
  }>();

  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    (e: 'update:paramOverrides', value: Record<string, SceneParamOverride>): void;
  }>();

  const { t } = useI18n();

  const inputVariableList = computed(() => props.inputVariables || []);

  // 展示第一步「参数名」：API 工具为 var_name，数据查询等为 raw_name
  const getParamName = (param: Pick<InputVarItem, 'raw_name' | 'var_name'>) => param.var_name || param.raw_name;

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

  // 从第一步工具配置中读取参数原始默认值
  const getParamOriginalDefault = (rawName: string) => {
    const param = inputVariableList.value.find(v => v.raw_name === rawName);
    if (!param) return '';
    if (param.default_value !== undefined && param.default_value !== '') {
      return param.default_value;
    }
    if (param.raw_default_value !== undefined && param.raw_default_value !== '') {
      return param.raw_default_value;
    }
    return param.default_value ?? '';
  };

  // 覆盖参数选择变更
  const handleOverrideChange = (item: ConfigItem, keys: string[]) => {
    /* eslint-disable no-param-reassign */
    item.override_keys = keys;
    // 清理不再选中的参数；新选中的参数自动代入第一步配置的默认值
    const newValues: Record<string, any> = {};
    for (const k of keys) {
      if (item.default_values[k] !== undefined) {
        newValues[k] = item.default_values[k];
      } else {
        newValues[k] = getParamOriginalDefault(k);
      }
    }
    item.default_values = newValues;
    /* eslint-enable no-param-reassign */
    emitChange();
  };

  // 移除单个覆盖参数
  const handleRemoveParam = (item: ConfigItem, rawName: string) => {
    const keys = item.override_keys.filter(k => k !== rawName);
    handleOverrideChange(item, keys);
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
    --param-action-col-width: 50px;
    --param-data-col-width: calc((100% - var(--param-action-col-width)) / 2);

    margin-top: 16px;
  }

  .param-config-block {
    margin-bottom: 16px;
    overflow: hidden;
    background-color: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .block-header {
    height: 42px;
    padding: 0 16px;
    font-size: 12px;
    font-weight: 600;
    line-height: 42px;
    color: #313238;
    background-color: #f0f1f5;
    box-shadow: 0 1px 0 0 #dcdee5;
  }

  .block-body {
    padding: 16px;
    background-color: #fafbfd;
  }

  .override-section {
    margin-bottom: 12px;

    .form-label {
      display: block;
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
    }

    /* 与下方表格参数名列同宽 */
    .form-control {
      width: var(--param-data-col-width);
      max-width: var(--param-data-col-width);
    }
  }

  .render-field {
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    user-select: none;
  }

  .field-header-row,
  .field-row {
    display: flex;
  }

  .col-name,
  .col-default {
    flex: 1 1 0;
    min-width: 0;
  }

  .col-action {
    flex: 0 0 var(--param-action-col-width);
    width: var(--param-action-col-width);
  }

  .field-header-row {
    height: 42px;
    font-size: 12px;
    line-height: 40px;
    color: #313238;
    background: #f0f1f5;

    .col-name,
    .col-default,
    .col-action {
      height: 42px;
      padding-left: 8px;
    }

    .col-default,
    .col-action {
      border-left: 1px solid #dcdee5;
    }

    .col-action {
      background: #f0f1f5;
    }
  }

  .field-row {
    overflow: hidden;
    font-size: 12px;
    line-height: 42px;
    color: #63656e;
    border-right: 1px solid #dcdee5;
    border-bottom: 1px solid #dcdee5;
    transition: background-color .2s;

    &:hover {
      color: #313238;
      background: #eff5ff;
    }

    .col-name,
    .col-default,
    .col-action {
      display: flex;
      height: 42px;
      overflow: hidden;
      align-items: center;
    }

    .col-name {
      background: #fafbfd;
    }

    .col-default {
      background: #fff;
      border-left: 1px solid #dcdee5;
    }

    .col-action {
      background: #fafbfd;
      border-left: 1px solid #dcdee5;
    }
  }

  :deep(.field-row:hover .field-value) {
    background: #eff5ff !important;
  }

  :deep(.field-row:hover .bk-input),
  :deep(.field-row:hover .bk-input .bk-input--text),
  :deep(.field-row:hover .bk-input input) {
    color: #313238 !important;
    background: #eff5ff !important;
    border-color: transparent !important;
    transition: none !important;
  }

  :deep(.field-value) {
    .param-name-text {
      width: 100%;
      padding: 0 8px;
      overflow: hidden;
      font-size: 12px;
      color: #4d4f56;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .bk-input {
      width: 100%;
      height: 42px !important;
      border: none;
      border-radius: 0;
    }

    .bk-input.is-focused:not(.is-readonly) {
      border: 1px solid #3a84ff;
      outline: 0;
      box-shadow: 0 0 3px #a3c5fd;
    }
  }

  .field-operation {
    justify-content: center;
    background: #fafbfd;
  }

  .field-header-row .field-operation {
    background: #f0f1f5;
  }

  .field-icon {
    font-size: 14px;
    color: #c4c6cc;
    cursor: pointer;

    &:hover {
      color: #ea3636;
    }
  }
</style>
