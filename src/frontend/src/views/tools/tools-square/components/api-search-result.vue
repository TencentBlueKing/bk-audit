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
  <div v-if="toolExecuteData?.data?.status_code === 200 && groupData.length > 0">
    <bk-card
      v-for="(group, groupIndex) in groupData"
      :key="groupIndex"
      is-collapse
      :title="t(`分组${groupIndex + 1}`)">
      <div class="card-content">
        <!-- KV 字段展示 -->
        <template v-if="group.kv_fields && group.kv_fields.length > 0">
          <render-info-block
            v-for="(kvFieldsChunk, chunkIndex) in chunkArray(group.kv_fields, 3)"
            :key="chunkIndex"
            style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
            <render-info-item
              v-for="(kvField, kvIndex) in kvFieldsChunk"
              :key="kvIndex"
              class="kv-field-item"
              :label="kvField.display_name || kvField.raw_name">
              <template v-if="getMappedValue(kvField) || hasDrillConfig(kvField)">
                <!-- 有字段映射或者有证据下探 -->
                <div style="display: flex; align-items: center; gap: 5px;">
                  <bk-popover
                    placement="top"
                    theme="black">
                    <span
                      :class="[
                        getMappedValue(kvField) ? 'tips' : '',
                      ]"
                      :style="{
                        color: hasDrillConfig(kvField) ? '#3a84ff' : '#313238',
                        cursor: hasDrillConfig(kvField) ? 'pointer' : 'default',
                      }"
                      @click.stop="hasDrillConfig(kvField) && handleKVFieldDownClick(kvField)">
                      {{ getMappedValue(kvField)?.name || kvField.resolvePathValue }}
                    </span>
                    <template #content>
                      <div>
                        <div v-if="getMappedValue(kvField)">
                          <span>{{ t('存储值: ') }}</span>
                          <span>{{ getMappedValue(kvField)?.key }}</span>
                          <br>
                          <span>{{ t('展示文本: ') }}</span>
                          <span>{{ getMappedValue(kvField)?.name }}</span>
                        </div>
                        <div
                          v-if="hasDrillConfig(kvField)"
                          :style="{
                            marginTop: getMappedValue(kvField) ? '8px' : '0',
                          }">
                          {{ t('点击查看此字段的证据下探') }}
                        </div>
                      </div>
                    </template>
                  </bk-popover>
                  <!-- 证据下探按钮 -->
                  <bk-popover
                    v-if="hasDrillConfig(kvField)"
                    placement="top"
                    theme="black">
                    <template #content>
                      <div>
                        <div
                          v-for="config in kvField.drill_config"
                          :key="config.tool.uid">
                          {{ config.drill_name || getToolNameAndType(config.tool.uid).name }}
                          <bk-button
                            class="ml8"
                            text
                            theme="primary"
                            @click.stop="handleKVFieldDownClick(kvField, config.tool.uid)">
                            {{ t('去查看') }}
                            <audit-icon
                              class="mr-18"
                              type="jump-link" />
                          </bk-button>
                        </div>
                      </div>
                    </template>
                    <span
                      :style="{
                        padding: '1px 8px',
                        backgroundColor: '#cddffe',
                        borderRadius: '8px',
                        color: '#3a84ff',
                        cursor: 'pointer',
                      }"
                      @click.stop="handleKVFieldDownClick(kvField)">
                      {{ kvField.drill_config.length }}
                    </span>
                  </bk-popover>
                </div>
              </template>
              <!-- 没有字段映射或者没有证据下探 -->
              <span v-else>
                {{ kvField.resolvePathValue }}
              </span>
            </render-info-item>
          </render-info-block>
        </template>

        <!-- Table 字段展示 -->
        <template v-if="group.table_fields.length > 0">
          <div
            v-for="(tableField, tableIndex) in group.table_fields"
            :key="tableIndex">
            <div class="top-search-table-title">
              {{ tableField.display_name || tableField.raw_name }}
            </div>
            <bk-table
              :key="key"
              :border="['row','outer','col']"
              :columns="tableField.columns"
              :data="tableField.tableData"
              header-align="center"
              :max-height="maxHeight"
              :pagination="tableField.pagination"
              show-overflow-tooltip
              @page-limit-change="(val: number) => {
                handleGroupTablePageLimitChange(groupIndex, tableIndex, val);
              }"
              @page-value-change="(val: number) => {
                handleGroupTablePageChange(groupIndex, tableIndex, val);
              }" />
          </div>
        </template>
      </div>
    </bk-card>
  </div>
  <div v-else>
    <bk-exception
      :description="t('请联系工具维护人员进行修复')"
      :title="t('数据查询失败')"
      type="500">
      <div>
        <a
          href=""
          target="_blank">
          <audit-icon
            style="margin-right: 6px;"
            type="qw" />
          <span>{{ toolDetails.created_by }}、{{ toolDetails.updated_by }}</span>
        </a>
      </div>
    </bk-exception>
  </div>
