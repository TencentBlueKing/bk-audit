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
    <!-- 使用动态组件，单分组用 div，多分组用 bk-card -->
    <component
      :is="(groupData.length === 1 && !isGrouping) ? 'div' : AuditCollapsePanel"
      v-for="(group, groupIndex) in groupData"
      :key="groupIndex"
      style="margin-bottom: 16px;"
      v-bind="{ label: group.name, isActive: true }">
      <div
        class="card-content"
        :class="[groupData.length === 1 && !isGrouping ? 'single-content' : '']">
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
              :description="kvField.description"
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
                          {{ config.drill_name || props.getToolNameAndType(config.tool.uid).name }}
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
            <div
              v-if="group.kv_fields && group.kv_fields.length > 0 || tableIndex > 0"
              class="table-field-divider" />
            <div
              v-if="tableField.display_name !== 'list' || tableField.raw_name !== 'list'"
              class="top-search-table-title">
              <span
                v-bk-tooltips="{
                  disabled: !tableField.description,
                  content: tableField.description
                }"
                :class="[tableField.description ? 'tips' : '']">
                {{ tableField.display_name || tableField.raw_name }}
              </span>
            </div>
            <div class="top-search-table">
              <primary-table
                v-if="tableReady"
                :key="key"
                align="left"
                bordered
                class="api-search-result-table"
                :columns="tableField.columns"
                :data="tableField.tableData"
                location="left"
                :max-height="tableMaxHeight" />
              <div class="pagination-wrapper api-result-pagination">
                <bk-pagination
                  v-model="tableField.pagination.current"
                  align="left"
                  :count="tableField.pagination.count"
                  :layout="['total', 'limit', 'list']"
                  :limit="tableField.pagination.limit"
                  :limit-list="tableField.pagination.limitList"
                  location="left"
                  @change="(current: any) => {
                    const page = typeof current === 'number' ? current :
                      (current?.current ?? tableField.pagination.current);
                    tableField.pagination.current = page;
                    handleGroupPaginationChange(groupIndex, tableIndex, page);
                  }"
                  @limit-change="(limit: number) => {
                    tableField.pagination.limit = limit;
                    tableField.pagination.current = 1;
                    handleGroupPaginationChange(groupIndex, tableIndex);
                  }" />
              </div>
            </div>
          </div>
        </template>
      </div>
    </component>
  </div>
  <!-- 未查询时显示空占位 -->
  <div v-else-if="!toolExecuteData || Object.keys(toolExecuteData).length === 0">
    <bk-exception
      class="exception-part"
      scene="part"
      type="search-empty">
      {{ t('暂无数据') }}
    </bk-exception>
  </div>
  <!-- 查询失败时显示异常 -->
  <div v-else>
    <bk-exception
      :description="t('请联系工具维护人员进行修复')"
      :title="t('数据查询失败')"
      type="500">
      <div>
        <div style="color: #3a84ff; cursor: pointer;">
          <audit-icon
            style="margin-right: 6px;"
            type="qw" />
          <span
            v-for="(user, userIndex) in linkUsers"
            :key="user"
            @click="handleOpenUserWx(user)">
            {{ user }}
            <span v-if="linkUsers.length > 1 && userIndex !== linkUsers.length - 1">、</span>
          </span>
        </div>
      </div>
    </bk-exception>
  </div>
</template>

