<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed
  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div class="data-search-result-wrapper">
    <primary-table
      bordered
      :columns="columns"
      :data="tableData"
      hover
      :max-height="tableMaxHeight"
      show-header />
    <div class="pagination-wrapper data-result-pagination">
      <bk-pagination
        v-model="pagination.current"
        align="left"
        :count="pagination.count"
        :layout="['total', 'limit', 'list']"
        :limit="pagination.limit"
        :limit-list="pagination.limitList"
        location="left"
        @change="handlePaginationChange"
        @limit-change="handleLimitChange" />
    </div>
  </div>
</template>

<script setup lang="tsx">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';

  import { PrimaryTable } from '@blueking/tdesign-ui';

  import useRequest from '@hooks/use-request';

  interface SearchItem {
    value: any;
    raw_name: string;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
  }

  interface Props {
    uid: string;
    toolDetails: ToolDetailModel;
    searchList: SearchItem[];
    getToolNameAndType: (uid: string) => { name: string, type: string };
    riskToolParams?: Record<string, any>;
  }

  interface Emits {
    (e: 'handleFieldDownClick', item: OutputFields, data: Record<any, any>, uid?: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    riskToolParams: () => ({}),
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  // 表格响应式高度：大屏800px / 小屏600px - 分页区域高度(约68px)
  const isLargeScreen = ref(window.innerWidth >= 1440);
  const tableMaxHeight = computed(() => {
    const baseH = isLargeScreen.value ? 800 : 600;
    return `${Math.max(baseH - 80, 100)}px`;
  });

  // 监听窗口变化
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', () => {
      isLargeScreen.value = window.innerWidth >= 1440;
    });
  }

  // bk-pagination 分页状态
  const pagination = ref({
    count: 0,
    limit: 10,
    current: 1,
    limitList: [10, 20, 50, 100, 200, 500, 1000],
  });

  const tableData = ref<Record<string, any>[]>([]);

  // 获取工具执行结果
  const {
    loading: isLoading,
    run: fetchToolsExecute,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      if (!data?.data) {
        tableData.value = [];
        pagination.value.count = 0;
        return;
      }

      const results = data.data.results || [];
      tableData.value = results;

      // 从响应中提取 total：按优先级尝试多个路径
      const rawTotal = data.data.total
        ?? data.data?.data?.total
        ?? data?.total
        ?? 0;

      pagination.value.count = Math.max(rawTotal, results.length);
    },
  });

  // 判断值是否为空
  const isEmptyValue = (value: any) => {
    if (value === undefined || value === null || value === '') return true;
    if (Array.isArray(value) && value.length === 0) return true;
    return false;
  };

  // 格式化工具变量值
  const formatToolVariableValue = (item: SearchItem) => {
    // 人员选择器转字符串
    if (item.field_category === 'person_select') {
      const strValue = Array.isArray(item.value) && item.value.length > 0 ? item.value.join(',') : '';
      // 非必填且为空，返回 null
      return !item.required && strValue === '' ? null : strValue;
    }
    // 非必填且值为空，返回 null
    if (!item.required && isEmptyValue(item.value)) {
      return null;
    }
    return item.value;
  };

  // 执行工具（使用 toolDetails.uid 作为真实工具uid来调用后端API）
  const executeTool = () => {
    fetchToolsExecute({
      uid: props.toolDetails?.uid || props.uid,
      params: {
        tool_variables: props.searchList.map(item => ({
          raw_name: item.raw_name,
          value: formatToolVariableValue(item),
        })),
        page: pagination.value.current,
        page_size: pagination.value.limit,
      },
      ...(props.riskToolParams && Object.keys(props.riskToolParams).length > 0 ? props.riskToolParams : {}),
    });
  };

  defineExpose({
    executeTool,
    isLoading,
  });

  // 从 toolDetails 获取 outputFields
  const outputFields = computed(() => {
    if (props.toolDetails?.tool_type === 'data_search' && Array.isArray(props.toolDetails.config?.output_fields)) {
      return props.toolDetails.config.output_fields;
    }
    return [];
  });

  // 创建 columns（TDesign 格式：colKey / title / cell）
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const columns = computed<any[]>(() => outputFields.value.map(item => ({
    colKey: item.raw_name,
    title: () => (
      <span
        class={item.description ? 'tips' : ''}
        v-bk-tooltips={{
          disabled: !item.description,
          content: item.description,
        }}>
        {item.display_name || item.raw_name}
      </span>
    ),
    width: 200,
    minWidth: 100,
    ellipsis: true,
    cell: (_h: any, { row }: any) => {
      if (!row) {
        return '--';
      }
      const rawVal = row[item.raw_name];
      // 空值直接返回
      if (rawVal === undefined || rawVal === null || rawVal === '') {
        return '--';
      }
      // 如果有enum映射，优先用映射的name
      const mappings = item.enum_mappings?.mappings;
      const mapped = Array.isArray(mappings) && mappings.length
        ? mappings.find((m: any) => String(m.key) === String(rawVal))
        : undefined;
      const display = mapped ? mapped.name : rawVal;
      if (item.drill_config === null
        || item.drill_config.length === 0
        || (item.drill_config.length === 1 && !item.drill_config[0].tool.uid)) {
        // 普通单元格
        return <span
          v-bk-tooltips={{
            content: t('映射对象', {
              key: mapped?.key,
              name: mapped?.name,
            }),
            disabled: !mapped,
          }}
          style={{
            cursor: 'pointer',
          }}
          class={{ tips: mapped }}
        >
          {display}
        </span>;
      }
      // 可下钻的列，显示按钮
      return (
          <div>
            <bk-popover
              placement="top"
              theme="black"
              v-slots={{
                content: () => (
                  <>
                    {
                      mapped && (
                        <>
                          <span>
                            { t('存储值: ') }
                          </span>
                          <span>
                            { mapped?.key }
                          </span>
                          <br />
                          <span>
                            { t('展示文本: ') }
                          </span>
                          <span>
                            { mapped?.name }
                          </span>
                        </>
                      )
                    }
                    <div style={{
                      marginTop: '8px',
                    }}>
                      { t('点击查看此字段的证据下探') }
                    </div>
                  </>
                ),
              }}>
              <span
                style={{
                  cursor: 'pointer',
                  color: '#3a84ff',
                }}
                class={{ tips: mapped }}
                onClick={(e: any) => {
                  e.stopPropagation(); // 阻止事件冒泡
                  handleFieldDownClick(item, row);
                }}>
                {display}
              </span>
            </bk-popover>
            <bk-popover
              placement="top"
              theme="black"
              v-slots={{
                content: () => (
                  <div>
                    {item.drill_config.map(config => (
                      <div key={config.tool.uid}>
                        {config.drill_name || props.getToolNameAndType(config.tool.uid).name}
                        <bk-button
                          class="ml8"
                          theme="primary"
                          text
                          onClick={(e: any) => {
                            e.stopPropagation(); // 阻止事件冒泡
                            handleFieldDownClick(item, row, config.tool.uid);
                          }}>
                          {t('去查看')}
                          <audit-icon
                            class="mr-18"
                            type="jump-link" />
                        </bk-button>
                      </div>
                    ))}
                  </div>
                ),
              }}>
              <span style={{
                padding: '1px 8px',
                backgroundColor: '#cddffe',
                borderRadius: '8px',
                marginLeft: '5px',
                color: '#3a84ff',
                cursor: 'pointer',
              }}
              onClick={(e: any) => {
                e.stopPropagation(); // 阻止事件冒泡
                handleFieldDownClick(item, row);
              }}>
                {item.drill_config.length}
              </span>
            </bk-popover>
          </div>
      );
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  })) as any);

  const handleFieldDownClick = (item: OutputFields, data: Record<any, any>, uid?: string) => {
    emit('handleFieldDownClick', item, data, uid);
  };

  // bk-pagination 翻页事件
  const handlePaginationChange = (current: number) => {
    pagination.value.current = current;
    executeTool();
  };

  // bk-pagination 切换每页条数事件
  const handleLimitChange = (limit: number) => {
    pagination.value.limit = limit;
    pagination.value.current = 1;
    executeTool();
  };
</script>
<style lang="postcss" scoped>
/* stylelint-disable */
.data-search-result-wrapper {
  display: flex;
  flex-direction: column;

  /* 防止父容器产生额外滚动条，只保留表格自身内部滚动 */
  overflow: hidden;

  :deep(.t-table) {
    overflow: clip;
  }

  /* 核心修复：裁剪 TDesign Table 底部 L 型多余滚动条轨道 */
  :deep(.t-table__inner-wrapper),
  :deep(.t-table__scroll-container) {
    overflow: hidden;
  }

  :deep(.t-table--scroll-horizontal) {
    overflow-x: auto !important;
    overflow-y: hidden !important;
  }

  :deep(.t-table--scroll-vertical) {
    overflow-y: auto !important;
    overflow-x: hidden !important;
  }

  /* 固定滚动条宽度：hover 时不变宽，避免布局抖动 */
  :deep(.t-table--scroll-horizontal),
  :deep(.t-table--scroll-vertical),
  :deep(.t-table__inner-wrapper),
  :deep(.t-table__scroll-container) {
    scrollbar-width: thin;
    scrollbar-color: #c4c6cc transparent;
  }

  /* WebKit: 固定尺寸，禁止 hover 变宽（覆盖 scroll-faker 组件的 14px !important） */
  :deep(.t-table--scroll-horizontal),
  :deep(.t-table--scroll-vertical),
  :deep(.t-table__inner-wrapper),
  :deep(.t-table__scroll-container) {
    &::-webkit-scrollbar,
    & .scrollbar-vertical::-webkit-scrollbar,
    & .scrollbar-horizontal::-webkit-scrollbar {
      height: 6px !important;
      width: 6px !important;
    }

    &:hover::-webkit-scrollbar,
    & .scrollbar-vertical:hover::-webkit-scrollbar,
    & .scrollbar-horizontal:hover::-webkit-scrollbar {
      height: 6px !important;
      width: 6px !important;
    }

    & .scrollbar-vertical,
    & .scrollbar-horizontal {
      &:hover::-webkit-scrollbar {
        height: 6px !important;
        width: 6px !important;
      }
    }

    &::-webkit-scrollbar-thumb,
    & .scrollbar-vertical::-webkit-scrollbar-thumb,
    & .scrollbar-horizontal::-webkit-scrollbar-thumb {
      background-color: #c4c6cc !important;
      border-radius: 3px !important;
    }

    &:hover::-webkit-scrollbar-thumb,
    & .scrollbar-vertical:hover::-webkit-scrollbar-thumb,
    & .scrollbar-horizontal:hover::-webkit-scrollbar-thumb {
      background-color: #a3a6ad !important;
      border-radius: 3px !important;
    }

    &::-webkit-scrollbar-track,
    & .scrollbar-vertical::-webkit-scrollbar-track,
    & .scrollbar-horizontal::-webkit-scrollbar-track {
      background: transparent !important;
    }
  }

  .pagination-wrapper {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    padding: 12px 16px;
    background-color: #fff;

    /* 分页样式由底部非 scoped style 块统一处理 */
  }
}

.tips {
  text-decoration: underline;
  text-decoration-style: dashed;
  text-decoration-color: #c4c6cc;
  text-underline-offset: 5px;
  cursor: pointer;
}
</style>

<style lang="postcss">
/* 分页器：共x条/每页x条 在左，页码在右（非 scoped，确保穿透组件边界） */
.data-result-pagination .bk-pagination {
  display: flex !important;
  align-items: center;
  width: 100%;
}

.data-result-pagination .bk-pagination > *:nth-last-child(1) {
  margin-left: auto !important;
}
</style>
