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
    class="strategy-customize-rules"
    :class="needCondition ? 'has-condition' : ''">
    <div class="rule-item-wrap">
      <div
        v-for="(conditions, index) in where.conditions"
        :key="index"
        class="rule-item"
        :style="{
          paddingLeft: getPaddingLeft(index, conditions),
        }">
        <template v-if="needCondition">
          <!-- 二级横线 -->
          <div class="row-line" />
          <!-- 二级竖线 -->
          <div
            v-if="index > 0"
            class="column-line column-line-top" />
          <div
            v-if="index < where.conditions.length -1"
            class="column-line column-line-bottom" />
        </template>
        <field-item
          :aggregate-list="aggregateList"
          :conditions="conditions"
          :conditions-index="index"
          :config-type="configType"
          :expected-result="expectedResult"
          :table-fields="tableFields"
          @show-structure-preview="handleShowStructurePreview"
          @update-connector="handleUpdateConnector"
          @update-field-item="handleUpdateFieldItem"
          @update-field-item-list="handleUpdateFieldItemList" />
        <audit-icon
          v-if="where.conditions.length > 1"
          class="delete-conditions"
          style="font-size: 14px;"
          type="delete"
          @click="() => handleDelete(index)" />
      </div>
      <!-- 二级条件关系 -->
      <div
        v-if="needCondition"
        class="condition"
        @click="() => handleChangeConnector()">
        {{ where.connector }}
      </div>
    </div>
    <div
      class="add-rule-item"
      @click="handleAddRuleItem">
      <audit-icon
        style="margin: 0 6px;"
        type="add" />
      <span>{{ t('添加条件组') }}</span>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import FieldItem from './components/field-item.vue';

  interface Expose {
    resetFormData: () => void,
    setWhere: (whereData: Where, having: Where) => void;
  }
  interface Where {
    connector: 'and' | 'or';
    conditions: Array<{
      connector: 'and' | 'or';
      index: number; // 确保每个条件组都有索引值
      conditions: Array<{
        condition: {
          field: DatabaseTableFieldModel;
          filter: string;
          filters: string[];
          operator: string
        }
      }>
    }>;
  }
  interface Props {
    tableFields: Array<DatabaseTableFieldModel>,
    expectedResult: Array<DatabaseTableFieldModel>,
    aggregateList: Array<Record<string, any>>
    configType: string,
  }
  interface Emits {
    (e: 'updateWhere', value: Where): void;
    (e: 'show-structure-preview', rtId: string | Array<string>, currentViewField: string): void;
  }

  defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const where = ref<Where>({
    connector: 'and',
    conditions: [{
      connector: 'and',
      index: 0,
      conditions: [{
        condition: {
          field: new DatabaseTableFieldModel(),
          filter: '',
          filters: [],
          operator: '',
        },
      }],
    }],
  });
  const needCondition = computed(() => where.value.conditions.length > 1);

  // 是否有选中预期结果
  const hasSelectedExpectedResult = computed(() => where.value.conditions
    .some(item => item.conditions
      .some(condItem => condItem.condition.field?.aggregate)));

  const getPaddingLeft = (index: number, conditions: Where['conditions'][0]) => {
    const beforeArr = where.value.conditions.slice(0, index);
    const afterArr = where.value.conditions.slice(index + 1);
    const hasCondition =  beforeArr.concat(afterArr).some(item => item.conditions.length > 1);
    if (conditions.conditions.length > 1 || hasCondition) {
      return '55px';
    }
    return '16px';
  };

  const handleShowStructurePreview = (table: string | Array<string>, currentViewField: string) => {
    emits('show-structure-preview', table, currentViewField);
  };

  const handleDelete = (index: number) => {
    where.value.conditions.splice(index, 1);
    // 重新计算索引值，保持索引的连续性，通过创建新对象而不是直接修改原对象
    where.value.conditions = where.value.conditions.map((item, idx) => ({
      ...item,
      index: idx,
    }));
  };

  const handleChangeConnector = () => {
    // 有预期结果字段 只能选and
    if (hasSelectedExpectedResult.value) {
      where.value.connector = 'and';
      return;
    }
    where.value.connector = where.value.connector === 'and' ? 'or' : 'and';
  };

  const handleAddRuleItem = () => {
    // 计算新添加条件组的索引值
    const newIndex = where.value.conditions.length > 0
      ? Math.max(...where.value.conditions.map(item => item.index || 0)) + 1 : 0;
    where.value.conditions.push({
      connector: 'and',
      index: newIndex,
      conditions: [{
        condition: {
          field: new DatabaseTableFieldModel(),
          filter: '',
          filters: [],
          operator: '',
        },
      }],
    });
  };

  const handleUpdateFieldItemList = (conditionsIndex: number, value: Where['conditions'][0]) => {
    where.value.conditions[conditionsIndex] = value;
  };

  // eslint-disable-next-line max-len
  const handleUpdateFieldItem = (value: DatabaseTableFieldModel | string | Array<string>, conditionsIndex: number, childConditionsIndex: number, type: 'field' | 'operator' | 'filter') => {
    if (type === 'field') {
      // eslint-disable-next-line max-len
      where.value.conditions[conditionsIndex].conditions[childConditionsIndex].condition.field = value as DatabaseTableFieldModel;
    } else if (type === 'filter') {
      Array.isArray(value)
        // eslint-disable-next-line max-len
        ? where.value.conditions[conditionsIndex].conditions[childConditionsIndex].condition.filters = value as Array<string>
        : where.value.conditions[conditionsIndex].conditions[childConditionsIndex].condition.filter = value as string;
    } else {
      where.value.conditions[conditionsIndex].conditions[childConditionsIndex].condition.operator = value as string;
    }
  };

  const handleUpdateConnector = (value: 'and' | 'or', conditionsIndex: number) => {
    where.value.conditions[conditionsIndex].connector = value;
  };

  watch(() => where.value, (data) => {
    emits('updateWhere', data);
  }, {
    deep: true,
  });

  watch(() => hasSelectedExpectedResult.value, (data) => {
    if (data) {
      where.value.connector = 'and';
    }
  });

  defineExpose<Expose>({
    resetFormData: () => {
      where.value = {
        connector: 'and',
        conditions: [{
          connector: 'and',
          index: 0,
          conditions: [{
            condition: {
              field: new DatabaseTableFieldModel(),
              filter: '',
              filters: [],
              operator: '',
            },
          }],
        }],
      };
    },
    setWhere(whereData: Where, having: Where) {
      where.value = whereData;
      if (having && having.conditions.length > 0) {
        // 将having条件合并到where条件中, conditions根据item.index进行排序合并
        where.value.conditions = where.value.conditions.concat(having.conditions);
        where.value.conditions.sort((a, b) => a.index - b.index);
      }
    },
  });
