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
    v-for="(condition, index) in conditions.conditions"
    :key="index"
    class="rule-item-field"
    :style="{ marginBottom: index === conditions.conditions.length -1 ? '0px' : '8px' }">
    <!-- 一级横线 -->
    <div
      v-if="needCondition"
      class="row-line" />
    <!-- 一级竖线 -->
    <div
      v-if="index < conditions.conditions.length - 1"
      class="column-line" />
    <!-- 字段 -->
    <bk-form-item
      label=""
      label-width="0"
      :property="`configs.where.conditions[${conditionsIndex}].conditions[${index}].condition.field.display_name`"
      required>
      <bk-select
        v-model="condition.condition.field.display_name"
        filterable
        :placeholder="t('请选择字段')"
        style="flex: 1;"
        @change="(value: DatabaseTableFieldModel) => handleSelectField(value ,index)">
        <template
          v-if="configType === 'LinkTable' && condition.condition.field.table"
          #prefix>
          <span
            style="
              padding: 0 12px;
              line-height: 32px;
              color: #3a84ff;
              background: #f0f1f5">
            {{ condition.condition.field.table }}
          </span>
        </template>
        <bk-option
          v-for="item in tableFields"
          :key="item.raw_name"
          :value="item">
          <div v-if="configType === 'LinkTable'">
            <span
              v-if="configType === 'LinkTable'"
              style=" color: #3a84ff;">{{ item.table }}.</span>{{ item.display_name }}
          </div>
          <div v-else>
            {{ item.display_name }}
          </div>
        </bk-option>
      </bk-select>
    </bk-form-item>
    <!-- 连接条件 -->
    <bk-form-item
      label=""
      label-width="0"
      :property="`configs.where.conditions[${conditionsIndex}].conditions[${index}].condition.operator`"
      required>
      <!-- 操作人账号特殊处理 -->
      <!-- <bk-input
        v-if="condition.field.raw_name ==='user_identify_src_username'"
        v-model="condition.field.aggregate"
        class="condition-equation"
        :placeholder="t('请输入')" /> -->
      <bk-select
        v-model="condition.condition.operator"
        filterable
        :placeholder="t('请选择')">
        <bk-option
          v-for="item in conditionList"
          :key="item.value"
          :label="item.label"
          :value="item.value" />
      </bk-select>
    </bk-form-item>
    <!-- 值 -->
    <bk-form-item
      v-if="condition.condition.operator !== 'isnull' && condition.condition.operator !== 'notnull'"
      label=""
      label-width="0"
      :property="(input.includes(condition.condition.operator) &&
        !(dicts[condition.condition.field.raw_name] &&
          dicts[condition.condition.field.raw_name].length) &&
        !condition.condition.field.raw_name.includes('username')) ?
        `configs.where.conditions[${conditionsIndex}].conditions[${index}].condition.filter` :
        `configs.where.conditions[${conditionsIndex}].conditions[${index}].condition.filters`"
      required
      :rules="[
        { message: '', trigger: ['change', 'blur'], validator: (value: Array<any>) => handleValidate(value) },
      ]">
      <bk-cascader
        v-if="dicts[condition.condition.field.raw_name] &&
          dicts[condition.condition.field.raw_name].length"
        v-model="condition.condition.filters"
        class="consition-value"
        collapse-tags
        filterable
        float-mode
        id-key="value"
        :list="dicts[condition.condition.field.raw_name]"
        multiple
        name-key="label"
        trigger="hover" />
      <audit-user-selector
        v-else-if="condition.condition.field.raw_name.includes('username')"
        v-model="condition.condition.filters"
        allow-create
        class="consition-value" />
      <bk-tag-input
        v-else-if="tagInput.includes(condition.condition.operator)"
        v-model="condition.condition.filters"
        allow-create
        class="consition-value"
        collapse-tags
        :content-width="350"
        has-delete-icon
        :input-search="false"
        :list="dicts[condition.condition.field && condition.condition.field.raw_name]"
        :loading="fieldLoading"
        :placeholder="t('请输入并Enter结束')"
        trigger="focus" />
      <bk-input
        v-else-if="input.includes(condition.condition.operator)"
        v-model="condition.condition.filter"
        class="consition-value"
        :placeholder="t('请输入')" />
    </bk-form-item>
    <div class="icon-group">
      <audit-icon
        style="margin-right: 10px; cursor: pointer;"
        type="add-fill"
        @click="handleAdd" />
      <audit-icon
        style="cursor: pointer;"
        type="reduce-fill"
        @click="handleDelete" />
    </div>
  </div>
  <div
    v-if="needCondition"
    class="condition"
    @click="handleChangeConnector">
    {{ conditions.connector }}
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'updateFieldItemList', value: string, conditionsIndex: number): void;
    (e: 'updateFieldItem', value: DatabaseTableFieldModel, conditionsIndex: number, childConditionsIndex: number): void;
    (e: 'updateConnector', value: 'and' | 'or', conditionsIndex: number): void;
  }
  interface Props {
    tableFields: Array<DatabaseTableFieldModel>
    conditions: {
      connector: 'and' | 'or';
      conditions: Array<{
        condition: {
          field: DatabaseTableFieldModel;
          filter: string;
          filters: string[];
          operator: string,
        }
      }>
    },
    conditionsIndex: number,
    configType: string,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const conditionList = ref<Array<{
    label: string,
    value: string
  }>>([]);
  const dicts = ref<Record<string, Array<any>>>({});
  const input = ['eq', 'neq', 'reg', 'nreg', 'lte', 'lt', 'gte', 'gt'];
  const tagInput = ['include', 'exclude'];

  const needCondition = computed(() => props.conditions.conditions.length > 1);

  useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess(data) {
      conditionList.value = data.rule_audit_condition_operator;
    },
  });

  // 筛选条件值
  const {
    run: fetchStrategyFieldValue,
    loading: fieldLoading,
  } = useRequest(StrategyManageService.fetchStrategyFieldValue, {
    defaultValue: [],
  });

  const handleValidate = (value: any) => value.length > 0;

  const handleAdd = () => {
    emits('updateFieldItemList', 'add', props.conditionsIndex);
  };

  const handleDelete = () => {
    if (props.conditions.conditions.length === 1) {
      return;
    }
    emits('updateFieldItemList', 'delete', props.conditionsIndex);
  };

  const handleSelectField = (value: DatabaseTableFieldModel, index: number) => {
    if (value) {
      // 获取值的下拉选项
      fetchStrategyFieldValue({
        field_name: value.raw_name,
      }).then((data) => {
        dicts.value[value.raw_name] = data.filter((item: Record<string, any>) => item.id !== '');
      });
    }
    emits('updateFieldItem', _.cloneDeep(value), props.conditionsIndex, index);
  };

  const handleChangeConnector = () => {
    emits('updateConnector', props.conditions.connector === 'and' ? 'or' : 'and', props.conditionsIndex);
  };
</script>
<style scoped lang="postcss">
.rule-item-field {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr minmax(35px, auto);
  gap: 8px;

  :deep(.bk-form-error) {
    display: none;
  }

  :deep(.bk-form-item) {
    margin-bottom: 0;
  }

  :deep(.bk-form-item.is-error .bk-tag-input-trigger) {
    border-color: #ea3636;
  }

  .row-line {
    position: absolute;
    top: 16px;
    left: -25px;
    width: 25px;
    height: 0;
    border-top: 1px dashed #dcdee5;
  }

  .column-line {
    position: absolute;
    top: 16px;
    left: -25px;
    width: 0;
    height: 40px;
    border-left: 1px dashed #dcdee5;
  }

  .icon-group {
    color: #c4c6cc;;
  }
}

.condition {
  position: absolute;
  top: calc(50% - 14px);
  left: 14px;
  width: 28px;
  height: 28px;
  line-height: 28px;
  color: #f5b401;
  text-align: center;
  cursor: pointer;
  background: #fff;
  border: 1px solid #f5b401;
  border-radius: 2px;
}
</style>