<script setup lang="tsx">
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import _ from 'lodash';
  import { computed, nextTick, type Ref, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import { PrimaryTable } from '@blueking/tdesign-ui';

  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useRequest from '@hooks/use-request';

  import AuditCollapsePanel from '@components/audit-collapse-panel/index.vue';

  import RenderInfoItem from '@views/risk-manage/detail/components/render-info-item.vue';
  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';

  import { formatTimeRangeSelectValue } from '@views/tools/tools-square/utils/time-range-value';

  interface Exposes {
    executeTool: () => void;
    toolExecuteData: any;
    isLoading: Ref<boolean>;
    resetGroupData: () => void;
  }

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
    name: string;
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      columns: any[];
      tableData: any[];
      pagination: {
        current: number;
        limit: number;
        count: number;
        limitList?: number[];
      };
      // 分页配置（启用分页且匹配到 pagination_config 时存在）
      paginationConfig?: {
        page_param_raw_name: string;
        page_size_param_raw_name: string;
        total_path: string;
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
    searchList: SearchItem[];
    getToolNameAndType: (uid: string) => { name: string, type: string };
    riskToolParams?: Record<string, any>;
  }

  interface Emits {
    (e: 'handleFieldDownClick', item: OutputFields, data: Record<any, any>, uid?: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    remotePagination: false,
    riskToolParams: () => ({}),
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  const groupData = ref<GroupTableConfig[]>([]);
  const key = ref(0);
  // bk-table 渲染门闸：只有当 groupData 的 pagination.count 等数据全部填充完毕后才允许挂载，
  // 否则 bk-table 在 count=0/中间值时挂载，分页器会用初值快照，后续更新不再生效。
  const tableReady = ref(false);

  // 表格响应式高度：大屏600px / 小屏400px - 分页区域高度(约68px)
  const isLargeScreen = ref(window.innerWidth >= 1440);
  const tableMaxHeight = computed(() => {
    const baseH = isLargeScreen.value ? 800 : 600;
    return `${Math.max(baseH - 80, 100)}px`;
  });

  if (typeof window !== 'undefined') {
    window.addEventListener('resize', () => {
      isLargeScreen.value = window.innerWidth >= 1440;
    });
  }

  const linkUsers = computed(() => [...new Set([props.toolDetails.created_by, props.toolDetails.updated_by]
    .filter(Boolean))]);

  const isGrouping = computed(() => props.toolDetails.config.output_config?.enable_grouping);

  // 获取工具执行结果
  const {
    loading: isLoading,
    data: toolExecuteData,
    run: fetchToolsExecute,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
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
    // 时间范围选择器统一转换为绝对时间（后端不支持 now-7d 等相对时间表达式）
    if (item.field_category === 'time_range_select') {
      return formatTimeRangeSelectValue(item.value);
    }
    return item.value;
  };

  const collectPaginationVariables = (): Array<{ raw_name: string; value: any }> => {
    const result: Array<{ raw_name: string; value: any }> = [];
    const seen = new Set<string>();

    const enablePagination = !!props.toolDetails?.config?.output_config?.enable_pagination;
    const paginationConfigs = Array.isArray(props.toolDetails?.config?.output_config?.pagination_config)
      ? props.toolDetails!.config!.output_config!.pagination_config!
      : [];
    if (!enablePagination || paginationConfigs.length === 0) return result;

    const findRuntimePagination = (cfg: any) => {
      const listRawName = cfg?.list_field?.raw_name || '';
      const listJsonPath = cfg?.list_field?.json_path || '';
      const candidates: Array<{ current: number; limit: number; raw_name: string; path: string }> = [];
      groupData.value.forEach((group) => {
        group.table_fields.forEach((tf) => {
          if (tf.paginationConfig) {
            candidates.push({
              current: tf.pagination.current,
              limit: tf.pagination.limit,
              raw_name: tf.raw_name,
              path: tf.path,
            });
          }
        });
      });
      let hit = candidates.find(c => listRawName && c.raw_name === listRawName);
      if (!hit && listJsonPath) {
        hit = candidates.find(c => c.path === listJsonPath);
      }
      if (!hit && paginationConfigs.length === 1 && candidates.length === 1) {
        [hit] = candidates;
      }
      return hit ? { current: hit.current, limit: hit.limit } : null;
    };

    paginationConfigs.forEach((cfg: any) => {
      if (!cfg) return;
      const runtime = findRuntimePagination(cfg);
      const pageVal = runtime ? runtime.current : (cfg.default_page ?? 1);
      const sizeVal = runtime ? runtime.limit : (cfg.default_page_size ?? 10);

      const pageRawName: string = cfg?.page_param?.raw_name || '';
      const sizeRawName: string = cfg?.page_size_param?.raw_name || '';

      if (pageRawName && !seen.has(pageRawName)) {
        result.push({ raw_name: pageRawName, value: pageVal });
        seen.add(pageRawName);
      }
      if (sizeRawName && !seen.has(sizeRawName)) {
        result.push({ raw_name: sizeRawName, value: sizeVal });
        seen.add(sizeRawName);
      }
    });

    return result;
  };

  // 执行工具（使用 toolDetails.uid 作为真实工具uid来调用后端API）
  // 后端分页：page/page_size 由前端通过 tool_variables 注入，后端按工具配置渲染到下游 API 的 query/path/body
  const executeTool = (paginationParams?: Array<{ raw_name: string; value: any }>) => {
    const toolVariables = props.searchList.map(item => ({
      raw_name: item.raw_name,
      value: formatToolVariableValue(item),
    }));

    // 合入分页参数：优先使用显式传入的；否则从当前 groupData 自动收集（首次查询用配置默认值）
    const finalPaginationParams = paginationParams && paginationParams.length > 0
      ? paginationParams
      : collectPaginationVariables();

    if (finalPaginationParams.length > 0) {
      const existedNames = new Set(toolVariables.map(v => v.raw_name));
      finalPaginationParams.forEach((param) => {
        // 避免与 input_variable 重名时重复推入（后端已校验重名，此处以 input_variable 为准）
        if (existedNames.has(param.raw_name)) return;
        toolVariables.push({
          raw_name: param.raw_name,
          value: param.value,
        });
      });
    }

    fetchToolsExecute({
      uid: props.toolDetails?.uid || props.uid,
      params: {
        tool_variables: toolVariables,
      },
      ...(props.riskToolParams && Object.keys(props.riskToolParams).length > 0 ? props.riskToolParams : {}),
    });
  };

  defineExpose<Exposes>({
    executeTool,
    toolExecuteData,
    isLoading,
    resetGroupData: () => {
      groupData.value = [];
      toolExecuteData.value = {};
    },
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

  const handleOpenUserWx = (username: string) => {
    const link = document.createElement('a');
    link.href = `wxwork://message/?username=${username}`;
    link.click();
  };

  // 记录用户主动翻页/切条数的意图（用独立变量，不依赖响应式对象引用）
  const pendingPageMap = new Map<string, { current?: number; limit?: number }>();
  let isUserPaginating = false;

  // bk-pagination 翻页/切条数后触发请求
  const handleGroupPaginationChange = (groupIndex: number, tableIndex: number, targetPage?: number) => {
    const tf = groupData.value[groupIndex]?.table_fields[tableIndex];
    if (!tf?.paginationConfig) return;
    // 直接从参数或最新状态记录用户意图
    const key = `${groupIndex}-${tableIndex}-${tf.raw_name}`;
    pendingPageMap.set(key, {
      current: targetPage ?? tf.pagination.current,
      limit: tf.pagination.limit,
    });
    isUserPaginating = true;
    executeTool();
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

  const deepFindNumberByKey = (data: any, key: string, maxDepth = 6): number | null => {
    if (!data || !key) return null;
    const visited = new WeakSet<object>();
    const stack: Array<{ node: any; depth: number }> = [{ node: data, depth: 0 }];
    while (stack.length > 0) {
      const { node, depth } = stack.pop()!;
      if (!node || typeof node !== 'object' || depth > maxDepth) continue;
      if (visited.has(node)) continue;
      visited.add(node);
      if (Array.isArray(node)) {
        for (const item of node) {
          if (item && typeof item === 'object') {
            stack.push({ node: item, depth: depth + 1 });
          }
        }
        continue;
      }
      if (Object.prototype.hasOwnProperty.call(node, key)) {
        const v = node[key];
        if (typeof v === 'number' && Number.isFinite(v)) return v;
        if (typeof v === 'string' && v !== '' && Number.isFinite(Number(v))) return Number(v);
      }
      Object.values(node).forEach((v) => {
        if (v && typeof v === 'object') {
          stack.push({ node: v, depth: depth + 1 });
        }
      });
    }
    return null;
  };

  const handleKVFieldDownClick = (kvField: GroupTableConfig['kv_fields'][0], uid?: string) => {
    emit('handleFieldDownClick', kvField as OutputFields, toolExecuteData.value?.data.result, uid);
  };

  const handleFieldDownClick = (item: OutputFields, data: Record<any, any>, uid?: string) => {
    const newItem = _.cloneDeep(item);
    // 把item中的drill_config.config.target_value作为json_path只保留最后一级，因为已经是对应表格数据
    newItem.drill_config.forEach((config: any) => {
      config.config.forEach((configItem: any) => {
        // eslint-disable-next-line no-param-reassign
        configItem.target_value = typeof configItem.target_value === 'string' ? configItem.target_value.split('.').pop() || '' : configItem.target_value;
      });
    });
    emit('handleFieldDownClick', newItem, data, uid);
  };

  // 创建 groupData
  const createGroupData = (data: ToolDetailModel): GroupTableConfig[] => {
    if (!data.config.output_config || !Array.isArray(data.config.output_config.groups)) {
      return [{
        name: '',
        kv_fields: [],
        table_fields: [],
      }];
    }

    const outputConfig = data.config.output_config;
    const enablePagination = !!outputConfig.enable_pagination;
    const paginationConfigs = Array.isArray(outputConfig.pagination_config)
      ? outputConfig.pagination_config
      : [];

    const findPaginationConfig = (field: any) => {
      if (!enablePagination) return undefined;
      const fieldRawName = field?.raw_name;
      const fieldPath = field?.json_path;
      let matched = paginationConfigs.find((p: any) => p?.list_field?.raw_name === fieldRawName);
      if (!matched && fieldPath) {
        matched = paginationConfigs.find((p: any) => p?.list_field?.json_path === fieldPath);
      }
      // 如果配置里只有一个分页项且 groups 内只有一个 table 字段，直接关联以兜底
      if (!matched && paginationConfigs.length === 1) {
        const tableFieldsCount = (outputConfig.groups || []).reduce((acc: number, g: any) => {
          const cnt = (g.output_fields || []).filter((f: any) => f?.field_config?.field_type === 'table').length;
          return acc + cnt;
        }, 0);
        if (tableFieldsCount === 1) {
          [matched] = paginationConfigs;
        }
      }
      return matched;
    };

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
              // 将值转换为可渲染的字符串
              const toDisplayString = (val: any): string => {
                if (val === null || val === undefined) return '--';
                if (typeof val === 'object') return JSON.stringify(val);
                return String(val);
              };

              const rawVal = row[item.raw_name];
              const rawValStr = toDisplayString(rawVal);
              // 如果有enum映射，优先用映射的name
              const mappings = item.enum_mappings?.mappings;
              const mapped = Array.isArray(mappings) && mappings.length
                ? mappings.find((m: any) => String(m.key) === String(rawVal))
                : undefined;
              // display 始终是字符串，可以安全渲染
              const display = mapped ? toDisplayString(mapped.name) : rawValStr;
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
          }));

          const matchedPaginationConfig = findPaginationConfig(field);
          const initialLimit = matchedPaginationConfig?.default_page_size ?? 10;
          const initialCurrent = matchedPaginationConfig?.default_page ?? 1;
          // bk-pagination 分页配置：保证默认值在 limitList 内
          const baseLimitList = [10, 20, 50, 100, 200, 500, 1000];
          const limitList = baseLimitList.includes(initialLimit)
            ? baseLimitList
            : [...baseLimitList, initialLimit].sort((a, b) => a - b);

          tableFields.push({
            raw_name: field.raw_name,
            display_name: field.display_name || field.raw_name,
            description: field.description || '',
            path: field.json_path || '',
            columns: tableColumns,
            tableData: [],
            pagination: {
              current: initialCurrent,
              limit: initialLimit,
              count: 0,
              limitList,
            },
            paginationConfig: matchedPaginationConfig
              ? {
                page_param_raw_name: matchedPaginationConfig.page_param?.raw_name || '',
                page_size_param_raw_name: matchedPaginationConfig.page_size_param?.raw_name || '',
                total_path: matchedPaginationConfig.total_field?.json_path || '',
              }
              : undefined,
          });
        }
      });

      return {
        name: group.name,
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

    // 如果是用户主动翻页/切条数触发的请求（pendingPageMap 有记录），
    // 则只更新数据，不重建 groupData 结构（保留分页状态和 DOM 实例）
    if (isUserPaginating && pendingPageMap.size > 0 && groupData.value.length > 0) {
      isUserPaginating = false;
      nextTick(() => {
        if (!data.data?.result) return;
        const { result } = data.data;
        // 只更新数据，不动分页状态
        groupData.value.forEach((group) => {
          group.kv_fields.forEach((kvField) => {
            // eslint-disable-next-line no-param-reassign
            kvField.resolvePathValue = extractDataByPath(result, kvField.path) === null
              || extractDataByPath(result, kvField.path) === undefined ? '--'
              : extractDataByPath(result, kvField.path);
          });
          group.table_fields.forEach((tableField) => {
            const tableData = extractDataByPath(result, tableField.path);
            let finalTableData: any[] = [];
            if (Array.isArray(tableData)) {
              finalTableData = tableData.map((item, index) => ({
                ...item,
                __uniqueId: index + 1,
              }));
            } else if (tableData) {
              finalTableData = [{ ...tableData, __uniqueId: 1 }];
            }
            // eslint-disable-next-line no-param-reassign
            tableField.tableData = finalTableData;

            // 更新 total（同原有逻辑）
            const enablePagination = !!props.toolDetails?.config?.output_config?.enable_pagination;
            const paginationConfigs = props.toolDetails?.config?.output_config?.pagination_config || [];
            const totalPathCandidates: string[] = [];
            if (tableField.paginationConfig?.total_path) {
              totalPathCandidates.push(tableField.paginationConfig.total_path);
            }
            if (enablePagination) {
              paginationConfigs.forEach((cfg: any) => {
                const p = cfg?.total_field?.json_path;
                if (p && !totalPathCandidates.includes(p)) totalPathCandidates.push(p);
              });
            }
            let resolved: any;
            const tryRoots = [result, data.data, data];
            for (const path of totalPathCandidates) {
              for (const root of tryRoots) {
                const v = extractDataByPath(root, path);
                if (v !== null && v !== undefined) {
                  resolved = v; break;
                }
              }
              if (resolved !== undefined) break;
            }

            if (resolved === undefined && totalPathCandidates.length > 0) {
              const keys = totalPathCandidates
                .map((p: string) => (p.split('.').pop() || '').trim())
                .filter(Boolean);
              for (const k of keys) {
                const v = deepFindNumberByKey(result, k);
                if (v !== null) {
                  resolved = v; break;
                }
              }
            }
            const totalNum = Number(resolved);
            if (Number.isFinite(totalNum) && totalNum >= 0) {
              // eslint-disable-next-line no-param-reassign
              tableField.pagination.count = Math.max(totalNum, tableField.tableData.length);
            } else {
              // eslint-disable-next-line no-param-reassign
              tableField.pagination.count = tableField.tableData.length;
            }
          });
        });
        key.value += 1;
        tableReady.value = true;
      });
      return; // 翻页请求：增量更新完毕，不执行后续的完整重建逻辑
    }

    // 首次加载或非翻页请求：完整重建 groupData
    isUserPaginating = false;
    const previousPaginationState = new Map<string, { current: number; limit: number }>();
    groupData.value.forEach((group, gIdx) => {
      group.table_fields.forEach((tf, tIdx) => {
        if (tf.paginationConfig) {
          previousPaginationState.set(`${gIdx}-${tIdx}-${tf.raw_name}`, {
            current: tf.pagination.current,
            limit: tf.pagination.limit,
          });
        }
      });
    });
    tableReady.value = false;
    groupData.value = createGroupData(props.toolDetails);

    // 还原用户已调整的后端分页状态（优先级：pendingPageMap > previousPaginationState > 默认值）
    groupData.value.forEach((group, gIdx) => {
      group.table_fields.forEach((tf, tIdx) => {
        if (!tf.paginationConfig) return;
        const key = `${gIdx}-${tIdx}-${tf.raw_name}`;
        // 1. 优先使用用户最近一次翻页/切条数的意图
        const pending = pendingPageMap.get(key);
        if (pending) {
          // eslint-disable-next-line no-param-reassign
          if (pending.current !== undefined) tf.pagination.current = pending.current;
          // eslint-disable-next-line no-param-reassign
          if (pending.limit !== undefined) tf.pagination.limit = pending.limit;
          return; // 已恢复，跳过后续逻辑
        }
        // 2. 其次使用上一次的状态
        const prev = previousPaginationState.get(key);
        if (prev) {
          // eslint-disable-next-line no-param-reassign
          tf.pagination.current = prev.current;
          // eslint-disable-next-line no-param-reassign
          tf.pagination.limit = prev.limit;
        }
      });
    });

    // 异步更新 groupData，填充数据
    nextTick(() => {
      if (data.data.status_code === 200 && data.data.result) {
        const { result } = data.data;
        // 更新每个 group 的 table_fields 数据
        groupData.value.forEach((group) => {
          group.kv_fields.forEach((kvField) => {
            // eslint-disable-next-line no-param-reassign
            kvField.resolvePathValue = extractDataByPath(result, kvField.path) === null
              || extractDataByPath(result, kvField.path) === undefined ? '--'
              : extractDataByPath(result, kvField.path);
          });
          group.table_fields.forEach((tableField) => {
            const tableData = extractDataByPath(result, tableField.path);
            let finalTableData: any[] = [];
            let count = 0;
            if (Array.isArray(tableData)) {
              // 为每条数据添加自增 id
              finalTableData = tableData.map((item, index) => ({
                ...item,
                __uniqueId: index + 1,
              }));
              count = tableData.length;
            } else if (tableData) {
              finalTableData = [{
                ...tableData,
                __uniqueId: 1,
              }];
              count = 1;
            }
            // eslint-disable-next-line no-param-reassign
            tableField.tableData = finalTableData;

            const enablePagination = !!props.toolDetails?.config?.output_config?.enable_pagination;
            const paginationConfigs = props.toolDetails?.config?.output_config?.pagination_config || [];

            const totalPathCandidates: string[] = [];
            if (tableField.paginationConfig?.total_path) {
              totalPathCandidates.push(tableField.paginationConfig.total_path);
            }
            if (enablePagination) {
              paginationConfigs.forEach((cfg: any) => {
                const p = cfg?.total_field?.json_path;
                if (p && !totalPathCandidates.includes(p)) totalPathCandidates.push(p);
              });
            }

            // 1) 路径精确匹配（含双根尝试，兼容历史/异常配置）
            let resolved: any;
            const tryRoots = [result, data.data, data];
            for (const path of totalPathCandidates) {
              for (const root of tryRoots) {
                const v = extractDataByPath(root, path);
                if (v !== null && v !== undefined) {
                  resolved = v;
                  break;
                }
              }
              if (resolved !== undefined) break;
            }

            // 2) 兜底：根据路径最后一段（如 'total'）在响应里全局深搜
            if (resolved === undefined && totalPathCandidates.length > 0) {
              const keys = totalPathCandidates
                .map(p => (p.split('.').pop() || '').trim())
                .filter(Boolean);
              for (const k of keys) {
                const v = deepFindNumberByKey(result, k);
                if (v !== null) {
                  resolved = v;
                  // eslint-disable-next-line no-console
                  console.warn(
                    `[api-search-result] total 路径精确匹配失败，已通过深搜 key='${k}' 兜底为 ${v}`,
                    { totalPathCandidates, sampleResult: result },
                  );
                  break;
                }
              }
            }

            const totalNum = Number(resolved);
            if (Number.isFinite(totalNum) && totalNum >= 0) {
              // 取后端返回的 total 和当前页实际数据量的较大值（防止 total 不准确）
              // eslint-disable-next-line no-param-reassign
              tableField.pagination.count = Math.max(totalNum, tableField.tableData.length);
              return;
            }

            if (enablePagination) {
              // eslint-disable-next-line no-console
              console.warn(
                '[api-search-result] 分页 total 解析失败，请检查工具"数据总条数字段"配置是否与运行时响应结构一致',
                { totalPathCandidates, sampleResult: result },
              );
            }
            // 兜底：使用当前页返回的数据条数
            // eslint-disable-next-line no-param-reassign
            tableField.pagination.count = count;
          });
        });

        key.value += 1;
        tableReady.value = true;
      } else {
        // 没有有效结果时也要恢复 tableReady，让空状态/错误占位能正常显示后续重试结果
        tableReady.value = true;
      }
    });
  });
