<template>
  <div class="event-table">
    <!-- 表头 -->
    <div class="head">
      <div
        v-for="(item, index) in columns"
        :key="index"
        class="header-cell"
        :class="getHeaderClass(index)"
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
            :event-item-arr="item"
            :event-item-key="key"
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

  import TableRow from './table-raw.vue';

  import useRequest from '@/hooks/use-request';

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
  const tableRowRef = ref();

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
      { label: t('事件分组'), width: locale.value === 'en-US' ? 140 : 80 },
      { label: t('字段名称'), width: 190 },
      { label: t('字段显示名'), width: 240 },
      { label: t('重点展示'), tips: t('开启后将在单据里优先展示'), width: 120 },
      { label: t('字段映射'), tips: t('系统字段需要关联到策略，默认按照规则自动从结果字段内获取填充，可修改'), width: 240 },
      { label: t('字段下钻') },
      { label: t('字段说明'), tips: t('在单据页，鼠标移入label，即可显示字段说明') },
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

  const getHeaderClass = (index: number) => {
    const classes = ['group'];
    if (index === 1) classes.push('field-name');
    if (index === 2) classes.push('display-name');
    if (index === 3) classes.push('is-priority');
    if (index === 4) classes.push('map-config');
    if (index === 5) classes.push('drill_config');
    if (index === columns.value.length - 1) classes.push('last');
    return classes;
  };

  const createField = (item: DatabaseTableFieldModel) => ({
    field_name: item.display_name,
    display_name: item.display_name,
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
                  field_name: item.field_name,
                  display_name: item.display_name,
                  is_priority: editItem.is_priority,
                  map_config: {
                    target_value: editItem.map_config?.target_value,
                    source_field: editItem.map_config?.source_field || editItem.map_config?.target_value, // 固定值赋值，用于反显
                  },
                  drill_config: {
                    tool: {
                      uid: editItem.drill_config?.tool?.uid || '',
                      version: editItem.drill_config?.tool?.version || 1,
                    },
                    config: editItem.drill_config?.config || [],
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
        width: 220px;
      }

      &.drill_config {
        width: 240px;
      }

      &.last {
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
