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
  <div class="variable-table-wrap">
    <div class="title">
      {{ t('变量列表') }}
    </div>
    <bk-loading
      :loading="showLoading"
      style="min-height: 160px;">
      <bk-table
        ref="variableTable"
        :columns="tableColumn"
        :data="variableData"
        style="max-height: 320px;"
        width="100%" />
    </bk-loading>
  </div>
</template>
<script setup lang='tsx'>
  import type { Column } from 'bkui-vue/lib/table/props';
  import { computed, onActivated, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import Tooltips from '@components/show-tooltips-text/index.vue';

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

  const getVariableText = (prefix: string, fieldName: string) => (
    prefix ? `{{ ${prefix}["${fieldName}"] }}` : `{{ ${fieldName} }}`
  );

  const tableColumn = ref([
    {
      label: () => t('变量名称'),
      minWidth: 260,
      width: 300,
      render: ({ data }: { data: StrategyFieldEvent['event_basic_field_configs'][0]}) => {
        const text = getVariableText(data.prefix, data.field_name);
        return (
          <div class="variable-name-cell">
            <Tooltips
              class="variable-name-text"
              data={text} />
            <span
              class="variable-copy-btn"
              v-bk-tooltips={t('复制')}
              onClick={e => handleVariableCopy(e, data.prefix, data.field_name)}>
              <audit-icon
                class="variable-copy-icon"
                type="copy" />
            </span>
          </div>
        );
      },
    },
    {
      label: () => t('含义'),
      field: () => 'display_name',
      minWidth: 120,
      showOverflowTooltip: true,
    },
  ] as Column[]);

  const variableData = ref<StrategyFieldEvent['event_basic_field_configs']>([]);

  const createField = (item: DatabaseTableFieldModel) => ({
    field_name: item.display_name,
    display_name: item.display_name,
    is_show: true,
    is_priority: false,
    duplicate_field: false,
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

  // 首次请求完成前保持 loading，避免闪「暂无数据」
  const hasFetched = ref(false);

  const {
    data: tableData,
    loading: isLoading,
  } = useRequest(StrategyManageService.fetchStrategyEvent, {
    defaultValue: new StrategyFieldEvent(),
    defaultParams: {
      strategy_id: props.strategyId,
    },
    onSuccess: () => {
      process();
    },
    onFinally: () => {
      hasFetched.value = true;
    },
    manual: true,
  });

  const showLoading = computed(() => isLoading.value || !hasFetched.value);

  const handleVariableCopy = (e: Event, prefix: string, value: string) => {
    const formattedVariable = getVariableText(prefix, value);
    e.stopPropagation();
    emits('isCopy');
    execCopy(formattedVariable, t('变量 {variable} 复制成功', { variable: `{{ ${value} }}` }));
  };

  onActivated(() => {
    process();
  });
</script>
<style lang="postcss" scoped>
.variable-table-wrap {
  min-width: 480px;
}

.title {
  margin-bottom: 12px;
  font-size: 14px;
  color: #313238;
}

:deep(.bk-table-head) {
  overflow: unset;
}

:deep(.variable-name-cell) {
  display: flex;
  gap: 6px;
  align-items: center;
  width: 100%;
  min-width: 0;
}

:deep(.variable-name-text) {
  flex: 0 1 auto;
  max-width: calc(100% - 26px);
  min-width: 0;
  overflow: hidden;
}

:deep(.variable-copy-btn) {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: #3a84ff;
  cursor: pointer;
  border-radius: 2px;

  &:hover {
    background: #e1ecff;
  }
}

:deep(.variable-copy-icon) {
  font-size: 14px;
}
</style>
