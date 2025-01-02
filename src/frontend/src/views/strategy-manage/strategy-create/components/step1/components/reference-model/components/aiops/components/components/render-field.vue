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
  <div class="render-field">
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
        {{ t('映射值') }}
        <audit-icon
          v-bk-tooltips="{
            content: t('数据源中与方案输入参数匹配的字段'),
          }"
          style="margin-left: 8px;font-size: 14px;color: #c4c6cc;"
          type="info-fill" />
      </div>
    </div>
    <template
      v-for="(fieldItem, fieldIndex) in renderData"
      :key="fieldIndex">
      <div class="field-row">
        <div class="field-id">
          {{ fieldIndex + 1 }}
        </div>
        <div class="field-key">
          <span class="field-type">{{ fieldItem.field_type }}</span>
          <span style="line-height: 20px;">
            {{ fieldItem.field_name }}（{{ fieldItem.field_alias }}）
          </span>
          <span
            v-if="fieldItem.properties?.is_required"
            class="field-required">*</span>
        </div>
        <div class="field-value field-value-content">
          <div style="width: 100%;height: 100%;">
            <field-select
              ref="fieldItemRef"
              :default-value="fieldItem.source_field || ''"
              :field-name="fieldItem.field_name"
              :required="fieldItem.properties?.is_required"
              :rt-fields="rtFields"
              theme="background"
              @change="(value: string) => handleChange(value, fieldItem)"
              @init="(value: string) => handleInit(value, fieldItem)" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
<script lang="ts">
  export interface ResourceFieldType {
    label: string;
    value: string;
    field_type?: string;
  }
</script>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import AiopPlanModel from '@model/strategy/aiops-plan';

  import FieldSelect from './field-select.vue';


  interface Props {
    data: Record<string, any>[];
    rtFields: Array<ResourceFieldType>;
    configs: Record<string, any>[];
    triggerError?: boolean
  }

  interface Exposes {
    getValue: () => Promise<any>;
    getFields: () => Record<string, any>;
    clearFields: () => void;
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const fieldItemRef = ref();
  const renderData = computed(() => {
    const genKey = (fieldConfig: Record<string, any>) => `${[fieldConfig.field_name]}(${fieldConfig.field_alias})`;
    const fieldNameConfigMap = props.configs.reduce((result, item) => ({
      ...result,
      [genKey(item)]: item,
    }), {});
    return _.filter(props.data, (item) => {
      const config = fieldNameConfigMap[genKey(item)];
      if (!config || !config.roles) {
        return false;
      }
      return AiopPlanModel.checkHideInputField(config);
    });
  });

  let localData: Props['data'];


  const handleChange = (value: string | string[], fieldItem: Record<string, any>) => {
    const targetIndex = _.findIndex(props.data, item => item === fieldItem);
    if (targetIndex > -1) {
      localData[targetIndex].source_field = value;
    }
    window.changeConfirm = true;
  };

  // // 初始化填充
  const handleInit = (value: string | string[], fieldItem: Record<string, any>) => {
    const targetIndex = _.findIndex(props.data, item => item === fieldItem);
    if (targetIndex > -1) {
      localData[targetIndex].source_field = value;
    }
  };


  watch(() => props.data, () => {
    localData = _.cloneDeep(props.data);
  }, {
    immediate: true,
  });
  watch(() => [fieldItemRef.value, props.triggerError], () => {
    if (props.triggerError && fieldItemRef.value) {
      Promise.all((fieldItemRef.value as { getValue: () => any }[]).map(item => item.getValue()));
    }
  }, {
    immediate: true,
    deep: true,
  });
  defineExpose<Exposes>({
    clearFields() {
      if (!fieldItemRef.value) return;
      (fieldItemRef.value as { clearFields: () => void }[]).map(item => item.clearFields());
    },
    getValue() {
      return Promise.all((fieldItemRef.value as { getValue: () => any }[])?.map(item => item.getValue()));
    },
    getFields() {
      const res = localData.reduce((res, item) => {
        if (item.source_field) {
          res[res.length] = {
            field_name: item.field_name,
            source_field: item.source_field,
          };
        }
        return res;
      }, []);
      return res;
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

    .field-type {
      display: inline-block;
      padding: 0 10px;
      margin-right: 4px;
      line-height: 21px;
      color: #3a84ff;
      background: #e1ecff;
      border-radius: 10px;
    }

    .field-type-icon {
      width: 46px;
      margin-right: 6px;
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

  .field-value-content {
    background-color: #fff;
  }
}
</style>
