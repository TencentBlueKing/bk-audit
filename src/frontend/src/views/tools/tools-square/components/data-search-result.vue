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
  <bk-table
    :border="['row','outer','col']"
    :columns="columns"
    :data="tableData"
    header-align="center"
    :max-height="maxHeight"
    :pagination="pagination"
    :remote-pagination="remotePagination"
    show-overflow-tooltip
    @page-limit-change="handlePageLimitChange"
    @page-value-change="handlePageValueChange" />
</template>

<script setup lang="tsx">
  import type { Column } from 'bkui-vue/lib/table/props';
  import { computed } from 'vue';

  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';

  interface Pagination {
    current: number;
    limit: number;
    count: number;
    limitList?: number[];
  }

  interface Props {
    tableData: Record<string, any>[];
    toolDetails: ToolDetailModel;
    maxHeight?: string | number;
    remotePagination?: boolean;
    // eslint-disable-next-line max-len
    createRenderCell: (fieldItem: OutputFields, toolData: ToolDetailModel) => ({ data }: { data: Record<any, any> }) => any;
  }

  interface Emits {
    (e: 'updateTable'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    maxHeight: '300px',
    remotePagination: false,
  });

  const emit = defineEmits<Emits>();

  const pagination = defineModel<Pagination>('pagination', { required: true });

  // 从 toolDetails 获取 outputFields
  const outputFields = computed(() => {
    if (props.toolDetails?.tool_type === 'data_search' && Array.isArray(props.toolDetails.config?.output_fields)) {
      return props.toolDetails.config.output_fields;
    }
    return [];
  });

  // 创建 columns
  const columns = computed<Column[]>(() => outputFields.value.map((item): Column => {
    const renderCell = props.createRenderCell(item, props.toolDetails);
    return {
      label: item.display_name,
      field: item.raw_name,
      minWidth: 200,
      showOverflowTooltip: true,
      render: (args: any) => {
        // 包装 renderCell 以兼容 bk-table 的参数类型（data 是可选的）
        if (!args?.data) {
          return null;
        }
        return renderCell({ data: args.data });
      },
    };
  })) as unknown as Column[];

  const handlePageLimitChange = (val: number) => {
    pagination.value.limit = val;
    pagination.value.current = 1;
    emit('updateTable');
  };

  const handlePageValueChange = (val: number) => {
    pagination.value.current = val;
    emit('updateTable');
  };
</script>
