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
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div
    v-if="parameter.length"
    class="render-field">
    <div class="field-header-row">
      <div class="field-id">
        #
      </div>
      <div class="field-key">
        {{ t('方案输入字段') }}
      </div>
      <div
        class="field-value"
        style="display: flex;padding-left: 16px; align-items: center;">
        {{ t('参数值') }}
      </div>
    </div>
    <template
      v-for="(fieldItem, fieldIndex) in parameter"
      :key="fieldIndex">
      <div class="field-row">
        <div class="field-id">
          {{ fieldIndex + 1 }}
        </div>
        <div class="field-key">
          <span class="field-type">{{ fieldItem.value_type }}</span>
          <span
            v-bk-tooltips="{ content: fieldItem.description || fieldItem.variable_alias }"
            class="field-key-text">
            {{ fieldItem.variable_name }}（{{ fieldItem.variable_alias }}）
          </span>
          <span
            v-if="fieldItem.properties?.is_required"
            class="field-required">*</span>
        </div>
        <div class="field-value">
          <field-input
            ref="fieldItemRef"
            v-model="fieldItem.variable_value"
            :required="fieldItem.properties?.is_required"
            theme="background" />
        </div>
      </div>
    </template>
  </div>
  <model-empty v-else />
</template>
<script setup lang="ts">
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type ControlModel from '@model/control/control';

  import FieldInput from '../components/field-input.vue';
  import ModelEmpty from '../components/model-empty.vue';

  interface Props {
    controlDetail: ControlModel;
  }

  interface Exposes {
    getValue: () => Promise<any>;
    getFields: () => Array<ParameterItem>;
    setConfigs: (configs: Array<ParameterItem>) => void;
    clearFields: () => void;
  }

  interface ParameterItem {
    variable_name: string,
    variable_alias: string,
    variable_type: string,
    value_type: string,
    variable_value: string,
    description: string,
    properties: {
      is_required: boolean,
    },
    default_value?: string,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const fieldItemRef = ref();
  let parameterData:Array<ParameterItem> = []; // 编辑获取的数据
  const parameter = ref<Array<ParameterItem>>([]);
  watch(() => props.controlDetail, (val) => {
    parameter.value = val?.variable_config?.parameter || [];
    if (parameter.value.length) {
      parameter.value = parameter.value.map((item, index) => {
        // 创建一个新的item
        const ParameterItem = { ...item };
        // 如果有编辑数据，填充
        if (parameterData.length && parameterData[index].variable_value) {
          ParameterItem.variable_value = parameterData[index].variable_value;
        } else {
          // 没有编辑数据，获取默认值
          ParameterItem.variable_value = ParameterItem.default_value || '';
        }
        return ParameterItem;
      });
    }
  });

  defineExpose<Exposes>({
    getValue() {
      return Promise.all((fieldItemRef.value as { getValue: () => any }[])?.map(item => item.getValue()));
    },
    getFields() {
      const res = parameter.value.reduce((res: Array<ParameterItem>, item: ParameterItem) => {
        if (item.variable_name) {
          res.push({
            variable_name: item.variable_name,
            variable_alias: item.variable_alias,
            variable_type: item.variable_type,
            value_type: item.value_type,
            variable_value: item.variable_value,
            description: item.description,
            properties: item.properties,
          });
        }
        return res;
      }, []);
      return res;
    },
    setConfigs(configs: Array<ParameterItem>) {
      parameterData = configs;
    },
    clearFields() {
      if (!fieldItemRef.value) return;
      (fieldItemRef.value as { clearFields: () => void }[]).map(item => item.clearFields());
    },
  });
</script>
<style lang="postcss" scoped>
.render-field {
  display: flex;
  min-width: 640px;
  overflow: hidden;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-id {
    width: 40px;
    text-align: center;
    background: #fafbfd;
    border-right: 1px solid #dcdee5;
  }

  .field-header-row {
    display: flex;
    height: 42px;
    font-size: 12px;
    line-height: 40px;
    color: #313238;
    background: #f0f1f5;

    .field-key,
    .field-id {
      background: #f0f1f5;
    }
  }

  .field-row {
    display: flex;
    overflow: hidden;
    font-size: 12px;
    line-height: 42px;
    color: #63656e;
    border-top: 1px solid #dcdee5;
  }

  .field-key {
    position: relative;
    display: flex;
    height: 40px;
    padding-left: 16px;
    background: #fafbfd;
    align-items: center;
    flex: 1 0 340px;

    .field-key-text {
      line-height: 20px;
      cursor: pointer;
      border-bottom: 1px dashed rgb(196 198 204)
    }

    .field-type {
      display: inline-block;
      padding: 0 10px;
      margin-right: 4px;
      line-height: 21px;
      color: #3a84ff;
      background: #e1ecff;
      border-radius: 10px;
    }

    .field-required {
      margin-right: 10px;
      margin-left: auto;
      color: #ea3636;
    }
  }

  .field-value {
    display: flex;
    align-items: center;
    overflow: hidden;
    border-left: 1px solid #dcdee5;
    flex: 1 1 320px;
  }

}
</style>
