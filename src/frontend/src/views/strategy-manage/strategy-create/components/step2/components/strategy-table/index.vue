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
  <div class="strategy-table">
    <div class="head">
      <div
        v-for="(item, index) in columns"
        :key="index"
        class="header-cell"
        :class="getHeaderClass(item.key)"
        :style="{minWidth: (locale === 'en-US' && index === 0) ? '140px' : '80px'}">
        <span
          v-bk-tooltips="{
            disabled: !item.tips,
            content: item.tips
          }"
          :class="[item.tips ? 'tips' : '']">
          {{ item.label }}
        </span>
      </div>
    </div>

    <div class="table-section">
      <div class="rows-container">
        <table-row
          ref="tableRowRef"
          :all-tools-data="allToolsData"
          :event-item-arr="tableData"
          event-item-key="event_basic_field_configs"
          :output-fields="[]"
          :select="select"
          :strategy-name="strategyName"
          :strategy-type="strategyType"
          :tag-data="tagData"
          @open-tool="handleOpenTool" />
      </div>
    </div>
  </div>
  <!-- 循环所有工具 -->
  <div
    v-for="item in allToolsDataUids"
    :key="item">
    <component
      :is="DialogVue"
      :ref="(el:any) => dialogRefs[item] = el"
      :tags-enums="tagData"
      @open-field-down="openFieldDown" />
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';
  import ToolManageService from '@service/tool-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import DialogVue from '@views/tools/tools-square/components/dialog.vue';

  import tableRow from './table-raw.vue';

  import useRequest from '@/hooks/use-request';

  interface Exposes {
    getData: () => { risk_meta_field_config: StrategyFieldEvent['risk_meta_field_config'] };
  }

  interface Props {
    data: StrategyModel,
    select: Array<DatabaseTableFieldModel>,
    strategyId: number,
    strategyType: string,
    strategyName: string
  }

  interface DrillDownItem {
    raw_name: string;
    display_name: string;
    description: string;
    drill_config: {
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
      }>
    };
  }

  const props = defineProps<Props>();
  const { t, locale } = useI18n();
  const route = useRoute();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const disabledList = ['risk_level', 'status', 'current_operator'];
<<<<<<< HEAD
  const isPriorityList = ['risk_id', 'risk_tags', 'risk_hazard', 'risk_guidance'];
