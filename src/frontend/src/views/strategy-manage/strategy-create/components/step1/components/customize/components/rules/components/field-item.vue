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
    <bk-select
      v-model="condition.field"
      filterable
      :placeholder="t('请选择字段')"
      style="flex: 1;"
      @change="handleSelectField">
      <bk-option
        v-for="item in tableFields"
        :key="item.raw_name"
        :label="item.display_name"
        :value="item" />
    </bk-select>
    <bk-select
      v-model="condition.operation"
      filterable
      :placeholder="t('请选择规则')">
      <bk-option
        v-for="item in ruleData.rulesList"
        :key="item.value"
        :label="item.name"
        :value="item.value" />
    </bk-select>
    <bk-select
      v-if="ruleData.enumList.length"
      v-model="condition.filters"
      filterable
      :placeholder="t('请选择枚举值')">
      <bk-option
        v-for="item in ruleData.enumList"
        :key="item.value"
        :label="item.name"
        :value="item.value" />
    </bk-select>
    <bk-input
      v-else
      v-model="condition.filter"
      :placeholder="t('请输入数值')"
      show-word-limit />
    <div class="icon-group">
      <audit-icon
        style="margin-right: 10px;"
        type="add-fill"
        @click="handleAdd" />
      <audit-icon
        type="reduce-fill"
        @click="handleDelete" />
    </div>
  </div>
  <div
    v-if="needCondition"
    class="condition">
    {{ conditions.operator }}
  </div>
</template>
<script setup lang="ts">
  // import { ref, watch } from 'vue';
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'updateFieldItemList', value: string, conditionsIndex: number): void;
  }
  interface Props {
    tableFields: Array<DatabaseTableFieldModel>
    conditions: {
      operator: 'and' | 'or';
      conditions: Array<{
        field: DatabaseTableFieldModel | '';
        operation: string;
        filter: string;
        filters: string[];
      }>
    },
    conditionsIndex: number
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const needCondition = computed(() => props.conditions.conditions.length > 1);

  // 获取对应规则和枚举值列表
  const {
    data: ruleData,
    run: fetchFiledRules,
  } = useRequest(StrategyManageService.fetchFiledRules, {
    defaultValue: {
      rulesList: [],
      enumList: [],
    },
  });

  const handleAdd = () => {
    emits('updateFieldItemList', 'add', props.conditionsIndex);
  };

  const handleDelete = () => {
    if (props.conditions.conditions.length === 1) {
      return;
    }
    emits('updateFieldItemList', 'delete', props.conditionsIndex);
  };

  const handleSelectField = (value: DatabaseTableFieldModel) => {
    fetchFiledRules({
      data: value,
    });
  };
</script>
<style scoped lang="postcss">
.rule-item-field {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr minmax(35px, auto);
  gap: 8px;

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
  background: #fff;
  border: 1px solid #f5b401;
  border-radius: 2px;
}
</style>
