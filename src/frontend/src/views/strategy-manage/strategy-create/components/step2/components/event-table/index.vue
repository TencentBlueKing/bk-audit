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
  <div class="event-table">
    <!-- 表头 -->
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

    <!-- 表格内容 -->
    <template
      v-for="(item, key) in tableData"
      :key="key">
      <!-- strategyType === 'rule'时不显示 event_evidence_field_configs -->
      <template v-if="strategyType === 'rule' && key === 'event_evidence_field_configs'" />
      <div
        v-else
        class="table-section">
        <div
          class="group-cell"
          :style="{minWidth: locale === 'en-US' ? '140px' : '80px'}">
          <span>{{ groupMap[key] }}</span>
        </div>
        <div class="rows-container">
          <table-row
            ref="tableRowRef"
            :all-tools-data="allToolsData"
            :event-item-arr="item"
            :event-item-key="key"
            :output-fields="outputFields"
            :select="select"
            :strategy-name="strategyName"
            :strategy-type="strategyType"
            :tag-data="tagData"
            @open-tool="handleOpenTool" />
        </div>
      </div>
    </template>
  </div>
  <!-- 循环所有工具 -->
  <div
    v-for="item in allToolsData"
    :key="item.uid">
    <component
      :is="DialogVue"
      :ref="(el:any) => dialogRefs[item.uid] = el"
      :tags-enums="tagData"
      @open-field-down="openFieldDown" />
  </div>
</template>

