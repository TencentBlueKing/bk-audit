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
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useRequest from '@hooks/use-request';

  interface Pagination {
    current: number;
    limit: number;
    count: number;
    limitList?: number[];
  }

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
    maxHeight?: string | number;
    remotePagination?: boolean;
    searchList: SearchItem[];
    getToolNameAndType: (uid: string) => { name: string, type: string };
    riskToolParams?: Record<string, any>;
  }

  interface Emits {
    (e: 'handleFieldDownClick', item: OutputFields, data: Record<any, any>, uid?: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    maxHeight: '300px',
    remotePagination: false,
    riskToolParams: () => ({}),
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const pagination = ref<Pagination>({
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
      if (data === undefined) {
        tableData.value = [];
      } else if (data?.data) {
        tableData.value = data.data.results || [];
        pagination.value.count = data.data.total || 0;
      }
    },
  });

  // 执行工具
  const executeTool = () => {
    fetchToolsExecute({
      uid: props.uid,
      params: {
        tool_variables: props.searchList.map(item => ({
          raw_name: item.raw_name,
          // eslint-disable-next-line no-nested-ternary
          value: (item.field_category === 'person_select') ? (item.value.length === 0 ?  '' :  item.value.join(','))  :  item.value,
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

  // 创建 columns
  const columns = computed<Column[]>(() => outputFields.value.map((item): Column => ({
    label: item.display_name,
    field: item.raw_name,
    minWidth: 200,
    showOverflowTooltip: true,
    render: ({ data }: { data?: Record<any, any> }) => {
      if (!data) {
        return '--';
      }
      const rawVal = data[item.raw_name];
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
                  handleFieldDownClick(item, data);
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
                            handleFieldDownClick(item, data, config.tool.uid);
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
                handleFieldDownClick(item, data);
              }}>
                {item.drill_config.length}
              </span>
            </bk-popover>
          </div>
      );
    },
  }))) as unknown as Column[];

  const handleFieldDownClick = (item: OutputFields, data: Record<any, any>, uid?: string) => {
    emit('handleFieldDownClick', item, data, uid);
  };

  const handlePageLimitChange = (val: number) => {
    pagination.value.limit = val;
    pagination.value.current = 1;
    executeTool();
  };

  const handlePageValueChange = (val: number) => {
    pagination.value.current = val;
    executeTool();
  };
</script>
