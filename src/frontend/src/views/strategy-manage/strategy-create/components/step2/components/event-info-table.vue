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
    <div class="head">
      <div
        v-for="(item, index) in column"
        :key="index"
        class="item"
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
    <template
      v-for="(item, key) in tableData"
      :key="key">
      <div
        v-if="!(key === 'event_evidence_field_configs' && strategyType !== 'model')"
        class="body">
        <div
          class="group"
          :style="{minWidth: locale === 'en-US' ? '140px' : '80px'}">
          <span> {{
            strategyType === 'model' && key === 'event_evidence_field_configs'
              ? (groupMap as GroupMapModel).event_evidence_field_configs
              : groupMap[key as keyof GroupMapBase]
          }} </span>
        </div>
        <div class="value-row">
          <value-item
            ref="valueItemRef"
            :item="item"
            :select="select"
            :strategy-type="strategyType" />
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang='tsx'>
  import { computed, onActivated, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import ValueItem from './valueItem.vue';

  import useRequest from '@/hooks/use-request';

  type GroupMapBase = {
    event_basic_field_configs: string;
    event_data_field_configs: string;
  };

  type GroupMapModel = GroupMapBase & {
    event_evidence_field_configs: string;
  };

  interface Exposes{
    getData: () => StrategyFieldEvent,
    getValue: () => Promise<any>;
  }

  interface Props {
    strategyId: number,
    data: StrategyModel,
    select: Array<DatabaseTableFieldModel>,
    strategyType: string
  }

  const props = defineProps<Props>();
  const route = useRoute();

  const { t, locale } = useI18n();
  const valueItemRef = ref();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const fieldMap: Record<string, string> = {
    event_id: 'raw_event_id',
    username: 'operator',
    start_timeaccess_source_ip: 'event_source',
  };

  const column = computed(() => {
    const initColumn = [
      { label: t('事件分组') },
      { label: t('字段名称') },
      { label: t('字段显示名') },
      { label: t('重点展示'), tips: t('开启后将在单据里优先展示') },
      { label: t('字段映射'), tips: t('系统字段需要关联到策略，默认按照规则自动从结果字段内获取填充，可修改') },
      { label: t('字段说明'), tips: t('在单据页，鼠标移入label，即可显示字段说明') },
    ];
    props.strategyType === 'rule' ? initColumn : initColumn.splice(4, 1);
    return initColumn;
  });

  const groupMap = computed<GroupMapBase | GroupMapModel>(() => {
    const baseMap: GroupMapBase = {
      event_basic_field_configs: t('基本信息'),
      event_data_field_configs: t('事件结果'),
    };

    if (props.strategyType === 'model') {
      const modelMap: GroupMapModel = {
        ...baseMap,
        event_evidence_field_configs: t('事件证据'),
      };
      return modelMap;
    }
    return baseMap;
  });

  const createField = (item: DatabaseTableFieldModel) => ({
    field_name: item.display_name,
    display_name: item.display_name,
    is_priority: false,
    map_config: {
      target_value: '',
      source_field: '',
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
                  field_name: item.field_name,
                  display_name: item.display_name,
                  is_priority: editItem.is_priority,
                  map_config: {
                    target_value: editItem.map_config?.target_value,
                    source_field: editItem.map_config?.source_field || editItem.map_config?.target_value, // 固定值赋值，用于反显
                  },
                  description: editItem.description,
                  example: item.example,
                  prefix: '',
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
      return Promise.all((valueItemRef.value as { getValue: () => any }[])?.map(item => item.getValue()));
    },
  });
</script>
<style lang="postcss" scoped>
.event-table {
  @mixin item-styles {
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

    .item {
      @include  item-styles;

      background-color: #f5f7fa;

      &:nth-child(2) {
        width: 190px;
      }

      &:nth-child(3) {
        width: 240px;
      }

      &:nth-child(4) {
        width: 120px;
      }

      &:nth-child(5) {
        width: 240px;
      }

      &:last-child {
        flex: 1;
      }
    }
  }

  .body {
    display: flex;
    min-height: 42px;

    .group {
      @include  item-styles;

      display: flex;
      background-color: #f5f7fa;
      align-items: center;
      justify-content: center;
    }

    .value-row {
      width: calc(100% - 80px);
    }
  }
}
</style>