<script setup lang='tsx'>
  import { computed, onActivated, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';
  import ToolManageService from '@service/tool-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';
  import ToolDetailModel from '@model/tool/tool-detail';

  import DialogVue from '@views/tools/tools-square/components/dialog.vue';

  import TableRow from './table-raw.vue';

  import ToolInfo from '@/domain/model/tool/tool-info';
  import useRequest from '@/hooks/use-request';

  interface Exposes{
    getData: () => StrategyFieldEvent,
    getValue: () => Promise<any>;
  }

  interface Props {
    strategyId: number,
    data: StrategyModel,
    select: Array<DatabaseTableFieldModel>,
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
  const route = useRoute();

  const { t, locale } = useI18n();
  const tableRowRef = ref();
  const dialogRefs = ref<Record<string, any>>({});

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  // 用于自动填充参数
  const fieldMap: Record<string, string> = {
    event_id: 'raw_event_id',
    username: 'operator',
    start_timeaccess_source_ip: 'event_source',
  };

  //  strategyType === 'rule'时显示全部列，否则排除 “字段映射”
  const columns = computed(() => {
    const initColumns = [
      { label: t('事件分组') },
      { key: 'field_name', label: t('字段名称') },
      { key: 'display_name', label: t('字段显示名') },
      { key: 'is_show', label: t('在单据中展示') },
      { key: 'is_priority', label: t('重点展示'), tips: t('开启后将在单据里优先展示') },
      { key: 'map_config', label: t('字段映射'), tips: t('系统字段需要关联到策略，默认按照规则自动从结果字段内获取填充，可修改') },
      { key: 'drill_config', label: t('字段下钻') },
      { key: 'description', label: t('字段说明'), tips: t('在单据页，鼠标移入label，即可显示字段说明') },
    ];

    return props.strategyType === 'rule'
      ? initColumns
      : initColumns.filter((_, index) => index !== 4);
  });

  //  strategyType === 'rule'时不显示 event_evidence_field_configs
  const groupMap = computed(() => (props.strategyType === 'rule'
    ? {
      event_basic_field_configs: t('基本信息'),
      event_data_field_configs: t('事件结果'),
    } : {
      event_basic_field_configs: t('基本信息'),
      event_data_field_configs: t('事件结果'),
      event_evidence_field_configs: t('事件证据'),
    }));

  const outputFields = computed(() => {
    const basicFields = tableData.value.event_basic_field_configs.map(item => ({
      raw_name: item.field_name,
      display_name: item.display_name,
      description: item.description,
      target_field_type: 'basic',
    }));
    const dataFields = tableData.value.event_data_field_configs.map(item => ({
      raw_name: item.field_name,
      display_name: item.display_name,
      description: item.description,
      target_field_type: 'data',
    }));
    const evidenceFields = props.strategyType === 'rule'
      ? tableData.value.event_evidence_field_configs.map(item => ({
        raw_name: item.field_name,
        display_name: item.display_name,
        description: item.description,
        target_field_type: 'evidence',
      }))
      : [];
    return basicFields.concat(dataFields, evidenceFields);
  });

  // 获取所有工具
  const {
    data: allToolsData,
    run: fetchAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
  });

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
    const toolItem = allToolsData.value.find(item => item.uid === uid);
    if (!toolItem) {
      return;
    }

    const toolInfo = new ToolInfo(toolItem as any);
    if (dialogRefs.value[uid]) {
      dialogRefs.value[uid].openDialog(toolInfo, drillDownItem, drillDownItemRowData);
    }
  };

  // 打开工具
  const handleOpenTool = async (toolInfo: ToolDetailModel) => {
    if (dialogRefs.value[toolInfo.uid]) {
      dialogRefs.value[toolInfo.uid].openDialog(toolInfo.uid);
    }
  };

  const getHeaderClass = (valueKey: string | undefined) => ({
    'field-name': valueKey === 'field_name',
    'display-name': valueKey === 'display_name',
    'is-priority': valueKey === 'is_priority' || valueKey === 'is_show',
    'map-config': valueKey === 'map_config',
    'drill-config': valueKey === 'drill_config',
    description: valueKey === 'description',
  });

  const createField = (item: DatabaseTableFieldModel) => ({
    field_name: item.display_name,
    display_name: item.display_name,
    is_show: true,
    is_priority: false,
    map_config: {
      target_value: '',
      source_field: '',
    },
    drill_config: {
      tool: {
        uid: '',
        version: 1,
      },
      config: [],
    },
    description: '',
    example: '',
    prefix: 'event_data',
  });

  const setTableData = (key: 'event_basic_field_configs' | 'event_data_field_configs') => {
    switch (key) {
    case 'event_basic_field_configs':
      if (tableData.value[key].length && props.select && props.select.length) {
        // 把不匹配的项清空(非固定值)
        tableData.value.event_basic_field_configs = tableData.value.event_basic_field_configs.map((item) => {
          if (item.map_config && !item.map_config.target_value) {
            const value = item.map_config.source_field || item.map_config.target_value;
            if (!props.select.some(selectItem => selectItem.display_name === value)) {
              // eslint-disable-next-line no-param-reassign
              item.map_config = {
                source_field: undefined,
                target_value: undefined,
              };
            }
          }
          return item;
        });
        // 根据select填充event_basic_field_configs参数
        props.select.forEach((item) => {
          if (fieldMap[item.raw_name]) {
            const field = tableData.value[key].find(fieldItem => fieldItem.field_name === fieldMap[item.raw_name]);
            if (field && field.map_config && !field.map_config.source_field) {
              field.map_config.source_field = item.display_name;
            }
          }
        });
      }
      break;
    case 'event_data_field_configs':
      if (props.select && props.select.length) {
        // 根据select更新event_data_field_configs
        tableData.value.event_data_field_configs = props.select.map((item) => {
          const existingField = tableData.value.event_data_field_configs.
            find(fieldItem => fieldItem.field_name === item.display_name);
          if (existingField) {
            return existingField;
          }
          return createField(item);
        });
      }
    }
  };

  const process = () => {
    // 填充内容（字段自动填充, 根据select更新event_data_field_configs)
    setTableData('event_basic_field_configs');
    setTableData('event_data_field_configs');
  };

  const {
    data: tableData,
  } = useRequest(StrategyManageService.fetchStrategyEvent, {
    defaultValue: new StrategyFieldEvent(),
    defaultParams: {
      strategy_id: props.strategyId,
    },
    onSuccess: () => {
      if (isEditMode || isCloneMode) {
        (Object.keys(tableData.value) as Array<keyof typeof tableData.value>).forEach((key)  => {
          if (props.data[key]?.length && tableData.value[key]?.length) {
            // 编辑填充参数
            tableData.value[key] = tableData.value[key].map((item) => {
              const editItem = props.data[key] && props.data[key].find(edItem => edItem.field_name === item.field_name);
              if (editItem) {
                return {
                  ...item,
                  ...editItem,
                  map_config: editItem.map_config || {
                    source_field: undefined,
                    target_value: undefined,
                  },
                  drill_config: editItem.drill_config || {
                    tool: {
                      uid: '',
                      version: 1,
                    },
                    config: [],
                  },
                };
              }
              return {
                ...item,
              };
            });
          }
        });
      }
      process();
    },
    manual: true,
  });

  onActivated(() => {
    process();
  });

  defineExpose<Exposes>({
    getData() {
      return tableData.value;
    },
    getValue() {
      return Promise.all((tableRowRef.value as { getValue: () => any }[])?.map(item => item.getValue()));
    },
  });
</script>

<style lang="postcss" scoped>
.event-table {
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
        width: 200px;
      }

      &.display-name {
        width: 200px;
      }

      &.is-priority {
        width: 120px;
      }

      &.map-config {
        width: 230px;
      }

      &.drill-config {
        width: 230px;
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
      width: calc(100% - 80px);
    }
  }
}
</style>