</script>
<style scoped lang="postcss">
.strategy-customize-rules {
  .rule-item-wrap {
    position: relative;

    .condition {
      position: absolute;
      top: calc(50% - 14px);
      left: -38px;
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

    .rule-item {
      position: relative;
      padding: 16px;
      padding-right: 25px;
      margin-bottom: 16px;
      background: #f5f7fa;
      flex: 1;

      .row-line {
        position: absolute;
        top: 50%;
        left: -25px;
        width: 25px;
        height: 0;
        border-top: 1px dashed #dcdee5;
      }

      .column-line {
        position: absolute;
        left: -25px;
        width: 0;
        height: calc(50% + 8px);
        border-left: 1px dashed #dcdee5;
      }

      .column-line-top {
        top: 0;
        transform: translateY(-8px);
      }

      .column-line-bottom {
        top: 50%;
      }

      .delete-conditions {
        position: absolute;
        top: 5px;
        right: 5px;
        color: #979ba5;;
        cursor: pointer;
      }
    }
  }

  .add-rule-item {
    display: flex;
    height: 32px;
    padding: 0 5px;
    color: #3a84ff;
    cursor: pointer;
    background: #fafbfd;
    border: 1px dashed #dcdee5;
    border-radius: 2px;
    align-items: center;
  }
}

.has-condition {
  width: calc(100% - 35px);
  transform: translateX(35px);
}
</style>
