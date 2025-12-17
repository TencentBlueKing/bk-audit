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
  <div v-show="apiData.status_code === 200 && groupData.length > 0 && apiData.result">
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
        <template
          v-for="(tableField, tableIndex) in group.table_fields"
          :key="tableIndex">
          <div class="top-search-table-title">
            {{ tableField.display_name || tableField.raw_name }}
          </div>
          <bk-table
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
        </template>
      </div>
    </bk-card>
  </div>
  <!-- undefined 说明还未开始查询 -->
  <!-- 查询后， 但 result 为 undefined 说明查询失败 -->
  <div
    v-show="(apiData.status_code !== 200 && apiData.status_code !== undefined) ||
      (!apiData.result && apiData.status_code !== undefined)">
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
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';

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
      columns: any[];
      tableData: any[];
      pagination: {
        count: number;
        limit: number;
        current: number;
        limitList?: number[];
      };
    }>;
  }

  interface Props {
    toolDetails: ToolDetailModel;
    maxHeight?: string | number;
    allToolsData: ToolDetailModel[];
    onKvFieldDownClick: (kvField: GroupTableConfig['kv_fields'][0], activeUid?: string) => void;
    // eslint-disable-next-line max-len
    createRenderCell: (fieldItem: OutputFields, toolData: ToolDetailModel) => ({ data }: { data: Record<any, any> }) => any;
    apiData: Record<string, any>; // API 返回的结果数据
  }

  const props = withDefaults(defineProps<Props>(), {
    maxHeight: '300px',
    remotePagination: false,
  });

  const { t } = useI18n();

  const groupData = ref<GroupTableConfig[]>([]);

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


  // 创建 groupData
  const createGroupData = (data: ToolDetailModel): GroupTableConfig[] => {
    if (data.tool_type !== 'api' || !data.config.output_config || !Array.isArray(data.config.output_config.groups)) {
      return [];
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
            render: props.createRenderCell(item, data),
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

  // 监听 toolDetails 变化，创建 groupData
  watch(() => props.toolDetails, (newToolDetails) => {
    if (newToolDetails && newToolDetails.tool_type === 'api') {
      const newGroupData = createGroupData(newToolDetails);
      groupData.value = newGroupData;
    } else {
      groupData.value = [];
    }
  }, { immediate: true });

  // 监听 API 结果数据变化，更新 groupData
  watch(() => props.apiData, (data) => {
    if (data.status_code === 200 && data.result) {
      const { result } = data;
      // 更新每个 group 的 table_fields 数据
      groupData.value = groupData.value.map(group => ({
        ...group,
        kv_fields: group.kv_fields.map(kvField => ({
          ...kvField,
          resolvePathValue: extractDataByPath(result, kvField.path),
        })),
        table_fields: group.table_fields.map((tableField) => {
          // 根据 path (json_path) 从 data 中提取对应的表格数据
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
          return {
            ...tableField,
            tableData: finalTableData,
            pagination: {
              ...tableField.pagination,
              count,
            },
          };
        }),
      }));
    }
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
