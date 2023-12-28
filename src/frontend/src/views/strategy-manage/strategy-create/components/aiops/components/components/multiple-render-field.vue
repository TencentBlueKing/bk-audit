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
        class="field-type-row"
        style="display: flex; padding-left: 16px;align-items: center;">
        <span>{{ t('映射值类型') }}</span>
        <audit-icon
          v-bk-tooltips="{
            content: t('由于不同操作对应的拓展字段不同，若需要使用拓展字段作为映射值，映射值类型请选择拓展字段。若不使用拓展字段则映射值类型选为公共字段'),
          }"
          style="margin-left: 8px;font-size: 14px;color: #c4c6cc;"
          type="info-fill" />
      </div>
      <div
        class="field-value"
        style="display: flex;padding-left: 16px; align-items: center;">
        <span>{{ t('映射值') }}</span>
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
          <img
            class="field-type-icon"
            :src="getAssetsFile(`field-type/${fieldItem.field_type}.png`)">
          <span style="line-height: 20px;">
            {{ fieldItem.field_name }}（{{ fieldItem.field_alias }}）
          </span>
          <span
            v-if="fieldItem.properties?.is_required"
            class="field-required">*</span>
        </div>
        <div class="field-type-row">
          <field-select
            ref="fieldItemRef"
            :default-value="fieldItem.mapping_type"
            :field-name="fieldItem.field_name"
            :required="fieldItem.properties?.is_required"
            :rt-fields="commonData.mapping_type"
            theme="background"
            @change="(value: string) => handleMappingTypeChange(value, fieldItem)" />
        </div>
        <div class="field-value field-value-content">
          <div
            v-if="fieldItem.mapping_type === 'action'"
            style="width: 100%; height: 100%;">
            <p
              v-for="(sourceFieldItem, index) in fieldItem.source_field"
              :key="sourceFieldItem"
              class="field-value-line">
              <field-cascader
                ref="fieldItemRef"
                :action-id="actionIdSourceField ? actionIdSourceField[index]?.action_id : ''"
                :default-value="getSourceFieldItemDefault(fieldItem, sourceFieldItem)"
                :field-item="fieldItem"
                :local-data="localData"
                :rt-fields="actionFields"
                :select-action-id-map="selectActionIdMap"
                :system-id="systemId"
                theme="background"
                @change="(value: string[]) => handleChange(index, value, fieldItem)"
                @change-action-id="(val: string) => onActionIdChange(val, fieldItem, index)" />
              <span class="field-option">
                <audit-icon
                  class="option-btn add-btn"
                  type="add-fill"
                  @click="() => handleAddClick(index, fieldItem, true)" />
                <audit-icon
                  class="option-btn reduce-btn"
                  type="reduce-fill"
                  @click="() => handleReduceClick(index, fieldItem)" />
              </span>
            </p>
          </div>
          <div
            v-else
            style="width: 100%;height: 100%;">
            <field-select
              ref="fieldItemRef"
              :default-value="fieldItem.source_field[0]?.source_field || ''"
              :field-name="fieldItem.field_name"
              :required="fieldItem.properties?.is_required"
              :rt-fields="selectRtFields"
              theme="background"
              @change="(value: string) => handleSelectChange(value, fieldItem)" />
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
    field_type: string;
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
  import {
    useRoute,
  } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import AiopPlanModel from '@model/strategy/aiops-plan';

  import useRequest from '@hooks/use-request';

  import getAssetsFile from '@utils/getAssetsFile';

  import FieldCascader from './field-cascader.vue';
  import FieldSelect from './field-select.vue';

  import CommonData from '@/domain/model/strategy/common-data';

  interface Props {
    data: Record<string, any>[];
    configs: Record<string, any>[];
    systemId: string;
    triggerError?: boolean;
  }

  interface Exposes {
    getValue: () => void;
    getFields: () => void;
    clearFields: () => void;
  }
  interface FieldType {
    action_id: string;
    source_field: string;
  }

  const props = defineProps<Props>();

  let localData: Props['data'];

  const { t } = useI18n();
  const route = useRoute();
  const fieldItemRef = ref();
  const actionIdSourceField = ref<Array<FieldType>>([]);
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyEdit';
  const isUpgradeMode = route.name === 'strategyUpgrade';

  const selectActionIdMap = computed(() => {
    if (actionIdSourceField.value) {
      const res = actionIdSourceField.value.reduce((res, item) => {
        if (item.action_id) {
          res[item.action_id] = res[item.action_id] ? res[item.action_id] + 1 : 1;
        }
        return res;
      }, {} as Record<string, number>);
      return res;
    }
    return {};
  });
  const renderData = computed(() => {
    const genKey = (fieldConfig: Record<string, any>) => `${[fieldConfig.field_name]}(${fieldConfig.field_alias})`;
    const fieldNameConfigMap = props.configs.reduce((result, item) => ({
      ...result,
      [genKey(item)]: item,
    }), {});
    const data = _.filter(props.data, (item) => {
      const config = fieldNameConfigMap[genKey(item)];
      if (!config || !config.roles) {
        return false;
      }
      return AiopPlanModel.checkHideInputField(config);
    });
    return data;
  });

  const selectRtFields = computed(() => rtFields.value.map(item => ({
    label: item.description,
    value: item.field_name,
  })));

  const {
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonData(),
    manual: true,
  });
  const {
    data: rtFields,
  } = useRequest(StrategyManageService.fetchStrategyFields, {
    defaultValue: [],
    manual: true,
  });
  const {
    data: actionFields,
    run: fetchStrategyFieldValue,
  } = useRequest(StrategyManageService.fetchStrategyFieldValue, {
    defaultValue: [],
  });

  const getSourceFieldItemDefault = (fieldItem: Record<string, Array<FieldType>>, item: FieldType) => {
    let res: string[] = [];
    if ((isEditMode || isUpgradeMode || isCloneMode) && !actionIdSourceField.value.length) {
      actionIdSourceField.value = fieldItem.source_field.map(item => ({
        action_id: item.action_id,
        source_field: '',
      }));
    }
    if (item.action_id && item.source_field) {
      res = [item.action_id, item.source_field];
    }
    return res;
  };
  const handleMappingTypeChange = (value: string, fieldItem: Record<string, any>) => {
    const targetIndex = _.findIndex(props.data, item => item === fieldItem);
    if (targetIndex < 0) return;
    if (fieldItem.mapping_type !== 'public' && value === 'public') {
      // eslint-disable-next-line no-param-reassign
      fieldItem.source_field = [[]];
      localData[targetIndex].source_field = [[]];
    }
    // eslint-disable-next-line no-param-reassign
    fieldItem.mapping_type = value;
    localData[targetIndex].mapping_type = value;

    // 对操作字段赋值
    if (value === 'action' && actionIdSourceField.value) {
      actionIdSourceField.value.forEach((field, index: number) => {
        if (index !== 0) {
          handleAddClick(index, fieldItem);
        }
      });
    }
    window.changeConfirm = true;
  };

  const handleSelectChange = (value: string, fieldItem: Record<string, any>) => {
    const targetIndex = _.findIndex(props.data, item => item === fieldItem);
    if (targetIndex < 0) return;
    localData[targetIndex].source_field[0].source_field = value;
    window.changeConfirm = true;
  };

  const handleChange = (index: number, value: string[], fieldItem: Record<string, any>) => {
    const targetIndex = _.findIndex(props.data, item => item === fieldItem);
    if (targetIndex < 0) return;
    [localData[targetIndex].source_field[index].action_id] = value;
    if (value.length > 1) {
      [, localData[targetIndex].source_field[index].source_field] = value;
    }
    window.changeConfirm = true;
  };
  const onActionIdChange = (actionId: string, fieldItem: Record<string, any>, fieldIndex: number) => {
    const targetIndex = _.findIndex(props.data, item => item === fieldItem);
    if (targetIndex < 0) return;

    actionIdSourceField.value[fieldIndex] = {
      action_id: actionId,
      source_field: '',
    };
  };

  const handleReduceClick = (index: number, fieldItem: Record<string, any>) => {
    if (fieldItem.source_field.length > 1) {
      fieldItem.source_field.splice(index, 1);
      const targetIndex = _.findIndex(props.data, item => item === fieldItem);
      if (targetIndex < 0) return;
      localData[targetIndex].source_field.splice(index, 1);

      actionIdSourceField.value.splice(index, 1);
      changeAllActionFields(fieldItem, index, false);
    }
  };

  const handleAddClick = (index: number, fieldItem: Record<string, any>, needChangeAll = false) => {
    fieldItem.source_field.splice(index + 1, 0, []);
    const targetIndex = _.findIndex(props.data, item => item === fieldItem);
    if (targetIndex < 0) return;
    localData[targetIndex].source_field.splice(index + 1, 0, []);

    if (needChangeAll) {
      actionIdSourceField.value.splice(index + 1, 0, { action_id: '', source_field: '' });
      changeAllActionFields(fieldItem, index, true);
    }
  };

  const changeAllActionFields = (originItem: Record<string, any>, index: number, add: boolean) => {
    renderData.value.forEach((fieldItem) => {
      if (fieldItem.mapping_type === 'action' && originItem !== fieldItem) {
        if (add) {
          fieldItem.source_field.splice(index + 1, 0, []);
          const targetIndex = _.findIndex(props.data, item => item === fieldItem);
          if (targetIndex < 0) return;
          localData[targetIndex].source_field.splice(index + 1, 0, []);
        } else {
          fieldItem.source_field.splice(index, 1);
          const targetIndex = _.findIndex(props.data, item => item === fieldItem);
          if (targetIndex < 0) return;
          localData[targetIndex].source_field.splice(index, 1);
        }
      }
    });
  };

  watch(() => props.data, () => {
    localData = _.cloneDeep(props.data);
  }, {
    immediate: true,
  });
  watch(() => props.systemId, (data) => {
    if (data) {
      fetchStrategyFieldValue({
        field_name: 'action_id',
        system_id: data,
      });
    }
  }, {
    immediate: true,
  });

  watch(() => [fieldItemRef.value, props.triggerError], () => {
    if (props.triggerError && fieldItemRef.value) {
      Promise.all((fieldItemRef.value as { getValue: () => any }[]).map(item => item.getValue()));
    }
  }, {
    deep: true,
    immediate: true,
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
        if (item.mapping_type
          && item.source_field
          && item.source_field.length
          && item.source_field[0].source_field) {
          res[res.length] = {
            field_name: item.field_name,
            source_field: item.source_field.map((fieldItem: Record<string, any>) => ({
              ...fieldItem,
              mapping_type: item.mapping_type,
            })),
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
    .field-type-row,
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

    /* height: 40px; */
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

  .field-type-row {
    display: flex;
    overflow: hidden;
    background-color: #fff;
    border-left: 1px solid #dcdee5;
    align-items: center;
    flex: 1 1 80px;

    .select-field-value {
      width: 100%;
    }

    :deep(.bk-select) {
      height: 100%;
    }

    :deep(.bk-select-trigger) {
      height: 100%;
    }

    :deep(.bk-input) {
      height: 100%;
    }
  }

  .field-value {
    display: flex;
    overflow: hidden;
    border-left: 1px solid #dcdee5;
    align-items: center;
    flex: 1 1 320px;

    .field-value-line {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: space-between;

      .select-field-value {
        width: 100%;
      }
    }

    .field-value-line+.field-value-line {
      border-top: 1px solid #dcdee5;
    }
  }

  .field-option {
    background-color: #fff;
    border-left: 1px solid #dcdee5;


    .option-btn {
      font-size: 14px;
      color: #979ba5;
      cursor: pointer;
    }

    .add-btn {
      margin: 0 5px;
    }

    .reduce-btn {
      margin-right: 5px;
    }

  }

  .field-value-content {
    background-color: #fff;
  }
}
</style>
