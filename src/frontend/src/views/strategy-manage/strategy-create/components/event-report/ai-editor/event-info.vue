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
  <div class="event-info">
    <div class="tips-banner">
      <audit-icon
        class="info-icon"
        type="info-fill" />
      <span class="tips-text">
        {{ t('一个审计风险工单可能关联多条事件,可以使用聚合函数对数据进行处理;若不使用聚合函数,系统将默认提取最后一个事件的数据') }}
      </span>
    </div>
    <div class="event-info-table">
      <div class="table-header">
        <div class="table-cell header-cell table-cell-right-border w1">
          {{ t('变量名称') }}
        </div>
        <div class="table-cell header-cell table-cell-right-border w2">
          {{ t('聚合函数') }}
        </div>
        <div class="table-cell header-cell table-cell-right-border w3">
          {{ t('引用方式') }}
        </div>
        <div class="table-cell header-cell w5">
          {{ t('操作') }}
        </div>
      </div>
      <div
        v-for="(row, index) in localTableData"
        :key="index"
        class="table-row">
        <div class="table-cell table-cell-right-border w1">
          <tool-tip-text
            :data="nameTiptext(row)"
            :line="1"
            placement="top" />
        </div>

        <div class="table-cell table-cell-right-border w2 pn">
          <bk-select
            v-model="row.aggregate"
            class="event-info-aggregation-select"
            :clearable="false">
            <bk-option
              v-for="item in handlerAggregationLists(row.field_type)"
              :id="item.id"
              :key="item.id"
              :name="`${item.name}(${item.id})`" />
          </bk-select>
        </div>
        <div class="table-cell table-cell-right-border w3">
          <tool-tip-text
            :data="referenceModeText(row)"
            :line="1"
            placement="top" />
          <audit-icon
            class="copy-icon"
            type="copy"
            @click="handleCopy(row)" />
        </div>

        <div class="table-cell w5">
          <span
            class="insert-link"
            @click="handleInsert(row)">
            {{ t('插入') }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="tsx">
  import { onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import useRequest from '@hooks/use-request';

  import { execCopy } from '@utils/assist';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';


  interface aggregation {
    id: string | undefined;
    name: string;
    supported_field_types: string[];
  }

  interface Props {
    tableData?: any[];
  }

  interface Emits {
    (e: 'insert', value: string): void;
  }
  interface expose {
    getEventVariables: () => any[];
  }
  const props = withDefaults(defineProps<Props>(), {
    tableData: () => [],
  });

  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  // localTableData 来自 expected-results/index.vue 中的 expectedResultList
  // 数据流：
  // 1. expected-results/index.vue 中的 <vuedraggable :list="expectedResultList">
  // 2. expectedResultList 通过 handleUpdateExpectedResult 保存到 formData.configs.select
  // 3. formData.configs.select 保存到 editData.configs.select
  // 4. event-report/index.vue: eventInfoData = computed(() => props.editData?.configs?.select || [])
  // 5. eventInfoData -> ai-editor -> inset-var -> event-info (作为 tableData prop)
  // 6. tableData -> localTableData
  const localTableData = ref<any[]>([]);

  // 初始化表格数据
  const initTableData = () => {
    if (props.tableData && props.tableData.length > 0) {
      // props.tableData 就是 expected-results/index.vue 中 vuedraggable 的 expectedResultList
      localTableData.value = props.tableData.map((item: any) => ({
        ...item,
        aggregate: 'latest',
      }));
    } else {
      localTableData.value = [];
    }
  };

  // 监听 props.tableData 变化，同步到本地数据
  // props.tableData 来自 expected-results/index.vue 的 expectedResultList (vuedraggable 的 :list)
  watch(() => props.tableData, () => {
    initTableData();
  }, { deep: true, immediate: true });

  // 变量名称
  const nameTiptext = (item: any) => {
    if (item.display_name !== '') {
      return `${item.display_name}(${item.raw_name})`;
    }
    return item.raw_name;
  };
  const referenceModeText = (item: any) => {
    if (item.aggregate === 'null') {
      return `{{ event.${item.display_name} }}`;
    }
    return  `{{ ${item.aggregate}(event.${item.display_name}) }}`;
  };
  const aggregationLists = ref<aggregation[]>([]);
  // 聚合函数
  const handlerAggregationLists = (fieldType: string) => {
    const list = aggregationLists.value.map((aggregationItem: aggregation) => {
      if (aggregationItem.supported_field_types.length === 0) {
        return aggregationItem;
      }
      if (aggregationItem.supported_field_types.includes(fieldType)) {
        return aggregationItem;
      }
      return null;
    }).filter((item: aggregation | null) => item !== null) as aggregation[];
    return list;
  };

  // 获取聚合函数列表
  const {
    run: fetchAggregationFunctions,
  } = useRequest(StrategyManageService.fetchAggregationFunctions, {
    defaultValue: [],
    onSuccess(data) {
      aggregationLists.value = data;
    },
  });
  // 复制
  const handleCopy = (item: any) => {
    execCopy(`{{ event.${item.display_name} }}`, t('复制成功'));
  };
  // 插入
  const handleInsert = (item: any) => {
    emits('insert', `{{ ${item.aggregate}(event.${item.display_name}) }}`);
  };
  // 获取事件变量
  const getEventVariables = () => localTableData.value ;

  onMounted(() => {
    fetchAggregationFunctions();
  });

  defineExpose<expose>({
    getEventVariables,
  });
</script>

<style lang="postcss" scoped>
.event-info {
  .tips-banner {
    display: flex;
    width: 880px;
    height: 32px;
    padding: 0 9px;
    margin: 24px 0 0 40px;
    line-height: 32px;
    background: #f0f5ff;
    border: 1px solid #a3c5fd;
    border-radius: 2px;
    align-items: center;

    .info-icon {
      font-size: 14px;
      color: #3a84ff;
    }

    .tips-text {
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
    }
  }

  .event-info-table {
    margin: 24px 40px;
    background: #fff;
    border-bottom: 1px solid #dcdee5;
    border-radius: 2px;

    .table-header {
      display: flex;
      background: #f0f1f5;
      border-bottom: 1px solid #dcdee5;
    }

    .table-row {
      display: flex;
      border-bottom: 1px solid #dcdee5;
      transition: background-color .2s;

      &:last-child {
        border-bottom: none;
      }

      &:hover {
        background: #f5f7fa;
      }
    }

    .table-cell {
      display: flex;
      height: 42px;
      padding-left: 16px;
      font-size: 12px;
      color: #4d4f56;
      align-items: center;

      &.header-cell {
        font-weight: 500;
        color: #313238;
      }

      &.table-cell-right-border {
        border-right: 1px solid #dcdee5;
      }

      &.w1 {
        width: 164px;
      }

      &.w2 {
        width: 201px;
      }

      &.w3 {
        width: 290px;
      }

      &.w5 {
        width: 100px;
      }

      &.pn {
        padding: 0;
      }

      .copy-icon,
      .expand-icon {
        font-size: 14px;
        cursor: pointer;
        transition: color .2s;
      }

      .copy-icon {
        margin-left: 5px;
        color: #4d4f56;

        &:hover {
          color: #3a84ff;
        }
      }

      .expand-icon {
        color: #979ba5;
      }

      .insert-link {
        color: #3a84ff;
        cursor: pointer;
        transition: opacity .2s;

        &:hover {
          opacity: 80%;
        }
      }
    }
  }

  :deep(.t-table) {
    .reference-cell {
      display: flex;
      align-items: center;
      gap: 8px;

      .copy-icon {
        font-size: 14px;
        color: #3a84ff;
        cursor: pointer;
        transition: opacity .2s;

        &:hover {
          opacity: 80%;
        }
      }
    }

    .insert-link {
      color: #3a84ff;
      cursor: pointer;
      transition: opacity .2s;

      &:hover {
        opacity: 80%;
      }
    }
  }

  .footer-tips {
    padding-top: 16px;
    margin-top: 16px;
    border-top: 1px solid #e8e8e8;

    .tip-item {
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;

      &:last-child {
        margin-bottom: 0;
      }
    }
  }
}

.empty-text {
  padding: 20px;
  font-size: 14px;
  color: #979ba5;
  text-align: center;
}

.event-info-aggregation-select {
  :deep(.bk-input) {
    width: 200px;
    height: 42px;
    border: none;
  }
}
</style>