</script>

<style scoped lang="postcss">
/* stylelint-disable */
:deep(.card-content) {
  padding: 16px;
  background-color: #fafbfd;
  border: .5px solid #dcdee5;
  border-bottom-right-radius: 2px;
  border-bottom-left-radius: 2px;

  .top-search-table-title {
    margin: 10px 0;
    font-size: 12px;
  }

  .table-field-divider {
    height: 1px;
    margin: 12px 16px;
    background-color: #eaebf0;
  }

  .kv-field-item {
    .info-label {
      width: fit-content !important;
      max-width: 400px !important;
      min-width: 120px !important;
    }
  }

  .pagination-wrapper {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    padding: 8px 16px;

    :deep(.bk-pagination) {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
    }

    /* 页码列表推到右边（多选器兜底） */
    :deep(.bk-pagination .bk-paging-list),
    :deep(.bk-pagination .bk-page-list),
    :deep(.bk-pagination .bk-pagination-list),
    :deep(.bk-pagination .is-last),
    :deep(.bk-pagination > *:nth-last-child(1)) {
      margin-left: auto;
    }


  }
}

.single-content {
  padding: 0;
  background-color: #fff;
}

.top-search-table {
  /* 防止父容器产生额外的滚动条，只保留表格自身的内部滚动 */
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
}
</style>
<style  lang="postcss">
.api-search-result-table {
  :deep(.t-table--header-wrapper) {
    background-color: #f0f1f5 !important;
  }

  :deep(.t-table__footer) {
    background-color: #fff;
  }
}

/* 分页器：共x条/每页x条 在左，页码在右 */
.api-result-pagination .bk-pagination {
  display: flex !important;
  align-items: center;
  width: 100%;
}

.api-result-pagination .bk-pagination > *:nth-last-child(1) {
  margin-left: auto !important;
}
</style>
