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
  <card-part-vue
    is-open
    :show-content="!isCollapsed"
    :show-icon="false">
    <template #title>
      <div class="pagination-title-bar">
        <audit-icon
          class="collapse-icon"
          :class="[{ 'is-collapsed': isCollapsed }]"
          type="angle-line-down"
          @click.stop="handleToggleCollapse" />
        <span class="title-text">{{ t('分页设置') }}</span>
      </div>
    </template>
    <template #content>
      <div
        ref="paginationRootRef"
        class="pagination-setting">
        <div class="enable-pagination-row">
          <span class="enable-pagination-label">{{ t('启用分页') }}</span>
          <bk-switcher
            v-model="enablePagination"
            theme="primary"
            @change="handleSwitchChange" />
        </div>
        <div
          v-if="enablePagination"
          class="pagination-table">
          <div class="pagination-table-content">
            <div class="table-header-row">
              <div class="table-cell is-required col-list-field">
                {{ t('数据列表字段') }}
              </div>
              <div class="table-cell is-required col-total-field">
                {{ t('数据总条数字段') }}
              </div>
              <div class="table-cell is-required col-page-param">
                {{ t('页码参数名') }}
              </div>
              <div class="table-cell is-required col-page-size-param">
                {{ t('每页条数参数名') }}
              </div>
              <div class="table-cell is-required col-default-page">
                {{ t('起始页码') }}
              </div>
              <div class="table-cell is-required col-default-page-size">
                {{ t('每页条数') }}
              </div>
              <div class="table-cell is-required col-position">
                {{ t('参数位置') }}
              </div>
              <div class="table-cell col-operation" />
            </div>
            <div
              v-for="(row, index) in paginationRows"
              :key="index"
              class="table-body-row">
              <div class="table-cell col-list-field">
                <bk-popover
                  :arrow="false"
                  ext-cls="pagination-field-popover"
                  :is-show="row.showListFieldPopover"
                  placement="bottom-start"
                  theme="light"
                  trigger="manual"
                  :width="320"
                  @after-hidden="() => { row.showListFieldPopover = false; closeAllPopovers(); }">
                  <div
                    class="field-selector pagination-field-trigger"
                    :class="[{ 'is-error': row.listFieldError }]"
                    @click="openPopover(paginationRows.indexOf(row), 'list_field')">
                    <bk-tag
                      v-if="row.list_field"
                      class="field-tag"
                      closable
                      @close.stop="handleClearField(row, 'list_field')">
                      <span
                        v-bk-tooltips="{
                          content: getFieldDisplayName(row.list_field),
                          placement: 'top',
                          disabled: !row.listFieldEllipsis,
                        }"
                        class="field-tag-text"
                        @mouseenter="(e: MouseEvent) => checkEllipsis(e, row, 'listFieldEllipsis')">
                        {{ getFieldDisplayName(row.list_field) }}
                      </span>
                    </bk-tag>
                    <span
                      v-else
                      class="placeholder">{{ t('请选择数据列表字段') }}</span>
                  </div>
                  <template #content>
                    <div class="field-tree-popover">
                      <bk-input
                        v-model="row.listFieldSearch"
                        clearable
                        :placeholder="t('搜索字段')"
                        style="margin-bottom: 8px;"
                        @clear="row.listFieldSearch = ''" />
                      <div class="tree-container">
                        <field-tree
                          :filter-text="row.listFieldSearch"
                          :nodes="arrayFieldNodes"
                          :selected-fields="getAllSelectedFields()"
                          type="array"
                          @select="(node: any) => handleSelectField(row, 'list_field', node)" />
                      </div>
                    </div>
                  </template>
                </bk-popover>
              </div>
              <div class="table-cell col-total-field">
                <bk-popover
                  :arrow="false"
                  ext-cls="pagination-field-popover"
                  :is-show="row.showTotalFieldPopover"
                  placement="bottom-start"
                  theme="light"
                  trigger="manual"
                  :width="320"
                  @after-hidden="() => { row.showTotalFieldPopover = false; closeAllPopovers(); }">
                  <div
                    class="field-selector pagination-field-trigger"
                    :class="[{ 'is-error': row.totalFieldError }]"
                    @click="openPopover(paginationRows.indexOf(row), 'total_field')">
                    <bk-tag
                      v-if="row.total_field"
                      class="field-tag"
                      closable
                      @close.stop="handleClearField(row, 'total_field')">
                      <span
                        v-bk-tooltips="{
                          content: getFieldDisplayName(row.total_field),
                          placement: 'top',
                          disabled: !row.totalFieldEllipsis,
                        }"
                        class="field-tag-text"
                        @mouseenter="(e: MouseEvent) => checkEllipsis(e, row, 'totalFieldEllipsis')">
                        {{ getFieldDisplayName(row.total_field) }}
                      </span>
                    </bk-tag>
                    <span
                      v-else
                      class="placeholder">{{ t('请选择数据总条数字段') }}</span>
                  </div>
                  <template #content>
                    <div class="field-tree-popover">
                      <bk-input
                        v-model="row.totalFieldSearch"
                        clearable
                        :placeholder="t('搜索字段')"
                        style="margin-bottom: 8px;"
                        @clear="row.totalFieldSearch = ''" />
                      <div class="tree-container">
                        <field-tree
                          :filter-text="row.totalFieldSearch"
                          :nodes="numberFieldNodes"
                          :selected-fields="getAllSelectedFields()"
                          type="number"
                          @select="(node: any) => handleSelectField(row, 'total_field', node)" />
                      </div>
                    </div>
                  </template>
                </bk-popover>
              </div>
              <div class="table-cell col-page-param">
                <bk-input
                  v-model="row.page_param_name"
                  :class="{ 'is-error-input': row.pageParamError }"
                  :placeholder="t('请输入类似 pageNum 的字段')"
                  @change="() => { row.pageParamError = false; }" />
              </div>
              <div class="table-cell col-page-size-param">
                <bk-input
                  v-model="row.page_size_param_name"
                  :class="{ 'is-error-input': row.pageSizeParamError }"
                  :placeholder="t('请输入类似 pageSize 的字段')"
                  @change="() => { row.pageSizeParamError = false; }" />
              </div>
              <div class="table-cell col-default-page">
                <bk-input
                  v-model="row.default_page"
                  :class="{ 'is-error-input': row.defaultPageError }"
                  :min="0"
                  :placeholder="t('请输入')"
                  type="number"
                  @change="() => { row.defaultPageError = false; }" />
              </div>
              <div class="table-cell col-default-page-size">
                <bk-select
                  v-model="row.default_page_size"
                  auto-focus
                  :class="{ 'is-error-select': row.defaultPageSizeError }"
                  @change="() => { row.defaultPageSizeError = false; }">
                  <bk-option
                    v-for="size in pageSizeOptions"
                    :id="size"
                    :key="size"
                    :name="String(size)" />
                </bk-select>
              </div>
              <div class="table-cell col-position">
                <bk-select
                  v-model="row.position"
                  auto-focus
                  :class="{ 'is-error-select': row.positionError }"
                  @change="() => { row.positionError = false; }">
                  <bk-option
                    v-for="pos in positionOptions"
                    :id="pos.id"
                    :key="pos.id"
                    :name="pos.name" />
                </bk-select>
              </div>
              <div class="table-cell col-operation operation">
                <audit-icon
                  class="op-icon"
                  type="add-fill"
                  @click="handleAddRow" />
                <audit-icon
                  class="op-icon"
                  type="reduce-fill"
                  @click="handleDeleteRow(index)" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </card-part-vue>
