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
  <div class="title">
    {{ t('变量列表') }}
  </div>
  <bk-table
    ref="variableTable"
    :columns="tableColumn"
    :data="variableData"
    show-overflow-tooltip
    style="max-height: 320px;"
    width="100%" />
</template>
<script setup lang='tsx'>
  import { onActivated, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import {
    execCopy,
  } from '@utils/assist';

  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'isCopy'): void;
  }
  interface Props {
    strategyId: number,
    select: Array<DatabaseTableFieldModel>,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const tableColumn = ref([
    {
      label: () => t('变量名称'),
      render: ({ data }: { data: StrategyFieldEvent['event_basic_field_configs'][0]}) => <div
        style='width: 100%; height: 100%;'
        onClick={e => handleVariableCopy(e, data.prefix, data.field_name)}>
          { `{{${data.field_name}}}` }
        </div>,
    },
    {
      label: () => t('含义'),
      field: () => 'display_name',
    },
    {
      label: () => t('实例'),
      render: ({ data }: {data: any}) => <div>
          {data.example || '--'}
        </div>,
      width: 160,
    },
  ]);

  const variableData = ref<StrategyFieldEvent['event_basic_field_configs']>([]);

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

  const process = () => {
    if (props.select && props.select.length) {
      // 根据select更新event_data_field_configs
      tableData.value.event_data_field_configs = props.select.map(item => createField(item));
    }
    variableData.value = [
      ...tableData.value.event_basic_field_configs,
      ...tableData.value.event_data_field_configs,
    ];
  };

  const {
    data: tableData,
  } = useRequest(StrategyManageService.fetchStrategyEvent, {
    defaultValue: new StrategyFieldEvent(),
    defaultParams: {
      strategy_id: props.strategyId,
    },
    onSuccess: () => {
      process();
    },
    manual: true,
  });

  const handleVariableCopy = (e: Event, prefix: string, value: string) => {
    const formattedVariable = prefix ? `{{${prefix}.${value}}}` : `{{${value}}}`;
    e.stopPropagation();
    emits('isCopy');
    execCopy(formattedVariable, t('变量 {variable} 复制成功', { variable: `{{${value}}}` }));
  };

  onActivated(() => {
    process();
  });
</script>
<style lang="postcss" scoped>
.title {
  margin-bottom: 12px;
  font-size: 14px;
  color: #313238;
}

:deep(.bk-table-head) {
  overflow: unset;
}

:deep(.bk-table-body-content tr td) {
  &:first-child:hover {
    cursor: pointer;
    background-color: #f0f1f5;
  }
}
</style>
