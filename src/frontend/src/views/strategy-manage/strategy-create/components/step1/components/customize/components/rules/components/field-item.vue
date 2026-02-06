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
    v-for="(condition, index) in localConditions.conditions"
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
      error-display-type="tooltips"
      label=""
      label-width="0"
      :property="`configs.where.conditions[${conditionsIndex}].conditions[${index}].condition.field.display_name`"
      required>
      <node-select
        :aggregate-list="aggregateList"
        :condition="condition"
        :conditions="conditions"
        :config-data="localTableFields"
        :config-type="configType"
        @handle-node-selected-value="(node ,val) => onHandleNodeSelectedValue(node ,val, condition)" />
    </bk-form-item>
    <!-- 连接条件 -->
    <bk-form-item
      error-display-type="tooltips"
      label=""
      label-width="0"
      :property="`configs.where.conditions[${conditionsIndex}].conditions[${index}].condition.operator`"
      required>
      <!-- 操作人账号特殊处理 -->
      <bk-select
        v-model="condition.condition.operator"
        filterable
        :placeholder="t('请选择')"
        :popover-options="{ placement: 'top-start' }"
        @change="(value: string) => handleSelectOperator(value, index)">
        <bk-option
          v-for="item in conditionList"
          :key="item.value"
          :label="item.label"
          :value="item.value" />
      </bk-select>
    </bk-form-item>
    <!-- 值 -->
    <bk-form-item
      v-if="!['', 'notnull', 'isnull'].includes(condition.condition.operator)"
      error-display-type="tooltips"
      label=""
      label-width="0"
      :property="(!tagInput.includes(condition.condition.operator) &&
        !(dicts[condition.condition.field.raw_name] &&
          dicts[condition.condition.field.raw_name].length &&
          condition.condition.field.raw_name !== 'action_id' &&
          props.configType === 'EventLog') &&
        !condition.condition.field.raw_name.includes('username')) ?
        `configs.where.conditions[${conditionsIndex}].conditions[${index}].condition.filter` :
        `configs.where.conditions[${conditionsIndex}].conditions[${index}].condition.filters`"
      required
      :rules="[
        { message: t('不能为空'), trigger: ['change', 'blur'], validator: (value: Array<any>) => handleValidate(value) },
      ]">
      <!-- 日志表特有，dict字典下拉 -->
      <bk-cascader
        v-if="dicts[condition.condition.field.raw_name] &&
          dicts[condition.condition.field.raw_name].length &&
          condition.condition.field.raw_name !== 'action_id' &&
          props.configType === 'EventLog'"
        v-model="condition.condition.filters"
        class="consition-value"
        collapse-tags
        filterable
        float-mode
        id-key="value"
        :list="dicts[condition.condition.field.raw_name]"
        :multiple="tagInput.includes(condition.condition.operator)"
        name-key="label"
        :popover-options="{ placement: 'top-start' }"
        trigger="hover"
        @change="(value: Array<Array<string>>) => handleCascaderFilter(value, index)" />

      <!-- 日志表特有，人员选择器 -->
      <audit-user-selector-tenant
        v-else-if="condition.condition.field.raw_name.includes('username') && props.configType === 'EventLog'"
        v-model="condition.condition.filters"
        allow-create
        class="consition-value"
        :multiple="tagInput.includes(condition.condition.operator)"
        :popover-options="{ placement: 'top-start' }"
        @change="(value: Array<string> | string) => handleFilter(Array.isArray(value) ? value : [value], index)" />

      <bk-tag-input
        v-else-if="tagInput.includes(condition.condition.operator)"
        v-model="condition.condition.filters"
        allow-create
        class="consition-value"
        collapse-tags
        :content-width="350"
        has-delete-icon
        :input-search="false"
        :list="(condition.condition.field.raw_name !== 'action_id' && props.configType === 'EventLog') ?
          dicts[condition.condition.field && condition.condition.field.raw_name] :
          []"
        :loading="fieldLoading"
        :paste-fn="pasteFn"
        :placeholder="t('请输入并Enter结束')"
        trigger="focus"
        @change="(value: Array<string>) => handleTagInput(value, index)" />
      <bk-input
        v-else
        v-model="condition.condition.filter"
        class="consition-value"
        :placeholder="t('请输入')"
        @input="(value: string) => handleFilter(value, index)" />
    </bk-form-item>
    <div class="icon-group">
      <audit-icon
        v-if="condition.condition.field.display_name"
        v-bk-tooltips="t('预览当前字段格式与最新值')"
        class="view-icon"
        type="view"
        @click="dataStructurePreview(condition.condition.field)" />
      <audit-icon
        style="margin-right: 10px; cursor: pointer;"
        type="add-fill"
        @click="handleAdd" />
      <audit-icon
        v-if="localConditions.conditions.length > 1"
        style="cursor: pointer;"
        type="reduce-fill"
        @click="() => handleDelete(index)" />
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
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import { splitAndMerge } from '@utils/assist/split-and-merge';

  import nodeSelect from './tree.vue';

  import useRequest from '@/hooks/use-request';


  interface Props {
    tableFields: Array<DatabaseTableFieldModel>,
    expectedResult: Array<DatabaseTableFieldModel>,
    aggregateList: Array<Record<string, any>>,
    conditions: {
      connector: 'and' | 'or';
      index: number,
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
  interface Emits {
    (e: 'updateFieldItemList', conditionsIndex: number, value: Props['conditions']): void;
    (e: 'updateFieldItem', value: DatabaseTableFieldModel | string | Array<string>, conditionsIndex: number, childConditionsIndex: number, type: 'field' | 'operator' | 'filter'): void;
    (e: 'updateConnector', value: 'and' | 'or', conditionsIndex: number): void;
    (e: 'show-structure-preview', rtId: string | Array<string>, currentViewField: string): void;
    (e: 'handleUpdateLocalConditions', value: any): void;
  }
  interface DataType{
    label: string;
    value: string;
    children?: Array<DataType>;
  }

  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const conditionList = ref<Array<{
    label: string,
    value: string
  }>>([]);
  const dicts = ref<Record<string, Array<any>>>({});
  const localTableFields = ref<Array<DatabaseTableFieldModel>>([]);

  const tagInput = ['include', 'exclude'];

  const localConditions = ref<Props['conditions']>({
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
  });

  const needCondition = computed(() => props.conditions.conditions.length > 1);

  const dataStructurePreview = (value: DatabaseTableFieldModel) => {
    emits('show-structure-preview', value.table, value.display_name);
  };

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

  const pasteFn = (value: string) => ([{ id: value, name: value }]);

  const handleAdd = () => {
    localConditions.value.conditions.push({
      condition: {
        field: new DatabaseTableFieldModel(),
        filter: '',
        filters: [],
        operator: '',
      },
    });
    emits('updateFieldItemList', props.conditionsIndex, localConditions.value);
  };

  const handleDelete = (index: number) => {
    if (props.conditions.conditions.length === 1) {
      return;
    }
    localConditions.value.conditions.splice(index, 1);
    emits('updateFieldItemList', props.conditionsIndex, localConditions.value);
  };

  const reSetFilter = (index: number) => {
    if (localConditions.value.conditions[index].condition.filter !== '') {
      localConditions.value.conditions[index].condition.filter = '';
      handleFilter('', index);
    }
    if (localConditions.value.conditions[index].condition.filters.length) {
      localConditions.value.conditions[index].condition.filters = [];
      handleFilter([], index);
    }
  };


  const handleSelectOperator = (value: string, index: number) => {
    emits('updateFieldItem', value, props.conditionsIndex, index, 'operator');
    // 重置数据
    reSetFilter(index);
  };

  // 级联选择器
  const handleCascaderFilter = (value: Array<Array<string>> | Array<string>, index: number) => {
    // 判断是否是级联(多选是二维数组，取每个元素最后一个；单选一维，取最后一个元素)
    const resultValue = (Array.isArray(value) && value.every(element => Array.isArray(element)))
      ? value.map(((valItem) => {
        if (Array.isArray(valItem)) {
          return _.last(valItem) || '';
        }
        return valItem;
      })) : value.slice(-1);
    emits('updateFieldItem', resultValue as Array<string>, props.conditionsIndex, index, 'filter');
  };

  // tag-input、user、input输入
  const handleFilter = (value: Array<string> | string, index: number) => {
    emits('updateFieldItem', value, props.conditionsIndex, index, 'filter');
  };
  // tag-input输入
  const handleTagInput = (value: Array<string>, index: number) => {
    localConditions.value.conditions[index].condition.filters = splitAndMerge(value);
    emits('updateFieldItem', splitAndMerge(value), props.conditionsIndex, index, 'filter');
  };

  const handleChangeConnector = () => {
    emits('updateConnector', props.conditions.connector === 'and' ? 'or' : 'and', props.conditionsIndex);
  };

  // 回显级联数据
  const handleCascader = (key: string, dataList: Array<DataType>) => {
    const conditionItemList = localConditions.value.conditions.filter(item => item.condition.field.raw_name === key);
    if (!conditionItemList) return;
    conditionItemList.forEach((conditionItem) => {
      const valueMap = conditionItem.condition.filters.reduce((res, v: string, index: number) => {
        res[v] = index;
        return res;
      }, {} as Record<string, number>);
      const newVal: Array<Array<string>> = [];
      dataList.forEach((data) => {
        if (valueMap[data.value] !== undefined) {
          newVal[valueMap[data.value]] = [data.value];
        } else {
          data.children?.forEach((childData: DataType) => {
            if (valueMap[childData.value] !== undefined) {
              newVal[valueMap[childData.value]] = [data.value, childData.value];
            }
          });
        }
      });
      // eslint-disable-next-line no-param-reassign
      conditionItem.condition.filters = !tagInput.includes(conditionItem.condition.operator)
        ? newVal.reduce((accumulator, currentValue) => accumulator.concat(currentValue), []) : newVal as any;
    });
  };

  // 回显下拉值
  const  handleValueDicts = () => {
    localConditions.value.conditions.forEach((item) => {
      dicts.value[item.condition.field.raw_name] = [];
    });
    Object.keys(dicts.value).forEach((key) => {
      if (key) {
        fetchStrategyFieldValue({
          field_name: key,
        }).then((data) => {
          dicts.value[key] = data;
          if (data && data.length) {
            handleCascader(key, data);
          }
        });
      }
    });
  };

  // 更新可选字段列表
  const updateTableFields = (conditions: Props['conditions']['conditions'], tableFields: Array<DatabaseTableFieldModel>, expectedResult: Array<DatabaseTableFieldModel>) => {
    const filteredExpectedResult = expectedResult.filter(item => item.aggregate);
    // 检查是否已经选择了预期结果中的字段
    const hasSelectedExpectedResultField = conditions.some(condItem => condItem.condition.field?.aggregate);

    // 根据是否选择了预期结果字段来更新字段列表
    localTableFields.value = hasSelectedExpectedResultField
      ? [...filteredExpectedResult]
      : [...tableFields, ...filteredExpectedResult];

    localTableFields.value = localTableFields.value.map(item => ({ ...item }));
  };
  // 返回值
  const onHandleNodeSelectedValue = (node: Record<string, any>, val: string, condition: Record<string, any>) => {
    // eslint-disable-next-line no-param-reassign
    condition.condition.field = { ...node };
    // eslint-disable-next-line no-param-reassign
    condition.condition.field.display_name = val;
    if ('fieldTypeValueAr' in node) {
      // eslint-disable-next-line no-param-reassign
      condition.condition.field.keys = node.fieldTypeValueAr;
    }
    emits('handleUpdateLocalConditions', localConditions.value);
  };
  // 合并预期结果，预期结果也可以在风险规则中使用
  watch(() => [props.tableFields, props.expectedResult], ([tableFields, expectedResult]) => {
    updateTableFields(localConditions.value.conditions, tableFields, expectedResult);
  }, {
    immediate: true,
    deep: true,
  });

  watch(() => props.conditions, (data) => {
    localConditions.value = JSON.parse(JSON.stringify(data));
    if (props.configType === 'EventLog') {
      // 日志表特有，dict字典下拉
      handleValueDicts();
    }
  }, {
    immediate: true,
  });
</script>
<style scoped lang="postcss">
.rule-item-field {
  position: relative;
  display: grid;
  grid-template-columns: 300px 180px 1fr minmax(65px, auto);
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
    font-size: 14px;
    color: #c4c6cc;

    .view-icon {
      margin-right: 10px;
      color: #3a84ff;
      cursor: pointer
    }
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