</template>

<script setup lang="tsx">
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CardPartVue from '../../card-part.vue';

  import { buildTree } from './build-tree';
  import FieldTree from './pagination-field-tree.vue';

  interface Props {
    resultData: any;
    inputVariableNames: string[];
    defaultPosition: string;
  }

  interface PaginationRow {
    list_field: string;
    total_field: string;
    page_param_name: string;
    page_size_param_name: string;
    default_page: number;
    default_page_size: number;
    position: string;
    // UI states
    showListFieldPopover: boolean;
    showTotalFieldPopover: boolean;
    listFieldSearch: string;
    totalFieldSearch: string;
    listFieldError: boolean;
    totalFieldError: boolean;
    pageParamError: boolean;
    pageSizeParamError: boolean;
    defaultPageError: boolean;
    defaultPageSizeError: boolean;
    positionError: boolean;
    listFieldEllipsis: boolean;
    totalFieldEllipsis: boolean;
  }

  interface Exposes {
    getPaginationConfig: () => { enable_pagination: boolean; pagination_config: any[] };
    setPaginationConfig: (data: any) => void;
    validate: () => boolean;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const enablePagination = ref(false);
  const isCollapsed = ref(false);
  const paginationRows = ref<PaginationRow[]>([]);
  const activePopoverRow = ref<number | null>(null); // 当前激活的弹层行索引
  const activePopoverField = ref<'list_field' | 'total_field' | null>(null); // 当前激活的弹层字段类型
  const paginationRootRef = ref<HTMLElement | null>(null);

  const pageSizeOptions = [10, 20, 50, 100, 200, 500];
  const positionOptions = [
    { id: 'query', name: 'Query' },
    { id: 'path', name: 'Path' },
    { id: 'body', name: 'Body' },
  ];

  const parsedTreeNodes = computed<any[]>(() => {
    if (!props.resultData) return [];
    try {
      const raw = typeof props.resultData === 'string'
        ? JSON.parse(props.resultData)
        : props.resultData;
      if (!raw) return [];
      // 已经是 build 过的 tree 数组（节点带 json_path/type 等字段）
      if (Array.isArray(raw)) {
        return raw;
      }
      // 原始 JSON 对象，构建为 tree
      return buildTree(raw);
    } catch {
      return [];
    }
  });

  const containsTable = (nodes: any[]): boolean => {
    if (!nodes || nodes.length === 0) return false;
    return nodes.some((node) => {
      if (node.type === 'table') return true;
      if ((node.type === 'object' || node.type === 'kv') && node.children && node.children.length > 0) {
        return containsTable(node.children);
      }
      return false;
    });
  };

  const buildPaginationNodes = (
    nodes: any[],
    rawData: any,
    type: 'array' | 'number',
    siblingsHaveTable = false,
  ): any[] => {
    const result: any[] = [];
    if (!nodes || nodes.length === 0) return result;

    // 当前层级是否与分页相关：当前兄弟节点中存在 table 节点
    const currentLevelHasTable = siblingsHaveTable || nodes.some(n => n.type === 'table');

    nodes.forEach((node) => {
      // 表格节点（数组项为对象的数组） —— 即"数组型字段"
      if (node.type === 'table') {
        if (type === 'array') {
          result.push({
            name: node.name,
            path: node.json_path,
            type: 'array',
            selectable: true,
            children: [],
          });
        }
        // type === 'number' 时，不进入 table 内部 list（list 内部为业务字段）
        return;
      }

      // 对象节点（根级 type='object' 或子级 type='kv' 且有 children）
      // buildTree 中根级对象节点 type 为 'object'，子级对象节点 type 为 'kv'
      if ((node.type === 'object' || node.type === 'kv') && node.children && node.children.length > 0) {
        // 仅当该对象内部（含后代）存在 table 节点时，才作为容器节点保留
        if (!containsTable(node.children)) return;
        const children = buildPaginationNodes(node.children, rawData, type, false);
        if (children.length > 0) {
          result.push({
            name: node.name,
            path: node.json_path,
            type: 'object',
            selectable: false,
            children,
          });
        }
        return;
      }

      // 叶子 kv 节点：根据原始值判断是否为数值型
      // 仅在"与分页相关"的对象层级（即兄弟中存在 table）下，number 兄弟节点才作为候选项
      if (node.type === 'kv') {
        if (type === 'number' && currentLevelHasTable) {
          // 优先通过原始 JSON 数据判断（调试模式）
          // 如果 rawData 为 null（编辑模式），则通过 buildTree 存储的 valueType 判断
          let isNumber = false;
          if (rawData) {
            const val = getRawValueByPath(rawData, node.json_path);
            isNumber = typeof val === 'number';
          } else if (node.valueType === 'number') {
            isNumber = true;
          }
          if (isNumber) {
            result.push({
              name: node.name,
              path: node.json_path,
              type: 'number',
              selectable: true,
              children: [],
            });
          }
        }
      }
    });

    return result;
  };

  // 通过 json_path 取原始 JSON 中的值（用于判断 number 类型）
  const getRawValueByPath = (data: any, path: string): any => {
    if (!data || !path) return undefined;
    const keys = path.split('.');
    let cur = data;
    for (let i = 0; i < keys.length; i++) {
      if (cur === null || cur === undefined) return undefined;
      cur = cur[keys[i]];
    }
    return cur;
  };

  // 取原始 JSON（用于 number 类型判断）
  const rawJsonData = computed(() => {
    if (!props.resultData) return null;
    try {
      const raw = typeof props.resultData === 'string'
        ? JSON.parse(props.resultData)
        : props.resultData;
      // 已 build 的 tree 数组无法判断 number，返回 null
      if (Array.isArray(raw)) return null;
      return raw;
    } catch {
      return null;
    }
  });

  const arrayFieldNodes = computed(() => buildPaginationNodes(parsedTreeNodes.value, rawJsonData.value, 'array'));

  const numberFieldNodes = computed(() => buildPaginationNodes(parsedTreeNodes.value, rawJsonData.value, 'number'));

  const getFieldDisplayName = (path: string) => {
    if (!path) return '';
    const parts = path.split('.');
    const name = parts[parts.length - 1];
    return `${name}(${path})`;
  };

  const createEmptyRow = (): PaginationRow => ({
    list_field: '',
    total_field: '',
    page_param_name: '',
    page_size_param_name: '',
    default_page: 1,
    default_page_size: 10,
    position: props.defaultPosition || 'query',
    showListFieldPopover: false,
    showTotalFieldPopover: false,
    listFieldSearch: '',
    totalFieldSearch: '',
    listFieldError: false,
    totalFieldError: false,
    pageParamError: false,
    pageSizeParamError: false,
    defaultPageError: false,
    defaultPageSizeError: false,
    positionError: false,
    listFieldEllipsis: false,
    totalFieldEllipsis: false,
  });

  // hover 时检测文本是否被截断，仅截断时才显示 tooltip
  const checkEllipsis = (e: MouseEvent, row: PaginationRow, key: 'listFieldEllipsis' | 'totalFieldEllipsis') => {
    const target = e.target as HTMLElement;
    if (!target) return;
    /* eslint-disable-next-line no-param-reassign */
    row[key] = target.scrollWidth > target.clientWidth;
  };

  // 检查字段是否已被其他行使用
  const isFieldUsed = (field: 'list_field' | 'total_field', path: string, currentIndex: number): boolean => paginationRows.value.some((row, index) => index !== currentIndex && row[field] === path);

  // 获取所有已选字段路径（用于跨行重复选择校验）
  const getAllSelectedFields = (): string[] => {
    const fields: string[] = [];
    paginationRows.value.forEach((row) => {
      if (row.list_field) fields.push(row.list_field);
      if (row.total_field) fields.push(row.total_field);
    });
    return fields;
  };

  // 关闭所有弹层
  const closeAllPopovers = () => {
    paginationRows.value.forEach((row) => {
      /* eslint-disable no-param-reassign */
      row.showListFieldPopover = false;
      row.showTotalFieldPopover = false;
      /* eslint-enable no-param-reassign */
    });
    activePopoverRow.value = null;
    activePopoverField.value = null;
  };

  // 打开弹层
  const openPopover = (rowIndex: number, field: 'list_field' | 'total_field') => {
    closeAllPopovers();
    activePopoverRow.value = rowIndex;
    activePopoverField.value = field;

    const row = paginationRows.value[rowIndex];
    if (field === 'list_field') {
      row.showListFieldPopover = true;
      row.listFieldSearch = ''; // 重置搜索关键词
    } else {
      row.showTotalFieldPopover = true;
      row.totalFieldSearch = ''; // 重置搜索关键词
    }
  };

  const handleSwitchChange = (val: boolean) => {
    if (val && paginationRows.value.length === 0) {
      paginationRows.value.push(createEmptyRow());
    }
  };

  const handleToggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value;
  };

  const handleAddRow = () => {
    paginationRows.value.push(createEmptyRow());
  };

  const handleDeleteRow = (index: number) => {
    if (paginationRows.value.length <= 1 && enablePagination.value) {
      // 只剩1行时，清空内容但不删除行
      paginationRows.value[index] = createEmptyRow();
      return;
    }
    paginationRows.value.splice(index, 1);
  };

  const handleSelectField = (row: PaginationRow, field: 'list_field' | 'total_field', node: any) => {
    if (!node.selectable) return;

    const rowIndex = paginationRows.value.findIndex(r => r === row);
    if (isFieldUsed(field, node.path, rowIndex)) return;

    /* eslint-disable no-param-reassign */
    if (field === 'list_field') {
      row.list_field = node.path;
      row.showListFieldPopover = false;
      row.listFieldError = false;
    } else {
      row.total_field = node.path;
      row.showTotalFieldPopover = false;
      row.totalFieldError = false;
    }
    /* eslint-enable no-param-reassign */

    closeAllPopovers();
  };

  const handleClearField = (row: PaginationRow, field: 'list_field' | 'total_field') => {
    /* eslint-disable no-param-reassign */
    if (field === 'list_field') {
      row.list_field = '';
    } else {
      row.total_field = '';
    }
    /* eslint-enable no-param-reassign */
  };

  const validate = (): boolean => {
    if (!enablePagination.value) return true;

    let isValid = true;
    const inputNames = props.inputVariableNames || [];
    const rawNameRows: Array<{ pageRaw: string; sizeRaw: string }> = paginationRows.value.map(r => ({
      pageRaw: r.page_param_name && r.position
        ? `${r.page_param_name}${r.position}`
        : '',
      sizeRaw: r.page_size_param_name && r.position
        ? `${r.page_size_param_name}${r.position}`
        : '',
    }));

    paginationRows.value.forEach((row, index) => {
      /* eslint-disable no-param-reassign */
      // 校验必填
      if (!row.list_field) {
        row.listFieldError = true;
        isValid = false;
      }
      if (!row.total_field) {
        row.totalFieldError = true;
        isValid = false;
      }
      if (!row.page_param_name) {
        row.pageParamError = true;
        isValid = false;
      }
      if (!row.page_size_param_name) {
        row.pageSizeParamError = true;
        isValid = false;
      }
      if (row.default_page === null || row.default_page === undefined || String(row.default_page) === '') {
        row.defaultPageError = true;
        isValid = false;
      }
      if (!row.default_page_size) {
        row.defaultPageSizeError = true;
        isValid = false;
      }
      if (!row.position) {
        row.positionError = true;
        isValid = false;
      }

      // 校验生成的 raw_name 不能与 input_variable.raw_name 重名
      const { pageRaw, sizeRaw } = rawNameRows[index];
      if (pageRaw && inputNames.includes(pageRaw)) {
        row.pageParamError = true;
        isValid = false;
      }
      if (sizeRaw && inputNames.includes(sizeRaw)) {
        row.pageSizeParamError = true;
        isValid = false;
      }

      // 校验 raw_name 不重复
      // 由于规则改为 var_name + position（无后缀），同一行内 page 与 page_size 也可能撞名，需要校验
      const collidesWith = (target: string, currentIdx: number, isPage: boolean): boolean => {
        if (!target) return false;
        // 同一行内：page 与 page_size 互查
        const sameRowOther = isPage ? rawNameRows[currentIdx].sizeRaw : rawNameRows[currentIdx].pageRaw;
        if (sameRowOther && sameRowOther === target) return true;
        // 跨行：page/page_size 互不撞
        return rawNameRows.some((r, i) => i !== currentIdx && (r.pageRaw === target || r.sizeRaw === target));
      };
      if (pageRaw && collidesWith(pageRaw, index, true)) {
        row.pageParamError = true;
        isValid = false;
      }
      if (sizeRaw && collidesWith(sizeRaw, index, false)) {
        row.pageSizeParamError = true;
        isValid = false;
      }

      // 校验起始页码最小值为0
      if (Number(row.default_page) < 0) {
        row.defaultPageError = true;
        isValid = false;
      }

      // 校验跨行重复选择
      if (row.list_field && isFieldUsed('list_field', row.list_field, index)) {
        row.listFieldError = true;
        isValid = false;
      }
      if (row.total_field && isFieldUsed('total_field', row.total_field, index)) {
        row.totalFieldError = true;
        isValid = false;
      }
      /* eslint-enable no-param-reassign */
    });

    // 校验失败时，展开折叠并滚动到第一个错误项
    if (!isValid) {
      isCollapsed.value = false;
      nextTick(() => {
        const root = paginationRootRef.value;
        if (!root) return;
        const errorEl = root.querySelector('.is-error, .is-error-input, .is-error-select') as HTMLElement | null;
        const target = errorEl || root;
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }

    return isValid;
  };

  // 当 resultData 变更时（重新调试后），保持分页配置不变
  watch(() => props.resultData, () => {
    // 数据变更后不清空配置，让用户手动调整
  });

  const buildParamRawName = (varName: string, position: string): string => `${varName}${position}`;

  const getPaginationConfig = () => {
    // 将路径字符串转换为后端 ApiPaginationField 要求的 dict 格式
    const pathToFieldDict = (path: string) => {
      if (!path) return null;
      const parts = path.split('.');
      const rawName = parts[parts.length - 1];
      return {
        raw_name: rawName,
        json_path: path,
        display_name: rawName,
      };
    };
    return {
      enable_pagination: enablePagination.value,
      pagination_config: enablePagination.value
        ? paginationRows.value.map(row => ({
          list_field: pathToFieldDict(row.list_field),
          total_field: pathToFieldDict(row.total_field),
          page_param: {
            raw_name: buildParamRawName(row.page_param_name, row.position),
            var_name: row.page_param_name,
          },
          page_size_param: {
            raw_name: buildParamRawName(row.page_size_param_name, row.position),
            var_name: row.page_size_param_name,
          },
          default_page: Number(row.default_page),
          default_page_size: Number(row.default_page_size),
          position: row.position,
        }))
        : [],
    };
  };

  // 回填分页配置（兼容后端 dict 格式与旧字符串格式）
  const setPaginationConfig = (data: any) => {
    if (!data) return;
    enablePagination.value = data.enable_pagination || false;
    // 从后端 dict 格式或旧字符串格式中提取 json_path
    const extractPath = (field: any): string => {
      if (!field) return '';
      if (typeof field === 'string') return field;
      return field.json_path || '';
    };
    // 兼容新协议（page_param / page_size_param 为对象）与旧协议（page_param_name / page_size_param_name 为字符串）
    const extractParamVarName = (item: any, key: 'page_param' | 'page_size_param'): string => {
      const obj = item?.[key];
      if (obj && typeof obj === 'object') return obj.var_name || obj.raw_name || '';
      // 旧字段兜底
      const legacyKey = key === 'page_param' ? 'page_param_name' : 'page_size_param_name';
      return item?.[legacyKey] || '';
    };
    if (data.pagination_config && data.pagination_config.length > 0) {
      paginationRows.value = data.pagination_config.map((item: any) => ({
        ...createEmptyRow(),
        list_field: extractPath(item.list_field),
        total_field: extractPath(item.total_field),
        page_param_name: extractParamVarName(item, 'page_param'),
        page_size_param_name: extractParamVarName(item, 'page_size_param'),
        default_page: item.default_page ?? 1,
        default_page_size: item.default_page_size ?? 10,
        position: item.position || 'query',
      }));
    } else if (enablePagination.value) {
      paginationRows.value = [createEmptyRow()];
    }
  };

  defineExpose<Exposes>({
    getPaginationConfig,
    setPaginationConfig,
    validate,
  });

  // 点击弹层外部时关闭所有弹层
  const handleDocumentClick = (e: MouseEvent) => {
    // 当前没有打开的弹层，直接返回
    const hasOpen = paginationRows.value.some(r => r.showListFieldPopover || r.showTotalFieldPopover);
    if (!hasOpen) return;

    const target = e.target as HTMLElement | null;
    if (!target) return;

    // 点击在触发器或弹层内容内，不关闭
    if (target.closest('.pagination-field-trigger')) return;
    if (target.closest('.pagination-field-popover')) return;
    // 兼容 bk-select 下拉等 teleport 到 body 的弹层
    if (target.closest('.bk-select-popover')
      || target.closest('.bk-select-content-wrapper')
      || target.closest('.bk-popover2')
      || target.closest('.tippy-box')) return;

    closeAllPopovers();
  };

  onMounted(() => {
    document.addEventListener('mousedown', handleDocumentClick, true);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('mousedown', handleDocumentClick, true);
  });
</script>

<style lang="postcss" scoped>
.pagination-setting {
  padding-bottom: 10px;
}

.enable-pagination-row {
  display: flex;
  align-items: center;
  margin-bottom: 4px;

  .enable-pagination-label {
    margin-right: 12px;
    font-size: 12px;
    color: #63656e;
  }
}

.pagination-title-bar {
  display: flex;
  align-items: center;

  .collapse-icon {
    display: inline-block;
    margin-right: 8px;
    font-size: 14px;
    color: #63656e;
    cursor: pointer;
    transition: transform .2s ease;

    &.is-collapsed {
      transform: rotate(-90deg);
    }
  }

  .title-text {
    margin-right: 12px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .title-switch {
    cursor: pointer;
  }
}

.pagination-table {
  margin-top: 12px;

  .pagination-table-content {
    width: 100%;
    overflow-x: auto;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    .table-cell {
      box-sizing: border-box;
    }

    /* 数据列表字段 / 数据总条数字段：占据较多空间，可伸缩 */
    .col-list-field,
    .col-total-field {
      flex: 2 1 220px;
      min-width: 180px;
    }

    /* 页码参数名 / 每页条数参数名：可伸缩 */
    .col-page-param,
    .col-page-size-param {
      flex: 1 1 150px;
      min-width: 130px;
    }

    /* 起始页码 / 每页条数 / 参数位置：可伸缩 */
    .col-default-page,
    .col-default-page-size,
    .col-position {
      flex: 1 1 110px;
      min-width: 100px;
    }

    /* 操作列：固定窄宽 */
    .col-operation {
      flex: 0 0 80px;
      min-width: 80px;
    }

    .table-header-row,
    .table-body-row {
      /* 整体最小宽度：保证小屏下表格仍可横向滚动而不挤压 */
      min-width: 960px;
    }

    .table-header-row {
      display: flex;
      height: 42px;
      font-size: 12px;
      line-height: 42px;
      color: #313238;
      background: #f0f1f5;
      border-bottom: 1px solid #dcdee5;

      .table-cell {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        padding: 0 12px;
        text-align: left;
        border-left: 1px solid #dcdee5;

        &:first-child {
          border-left: none;
        }

        &.col-operation {
          justify-content: center;
          text-align: center;
        }

        &.is-required::after {
          margin-left: 4px;
          color: #ea3636;
          content: '*';
        }
      }
    }

    .table-body-row {
      display: flex;
      min-height: 42px;
      font-size: 12px;
      line-height: 42px;
      border-bottom: 1px solid #dcdee5;
      align-items: stretch;

      &:last-child {
        border-bottom: none;
      }

      .table-cell {
        display: flex;
        padding: 0;
        overflow: hidden;
        border-left: 1px solid #dcdee5;
        align-items: center;
        justify-content: flex-start;

        &:first-child {
          border-left: none;
        }

        &.operation {
          display: flex;
          justify-content: flex-start;
          align-items: center;
          padding-left: 16px;
        }
      }

      /* 单元格内部输入框/下拉框：去掉边框，与单元格融为一体 */
      :deep(.bk-input),
      :deep(.bk-select-trigger),
      :deep(.bk-select .bk-input) {
        width: 100%;
        height: 40px !important;
        background: transparent;
        border: none;
      }

      /* 输入框文字与表头 12px padding 对齐 */
      :deep(.bk-input .bk-input--text) {
        padding-left: 12px;
        background: transparent;
      }

      /* 下拉框文字与表头 12px padding 对齐（select 内部 input 已被以上规则覆盖） */
      :deep(.bk-select-trigger) {
        padding-left: 0;
      }

      :deep(.bk-input.is-focused:not(.is-readonly)) {
        border: 1px solid #3a84ff;
        outline: 0;
        box-shadow: 0 0 3px #a3c5fd;
      }

      :deep(.bk-select.is-focus .bk-select-trigger) {
        border: 1px solid #3a84ff;
      }

      :deep(.bk-input--text) {
        background: transparent;
      }
    }
  }
}

.field-selector {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 40px;
  padding: 0 12px;
  overflow: hidden;
  font-size: 12px;
  cursor: pointer;
  background: transparent;
  border: none;
  align-items: center;

  &.is-error {
    border: 1px solid #ea3636;
  }

  .placeholder {
    padding: 0;
    color: #c4c6cc;
  }

  .field-tag {
    display: inline-flex;
    max-width: 100%;
    margin: 0;
    overflow: hidden;
    line-height: normal;
    align-items: center;

    :deep(.bk-tag-text) {
      display: inline-flex;
      overflow: hidden;
      align-items: center;
    }

    .field-tag-text {
      display: inline-block;
      max-width: 100%;
      overflow: hidden;
      line-height: 1;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}

.field-tree-popover {
  max-height: 300px;
  padding: 8px;

  .tree-container {
    max-height: 250px;
    overflow-y: auto;
  }
}

:deep(.bk-input.is-error-input),
:deep(.is-error-input.bk-input),
:deep(.is-error-input .bk-input) {
  border: 1px solid #ea3636 !important;
}

:deep(.is-error-select .bk-select-trigger),
:deep(.is-error-select .bk-input),
:deep(.bk-select.is-error-select .bk-select-trigger),
:deep(.bk-select.is-error-select .bk-input) {
  border: 1px solid #ea3636 !important;
}

.op-icon {
  margin-left: 16px;
  font-size: 14px;
  color: #c4c6cc;
  cursor: pointer;

  &:first-child {
    margin-left: 0;
  }

  &:hover {
    color: #979ba5;
  }

  &.is-disabled {
    color: #dcdee5;
    cursor: not-allowed;

    &:hover {
      color: #dcdee5;
    }
  }
}
</style>