=======
>>>>>>> 6e0b83ca (feat: 审计风险工单排版展示优化 --story=126952423)

  const dialogRefs = ref<Record<string, any>>({});

  const columns = [
    { key: 'field_name', label: t('字段名称') },
<<<<<<< HEAD
    { key: 'display_name', label: t('字段显示名') },
    { key: 'is_priority', label: t('重点展示'), tips: t('设为重点展示的字段将在风险单据中直接显示，其他字段将被折叠收起') },
    { key: 'drill_config', label: t('字段下钻'), tips: t('为字段配置下钻工具后，可以在风险单据中点击该字段，查询其关联信息') },
    // { key: 'description', label: t('字段说明'), tips: t('在单据页，鼠标移入label，即可显示字段说明') },
=======
    { key: 'is_priority', label: t('重点展示'), tips: t('设为重点展示的字段将在风险单据中直接显示，其他字段将被折叠收起') },
    { key: 'drill_config', label: t('字段下钻'), tips: t('为字段配置下钻工具后，可以在风险单据中点击该字段，查询其关联信息') },
    { key: 'description', label: t('字段说明'), tips: t('在单据页，鼠标移入label，即可显示字段说明') },
>>>>>>> 6e0b83ca (feat: 审计风险工单排版展示优化 --story=126952423)
  ];

  const getHeaderClass = (valueKey: string) => ({
    'field-name': valueKey === 'field_name',
<<<<<<< HEAD
    'display-name': valueKey === 'display_name',
    'is-priority': valueKey === 'is_priority',
    'drill-config': valueKey === 'drill_config',
    // description: valueKey === 'description',
=======
    'is-priority': valueKey === 'is_priority',
    'drill-config': valueKey === 'drill_config',
    description: valueKey === 'description',
>>>>>>> 6e0b83ca (feat: 审计风险工单排版展示优化 --story=126952423)
  });

  const tableData = ref<StrategyFieldEvent['risk_meta_field_config']>([]);

  useRequest(StrategyManageService.fetchStrategyEvent, {
    defaultValue: new StrategyFieldEvent(),
    defaultParams: {
      strategy_id: props.strategyId,
    },
    manual: true,
    onSuccess: (data) => {
      tableData.value = data.risk_meta_field_config.map(item => ({
        ...item,
<<<<<<< HEAD
        is_priority: disabledList.concat(isPriorityList).includes(item.field_name) ? true : item.is_priority,
      }));
      if ((isEditMode || isCloneMode) && props.data.risk_meta_field_config?.length && tableData.value.length) {
        // 以 tableData 的顺序为主，用 props.data 填充数据
        const propsDataMap = new Map();
        props.data.risk_meta_field_config.forEach((item) => {
          propsDataMap.set(item.field_name, item);
        });

        tableData.value = tableData.value.map((tableItem) => {
          const propsItem = propsDataMap.get(tableItem.field_name);
          if (propsItem) {
            return {
              ...tableItem,
              field_name: propsItem.field_name,
              display_name: propsItem.display_name,
              is_show: propsItem.is_show ?? true,
              is_priority: propsItem.is_priority,
              duplicate_field: propsItem.duplicate_field,
              map_config: {
                target_value: propsItem.map_config?.target_value,
                source_field: propsItem.map_config?.source_field || propsItem.map_config?.target_value, // 固定值赋值，用于反显
              },
              enum_mappings: {
                collection_id: propsItem.enum_mappings?.collection_id || '',
                mappings: propsItem.enum_mappings?.mappings || [],
              },
              drill_config: {
                tool: {
                  uid: propsItem.drill_config?.tool?.uid || '',
                  version: propsItem.drill_config?.tool?.version || 1,
                },
                config: propsItem.drill_config?.config || [],
              },
              description: propsItem.description,
              example: propsItem.example,
              prefix: propsItem.prefix || '',
            };
          }
          return tableItem;
        });
=======
        is_priority: disabledList.includes(item.field_name) ? true : item.is_priority,
      }));
      if ((isEditMode || isCloneMode) && props.data.risk_meta_field_config?.length && tableData.value.length) {
        // 编辑填充参数，不需要保持顺序
        tableData.value = props.data.risk_meta_field_config.map(item => ({
          field_name: item.field_name,
          display_name: item.display_name,
          is_show: item.is_show ?? true,
          is_priority: item.is_priority,
          map_config: {
            target_value: item.map_config?.target_value,
            source_field: item.map_config?.source_field || item.map_config?.target_value, // 固定值赋值，用于反显
          },
          enum_mappings: {
            collection_id: item.enum_mappings?.collection_id || '',
            mappings: item.enum_mappings?.mappings || [],
          },
          drill_config: {
            tool: {
              uid: item.drill_config?.tool?.uid || '',
              version: item.drill_config?.tool?.version || 1,
            },
            config: item.drill_config?.config || [],
          },
          description: item.description,
          example: item.example,
          prefix: item.prefix || '',
        }));
>>>>>>> 6e0b83ca (feat: 审计风险工单排版展示优化 --story=126952423)
      }
    },
  });

  // 获取所有工具
  const {
    data: allToolsData,
    run: fetchAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
  });

  // 动态工具数据
  const allToolsDataUids = ref<string[]>([]);

  // 获取标签列表
  const {
    data: tagData,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      fetchAllTools();
    },
  });

  // 下钻打开
  const openFieldDown = (drillDownItem: DrillDownItem, drillDownItemRowData: Record<any, string>) => {
    const { uid } = drillDownItem.drill_config.tool;

    // 如果工具不在 allToolsDataUids 中，添加它
    if (!allToolsDataUids.value.find(item => item === uid)) {
      allToolsDataUids.value.push(uid);
    }

    if (dialogRefs.value[uid]) {
      dialogRefs.value[uid].openDialog(uid, drillDownItem, drillDownItemRowData);
    }
  };

  // 打开工具
  const handleOpenTool = async (toolInfo: any) => {
    const { uid } = toolInfo;
    // 如果工具不在 allToolsDataUids 中，添加它
    if (!allToolsDataUids.value.find(item => item === uid)) {
      allToolsDataUids.value.push(uid);
    }
  };

  defineExpose<Exposes>({
    getData() {
      return {
        risk_meta_field_config: tableData.value,
      };
    },
  });
</script>
<style scoped lang="postcss">
.strategy-table {
  @mixin cell-base {
    display: flex;
    padding: 0 12px;
    border-right: 1px solid #dcdee5;
    border-bottom: 1px solid #dcdee5;
    align-items: center;
  }

  display: flex;
  margin-bottom: 10px;
  color: #63656e;
  border-top: 1px solid #dcdee5;
  border-left: 1px solid #dcdee5;
  flex-direction: column;

  .head {
    display: flex;
    height: 42px;
    background-color: #f5f7fa;

    .header-cell {
      @include cell-base;

      background-color: #f5f7fa;

      &.field-name {
        width: 250px;
      }

<<<<<<< HEAD
      &.display-name {
        width: 250px;
      }

=======
>>>>>>> 6e0b83ca (feat: 审计风险工单排版展示优化 --story=126952423)
      &.is-priority {
        width: 200px;
      }

      &.drill-config {
        width: 250px;
      }

      &:last-child {
        flex: 1;
      }
    }
  }

  .table-section {
    display: flex;
    min-height: 42px;

    .group-cell {
      @include cell-base;

      display: flex;
      background-color: #f5f7fa;
      align-items: center;
      justify-content: center;
    }

    .rows-container {
      width: 100%;
    }
  }
}
</style>