</template>

<script setup lang="tsx">
  import type { Column } from 'bkui-vue/lib/table/props';
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import RenderInfoItem from '@views/strategy-manage/list/components/render-info-item.vue';

  interface DrillDownItem {
    raw_name: string;
    display_name: string;
    description: string;
    drill_config: Array<{
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
        target_field_type?: string;
      }>;
      drill_name?: string;
    }>;
    enum_mappings: {
      collection_id: string;
      mappings: Array<{
        key: string;
        name: string;
      }>;
    };
  }

  interface GroupTableConfig {
    kv_fields: Array<{
      drill_config: DrillDownItem['drill_config'];
      enum_mappings: DrillDownItem['enum_mappings'];
      raw_name: string;
      display_name: string;
      description: string;
      path: string;
      resolvePathValue: unknown;
    }>;
    table_fields: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      path: string;
      columns: Column[];
      tableData: any[];
      pagination: {
        count: number;
        limit: number;
        current: number;
        limitList?: number[];
      };
    }>;
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
    allToolsData: ToolDetailModel[];
    onKvFieldDownClick: (kvField: GroupTableConfig['kv_fields'][0], activeUid?: string) => void;
    searchList: SearchItem[];
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

  const groupData = ref<GroupTableConfig[]>([]);
  const key = ref(0);

  // 获取工具执行结果
  const {
    loading: isLoading,
    data: toolExecuteData,
    run: fetchToolsExecute,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
  });

  // 执行工具
  const executeTool = () => {
    fetchToolsExecute({
      uid: props.uid,
      params: {
        tool_variables: props.searchList.map(item => ({
          raw_name: item.raw_name,
          value: item.value,
        })),
      },
      ...(props.riskToolParams && Object.keys(props.riskToolParams).length > 0 ? props.riskToolParams : {}),
    });
  };

  defineExpose({
    executeTool,
    toolExecuteData,
    isLoading,
  });

  // 将数组按指定大小分块
  const chunkArray = (array: any[], chunkSize: number): any[][] => {
    const chunks: any[][] = [];
    for (let i = 0; i < array.length; i += chunkSize) {
      chunks.push(array.slice(i, i + chunkSize));
    }
    return chunks;
  };

  // KV 字段辅助函数
  const getMappedValue = (kvField: GroupTableConfig['kv_fields'][0]) => {
    const rawVal = kvField.resolvePathValue;
    const mappings = kvField.enum_mappings?.mappings;
    if (Array.isArray(mappings) && mappings.length) {
      return mappings.find((m: any) => String(m.key) === String(rawVal));
    }
    return undefined;
  };

  const hasDrillConfig = (kvField: GroupTableConfig['kv_fields'][0]) => kvField.drill_config
    && Array.isArray(kvField.drill_config)
    && kvField.drill_config.length > 0
    && kvField.drill_config.some((config: any) => config.tool?.uid);


  const handleKVFieldDownClick = (kvField: GroupTableConfig['kv_fields'][0], activeUid?: string) => {
    props.onKvFieldDownClick(kvField, activeUid);
  };

  const getToolNameAndType = (uid: string) => {
    const tool = props.allToolsData?.find(item => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type,
    } : {
      name: '',
      type: '',
    };
  };

  // 处理分组表格页码变化(本地分页)
  const handleGroupTablePageChange = (groupIndex: number, tableIndex: number, newPage: number) => {
    if (groupData.value[groupIndex]?.table_fields[tableIndex]) {
      groupData.value[groupIndex].table_fields[tableIndex].pagination.current = newPage;
    }
  };

  // 处理分组表格每页条数变化(本地分页)
  const handleGroupTablePageLimitChange = (groupIndex: number, tableIndex: number, newLimit: number) => {
    if (groupData.value[groupIndex]?.table_fields[tableIndex]) {
      groupData.value[groupIndex].table_fields[tableIndex].pagination.limit = newLimit;
      groupData.value[groupIndex].table_fields[tableIndex].pagination.current = 1; // 重置到第一页
    }
  };

  // 根据 json_path 提取数据
  const extractDataByPath = (data: any, path: string): any => {
    if (!path || !data) return null;

    // 去掉路径中的下标，如 [1]、[26] 等
    const cleanPath = path.replace(/\[\d+\]/g, '');

    // 根据 . 分割路径，一层一层获取数据
    const pathParts = cleanPath.split('.').filter(part => part.length > 0);
    let result = data;

    for (const part of pathParts) {
      if (result === null || result === undefined) {
        return null;
      }
      result = result[part];
    }

    // 如果是字符串，去掉两边的引号（双引号或单引号）
    if (typeof result === 'string') {
      result = result.replace(/^["']|["']$/g, '');
    }

    return result;
  };

  const handleFieldDownClick = (item: OutputFields, data: Record<any, any>, uid?: string) => {
    emit('handleFieldDownClick', item, data, uid);
  };

  // 创建 groupData
  const createGroupData = (data: ToolDetailModel): GroupTableConfig[] => {
    if (!data.config.output_config || !Array.isArray(data.config.output_config.groups)) {
      return [{
        kv_fields: [],
        table_fields: [],
      }];
    }

    const outputConfig = data.config.output_config;
    return outputConfig.groups.map((group: any) => {
      const kvFields: GroupTableConfig['kv_fields'] = [];
      const tableFields: GroupTableConfig['table_fields'] = [];

      // 遍历每个 output_field，根据 field_config.field_type 分类
      (group.output_fields || []).forEach((field: any) => {
        const fieldConfig = field.field_config || {};
        const fieldType = fieldConfig.field_type;

        if (fieldType === 'kv') {
          // KV 模式：放入 kv_fields
          kvFields.push({
            raw_name: field.raw_name,
            enum_mappings: field.enum_mappings,
            drill_config: field.drill_config,
            display_name: field.display_name || field.raw_name,
            description: field.description || '',
            path: field.json_path || '',
            resolvePathValue: '', // 根据path解析的值
          });
        } else if (fieldType === 'table' && Array.isArray(fieldConfig.output_fields)) {
          // Table 模式：用 field_config.output_fields 生成 columns
          const tableColumns = fieldConfig.output_fields.map((item: OutputFields) => ({
            label: item.display_name || item.raw_name,
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
              console.log('mapped', mapped);
              const display = mapped ? mapped.name : rawVal;
              console.log('display', display);
              if (item.drill_config === null
                || item.drill_config.length === 0
                || (item.drill_config.length === 1 && !item.drill_config[0].tool.uid)) {
                // 普通单元格
                return <span>
                  { rawVal }
                </span>;
              // 没有映射时，直接显示
              // return <span>111</span>;
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
                        handleFieldDownClick(item, toolExecuteData.value?.data.result);
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
                              {config.drill_name || getToolNameAndType(config.tool.uid).name}
                              <bk-button
                                class="ml8"
                                theme="primary"
                                text
                                onClick={(e: any) => {
                                  e.stopPropagation(); // 阻止事件冒泡
                                  handleFieldDownClick(item, toolExecuteData.value?.data.result, config.tool.uid);
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
                      handleFieldDownClick(item, toolExecuteData.value?.data.result);
                    }}>
                      {item.drill_config.length}
                    </span>
                  </bk-popover>
                </div>
              );
            },
            // render: ({ data }: { data?: Record<any, any> }) => {
            //   if (!data) {
            //     return '--';
            //   }
            //   return '111';
            // },
          }));

          tableFields.push({
            raw_name: field.raw_name,
            display_name: field.display_name || field.raw_name,
            description: field.description || '',
            path: field.json_path || '',
            columns: tableColumns,
            tableData: [],
            pagination: {
              count: 0,
              limit: 100,
              current: 1,
              limitList: [100, 200, 500, 1000],
            },
          });
        }
      });

      return {
        kv_fields: kvFields,
        table_fields: tableFields,
      };
    });
  };

  // 监听 toolExecuteData 变化，初始化并更新 groupData
  watch(() => toolExecuteData.value, (data) => {
    // 如果数据为空或无效，清空 groupData 并返回
    if (!data || !data.data) {
      groupData.value = [];
      return;
    }

    key.value += 1;
    groupData.value = createGroupData(props.toolDetails);

    console.log('executeData324234234324', data);
    console.log('key', key.value);
    // 异步更新 groupData，填充数据
    setTimeout(() => {
      if (data.data.status_code === 200 && data.data.result) {
        const { result } = data.data;
        // 更新每个 group 的 table_fields 数据
        groupData.value.forEach((group) => {
          group.kv_fields.forEach((kvField) => {
            // eslint-disable-next-line no-param-reassign
            kvField.resolvePathValue = extractDataByPath(result, kvField.path);
          });
          group.table_fields.forEach((tableField) => {
            const tableData = extractDataByPath(result, tableField.path);
            let finalTableData: any[] = [];
            let count = 0;
            if (Array.isArray(tableData)) {
              finalTableData = tableData;
              count = tableData.length;
            } else if (tableData) {
              finalTableData = [tableData];
              count = 1;
            }
            // eslint-disable-next-line no-param-reassign
            tableField.tableData = finalTableData;
            // eslint-disable-next-line no-param-reassign
            tableField.pagination.count = count;
          });
        });
      }
    }, 1000);
  });
</script>

<style scoped lang="postcss">
.card-content {
  .top-search-table-title {
    margin: 10px 0;
    font-weight: 700;
  }
}
</style>
