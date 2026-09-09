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
  <div class="retrieval-guide-wrap">
    <div class="retrieval-guide-card">
      <!-- 已选系统：编辑时保留标题，仅替换内容区 -->
      <div class="systems-section">
        <template v-if="isEditingSystem">
          <div class="systems-edit-header">
            <div class="systems-edit-title">
              <img
                alt=""
                class="title-icon"
                :src="wenhaoIcon">
              <span>已选系统</span>
            </div>
          </div>
          <div class="system-edit-panel">
            <bk-select
              v-model="editingSystemId"
              class="guide-system-picker"
              clearable
              filterable
              :input-search="false"
              :loading="systemListLoading"
              placeholder="请选择系统"
              :popover-options="selectPopoverOptions"
              :scroll-height="280">
              <bk-option
                v-for="item in displaySystemList"
                :key="item.id"
                :label="`${item.name}(${item.id})`"
                :value="item.id" />
            </bk-select>
            <div class="system-edit-actions">
              <bk-button
                class="confirm-btn"
                :disabled="!editingSystemId
                  || confirmingSystem
                  || editingSystemId === currentSystemId"
                :loading="confirmingSystem"
                theme="primary"
                @click.stop="handleConfirmSystem">
                确认修改
              </bk-button>
              <bk-button
                :disabled="confirmingSystem"
                @click.stop="handleCancelEditSystem">
                取消
              </bk-button>
            </div>
          </div>
        </template>
        <selected-systems-panel
          v-else
          action-placement="header"
          action-text="重新选择"
          :systems="systems"
          title="已选系统"
          @action="handleStartEditSystem" />
      </div>

      <!-- 建议操作 -->
      <div class="suggest-section">
        <div class="suggest-title">
          可按以下建议进行后续操作
        </div>
        <div class="suggest-columns">
          <div class="suggest-column">
            <div class="column-label">
              常用操作
            </div>
            <button
              v-for="(item, index) in commonSuggestions"
              :key="`common-${index}`"
              class="suggest-item"
              type="button"
              @click="$emit('select-suggestion', item)">
              <show-tooltips-text
                class="suggest-text"
                :data="item" />
            </button>
          </div>
          <div class="suggest-column">
            <div class="column-label">
              历史操作
            </div>
            <button
              v-for="(item, index) in historySuggestions"
              :key="`history-${index}`"
              class="suggest-item"
              type="button"
              @click="$emit('select-suggestion', item)">
              <show-tooltips-text
                class="suggest-text"
                :data="item" />
            </button>
          </div>
        </div>
      </div>

      <!-- 按字段检索 -->
      <div class="field-section">
        <div class="field-divider">
          <span class="divider-line" />
          <span class="divider-text">没有合适的操作？试试按字段检索</span>
          <span class="divider-line" />
        </div>
        <div class="field-toolbar">
          <div
            class="field-title"
            @click="fieldExpanded = !fieldExpanded">
            <span
              class="field-arrow"
              :class="{ 'is-collapsed': !fieldExpanded }" />
            <span>按字段检索</span>
          </div>
          <template v-if="fieldExpanded">
            <div class="field-tabs">
              <button
                class="field-tab"
                :class="{ 'is-active': fieldTab === 'common' }"
                type="button"
                @click="fieldTab = 'common'">
                通用字段
              </button>
              <button
                class="field-tab"
                :class="{ 'is-active': fieldTab === 'extend' }"
                type="button"
                @click="fieldTab = 'extend'">
                拓展字段
              </button>
            </div>
            <div class="field-tip">
              <audit-icon
                class="tip-icon"
                type="info-fill" />
              <span>可使用字段进行精准筛选，支持自然语言检索和条件筛选检索两种方式。</span>
            </div>
          </template>
        </div>

        <div
          v-if="fieldExpanded"
          class="field-table-wrap">
          <table
            class="field-table"
            :class="{ 'is-extend': fieldTab === 'extend' }">
            <thead>
              <tr>
                <th>字段名称</th>
                <th>字段说明</th>
                <th>最近一条数据</th>
                <th v-if="fieldTab === 'extend'">
                  所属系统
                </th>
                <th class="col-actions">
                  检索方式
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, index) in currentFieldRows"
                :key="`${fieldTab}-${row.name}-${index}`">
                <td class="col-name">
                  <show-tooltips-text
                    class="cell-text"
                    :data="row.name || ''"
                    :max-width="FIELD_TABLE_TOOLTIP_MAX_WIDTH"
                    :tooltip-content-class="FIELD_TABLE_TOOLTIP_CONTENT_CLASS"
                    :tooltip-max-height="FIELD_TABLE_TOOLTIP_MAX_HEIGHT" />
                </td>
                <td class="col-desc">
                  <show-tooltips-text
                    class="cell-text"
                    :data="row.desc || ''"
                    :max-width="FIELD_TABLE_TOOLTIP_MAX_WIDTH"
                    :tooltip-content-class="FIELD_TABLE_TOOLTIP_CONTENT_CLASS"
                    :tooltip-max-height="FIELD_TABLE_TOOLTIP_MAX_HEIGHT" />
                </td>
                <td class="col-sample">
                  <show-tooltips-text
                    class="cell-text"
                    :data="row.sample || ''"
                    :max-width="FIELD_TABLE_TOOLTIP_MAX_WIDTH"
                    :tooltip-content-class="FIELD_TABLE_TOOLTIP_CONTENT_CLASS"
                    :tooltip-max-height="FIELD_TABLE_TOOLTIP_MAX_HEIGHT" />
                </td>
                <td
                  v-if="fieldTab === 'extend'"
                  class="col-system">
                  <show-tooltips-text
                    class="cell-text"
                    :data="row.system || ''"
                    :max-width="FIELD_TABLE_TOOLTIP_MAX_WIDTH"
                    :tooltip-content-class="FIELD_TABLE_TOOLTIP_CONTENT_CLASS"
                    :tooltip-max-height="FIELD_TABLE_TOOLTIP_MAX_HEIGHT" />
                </td>
                <td class="col-actions">
                  <button
                    class="action-link"
                    type="button"
                    @click="handleFieldSearch(row, 'nl')">
                    自然语言
                  </button>
                  <button
                    class="action-link"
                    type="button"
                    @click="handleFieldSearch(row, 'filter')">
                    条件筛选
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';
  import { useRoute } from 'vue-router';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';
  import MetaManageService from '@service/meta-manage';
  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import {
    buildParentFieldLabelMap,
    formatSampleValue,
    resolveFieldSampleDisplay,
    resolveSystemFieldDisplayLabel,
  } from '../../utils/map-ai-message';
  import type { SelectedSystem, SystemFieldRow } from '../../types';

  import wenhaoIcon from '@images/wenhao.svg';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';
  import SelectedSystemsPanel from './selected-systems-panel.vue';

  const props = withDefaults(defineProps<{
    systems: SelectedSystem[];
    historicalOperations?: string[];
    standardFields?: SystemFieldRow[];
    extensionFields?: SystemFieldRow[];
    confirmingSystem?: boolean;
  }>(), {
    historicalOperations: () => [],
    standardFields: () => [],
    extensionFields: () => [],
    confirmingSystem: false,
  });

  const emit = defineEmits<{
    confirmSystem: [systemIds: string[], systems: SelectedSystem[]];
    'select-suggestion': [text: string];
    /** 自然语言字段检索：向输入框追加字段值 */
    'append-nl-field': [text: string];
    'open-condition-filter': [payload: { fieldName: string; sample?: string }];
  }>();

  interface FieldRow {
    name: string;
    desc: string;
    /** 表格 / 自然语言展示文案 */
    sample: string;
    /** 条件筛选回填用的原始值 */
    sampleRaw: string;
    system?: string;
    rawName: string;
    nlName: string;
    keys: string[];
  }

  const SUGGESTION_LIMIT = 4;
  /** 按字段检索表格 tooltip：限制宽度与高度，长 JSON 内容区内滚动 */
  const FIELD_TABLE_TOOLTIP_MAX_WIDTH = 480;
  const FIELD_TABLE_TOOLTIP_MAX_HEIGHT = '400px';
  const FIELD_TABLE_TOOLTIP_CONTENT_CLASS = 'show-tooltips-text-popup';

  const fieldExpanded = ref(true);
  const fieldTab = ref<'common' | 'extend'>('common');
  const isEditingSystem = ref(false);
  const editingSystemId = ref('');
  const route = useRoute();
  const { messageWarn } = useMessage();

  /** 常用操作：前端固定文案，不依赖后端 */
  const commonSuggestions = [
    '查询「替换为实际用户」近7天的删除操作',
    '查询「替换为实际安装包」近7天的下载操作',
    '查询「替换为实际安装包」近7天的成功操作',
    '查询「替换为实际用户」近30天API操作',
  ];

  const historySuggestions = computed(() => (
    props.historicalOperations.slice(0, SUGGESTION_LIMIT)
  ));

  const parentFieldLabelMap = computed(() => buildParentFieldLabelMap(props.standardFields));

  const mapToFieldRow = (field: SystemFieldRow): FieldRow => ({
    // 有 keys 时与日志检索一致：父中文名/子 key，避免 instance_data / instance_origin_data 同名混淆
    name: resolveSystemFieldDisplayLabel(field, parentFieldLabelMap.value),
    desc: field.description || '',
    sample: resolveFieldSampleDisplay(field),
    sampleRaw: formatSampleValue(field.sampleValue),
    system: field.systemName || field.systemId,
    rawName: field.rawName,
    nlName: field.nlName || field.displayName || field.rawName,
    keys: field.keys || [],
  });

  const commonFields = computed(() => props.standardFields.map(mapToFieldRow));
  const extendFields = computed(() => props.extensionFields.map(mapToFieldRow));

  const currentFieldRows = computed(() => (
    fieldTab.value === 'common' ? commonFields.value : extendFields.value
  ));

  const currentSystemId = computed(() => props.systems[0]?.id || '');

  const {
    loading: systemListLoading,
    data: systemList,
    run: fetchSystemList,
  } = useRequest(() => {
    const params = getSceneSystemParams();
    return MetaManageService.fetchSystemWithAction({
      scope_id: params.scope_id || '',
      scope_type: params.scope_type || '',
      audit_status__in: 'accessed',
    });
  }, {
    defaultValue: [],
    manual: true,
  });

  const fetchedSystemList = computed(() => (systemList.value || []).map(item => ({
    id: String(item.id),
    name: item.name,
  })));

  const displaySystemList = computed(() => {
    const selectedMap = new Map(props.systems.map(item => [item.id, item]));
    fetchedSystemList.value.forEach((item) => {
      if (!selectedMap.has(item.id)) {
        selectedMap.set(item.id, item);
      }
    });
    return [...selectedMap.values()];
  });

  const selectPopoverOptions = {
    extCls: 'sec-chat-system-select-popover',
    boundary: 'body',
    placement: 'bottom-start',
    autoPlacement: true,
    zIndex: 9999,
  } as const;

  watch(() => currentSystemId.value, (value) => {
    if (!isEditingSystem.value) {
      editingSystemId.value = value;
    }
  }, { immediate: true });

  watch(
    () => [
      String(route.query.scene_id || ''),
      String(route.query.scope_id || ''),
      String(route.query.scope_type || ''),
    ].join('|'),
    () => {
      if (!isEditingSystem.value) return;
      fetchSystemList().then((list) => {
        const ids = (list || []).map(item => String(item.id));
        if (
          editingSystemId.value
          && editingSystemId.value !== currentSystemId.value
          && !ids.includes(editingSystemId.value)
        ) {
          editingSystemId.value = '';
        }
      });
    },
  );

  const handleStartEditSystem = () => {
    isEditingSystem.value = true;
    editingSystemId.value = currentSystemId.value;
    fetchSystemList();
  };

  const handleCancelEditSystem = () => {
    isEditingSystem.value = false;
    editingSystemId.value = currentSystemId.value;
  };

  const handleConfirmSystem = () => {
    if (!editingSystemId.value) {
      messageWarn('请选择系统');
      return;
    }
    if (editingSystemId.value === currentSystemId.value) {
      isEditingSystem.value = false;
      return;
    }
    const system = displaySystemList.value.find(item => item.id === editingSystemId.value)
      || { id: editingSystemId.value, name: editingSystemId.value };
    emit('confirmSystem', [system.id], [system]);
  };

  watch(() => props.confirmingSystem, (loading) => {
    if (!loading) {
      isEditingSystem.value = false;
    }
  });

  /** 与 condition-fields fieldConfig key 对齐：raw_name[.keys...] */
  const toConditionFieldName = (row: FieldRow) => {
    if (row.rawName && row.keys?.length) {
      return `${row.rawName}.${row.keys.join('.')}`;
    }
    return row.rawName || row.name;
  };

  const handleFieldSearch = (row: FieldRow, mode: 'nl' | 'filter') => {
    if (mode === 'filter') {
      // 条件筛选：每次点击产出条件卡；未检索时由父级覆盖草稿，不向已有卡追加字段
      // 回填必须用原始值，避免把展示文案写进筛选条件
      // 扩展字段须带 keys，否则会误命中父字段（如 instance_data →「实例当前内容」）
      emit('open-condition-filter', {
        fieldName: toConditionFieldName(row),
        sample: row.sampleRaw,
      });
      return;
    }
    const sampleText = row.sample || '替换为实际值';
    // 文档：自然语言用 nl_name + 展示文案 → `{nl_name}为{sample_display}`，多选向输入框追加
    emit('append-nl-field', `${row.nlName}为${sampleText}`);
  };
</script>

<style lang="postcss" scoped>
  .retrieval-guide-wrap {
    display: flex;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    box-sizing: border-box;
  }

  .retrieval-guide-card {
    display: flex;
    width: 100%;
    max-width: 100%;
    padding: 20px 24px 24px;
    overflow: visible;
    font-size: 14px;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;
    flex-direction: column;
  }

  .systems-section {
    margin-bottom: 20px;
    flex-shrink: 0;
  }

  .systems-edit-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .systems-edit-title {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 500;
    line-height: 22px;
    color: #313238;

    .title-icon {
      display: block;
      width: 18px;
      height: 18px;
      flex-shrink: 0;
    }
  }

  .system-edit-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 12px;
  }

  .guide-system-picker {
    width: 100%;
  }

  .system-edit-actions {
    display: flex;
    gap: 8px;

    :deep(.bk-button) {
      min-width: 88px;
    }
  }

  .suggest-section {
    margin-bottom: 8px;
    min-width: 0;
    flex-shrink: 0;
  }

  .suggest-title {
    margin-bottom: 12px;
    font-size: 16px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .suggest-columns {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 16px 24px;
    width: 100%;
    min-width: 0;
  }

  .suggest-column {
    min-width: 0;
    overflow: hidden;
  }

  .column-label {
    margin-bottom: 8px;
    font-size: 12px;
    font-weight: 700;
    line-height: 20px;
    color: #313238;
  }

  .suggest-item {
    display: block;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    margin-bottom: 8px;
    padding: 8px 12px;
    overflow: hidden;
    font-size: 14px;
    line-height: 22px;
    color: #63656e;
    text-align: left;
    letter-spacing: 0;
    cursor: pointer;
    background: #f5f7fa;
    border: 1px solid transparent;
    border-radius: 4px;
    transition: background-color .15s, border-color .15s;
    box-sizing: border-box;

    &:last-child {
      margin-bottom: 0;
    }

    &:hover {
      color: #3a84ff;
      background: #f0f5ff;
      border-color: #c5d8ff;
    }

    .suggest-text {
      display: block;
      width: 100%;
      max-width: 100%;
      overflow: hidden;
      color: inherit;
    }
  }

  .field-section {
    display: flex;
    margin-top: 16px;
    flex-direction: column;
    flex-shrink: 0;
  }

  .field-divider {
    display: flex;
    margin-bottom: 16px;
    flex-shrink: 0;
    align-items: center;
    gap: 12px;

    .divider-line {
      flex: 1;
      height: 1px;
      background: #dcdee5;
    }

    .divider-text {
      flex-shrink: 0;
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
    }
  }

  .field-toolbar {
    display: flex;
    flex-wrap: wrap;
    flex-shrink: 0;
    align-items: center;
    gap: 12px 16px;
  }

  .field-title {
    display: flex;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
    cursor: pointer;
    user-select: none;
    align-items: center;
    gap: 6px;

    .field-arrow {
      display: inline-block;
      width: 0;
      height: 0;
      border-style: solid;
      border-width: 7px 5px 0;
      border-color: #63656e transparent transparent;
      transition: transform .2s;
      flex-shrink: 0;

      &.is-collapsed {
        transform: rotate(-90deg);
      }
    }
  }

  .field-tabs {
    display: inline-flex;
    padding: 2px;
    background: #f0f1f5;
    border-radius: 4px;
  }

  .field-tab {
    height: 28px;
    padding: 0 12px;
    font-size: 12px;
    line-height: 28px;
    color: #63656e;
    cursor: pointer;
    background: transparent;
    border: none;
    border-radius: 2px;

    &.is-active {
      color: #3a84ff;
      background: #fff;
      box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
    }
  }

  .field-tip {
    display: flex;
    flex: 1;
    min-width: 240px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
    align-items: flex-start;
    gap: 4px;

    .tip-icon {
      margin-top: 2px;
      font-size: 14px;
      color: #979ba5;
      flex-shrink: 0;
    }
  }

  .field-table-wrap {
    margin-top: 12px;
    max-height: min(504px, calc(100vh - 360px));
    overflow: auto;
    border-bottom: 1px solid #dcdee5;
    scrollbar-width: thin;
    scrollbar-color: #dcdee5 transparent;

    &::-webkit-scrollbar {
      width: 4px;
      height: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;
    }
  }

  .field-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;

    th,
    td {
      padding: 0 16px;
      overflow: hidden;
      font-size: 12px;
      line-height: 20px;
      text-align: left;
      vertical-align: middle;
      box-sizing: border-box;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      height: 42px;
      font-weight: 400;
      color: #313238;
      background: #fafbfd;
      border-bottom: 1px solid #dcdee5;
    }

    td {
      height: 42px;
      color: #63656e;
      background: #fff;
      border-bottom: none;
    }

    tbody tr:nth-child(even) td {
      background: #fafbfd;
    }

    .cell-text {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .col-name {
      width: 18%;
      font-weight: 400;
      color: #313238;
    }

    .col-desc {
      width: 34%;
    }

    .col-sample {
      width: 28%;
    }

    .col-system {
      width: 14%;
    }

    th.col-actions {
      text-align: left;
    }

    td.col-actions {
      padding-right: 32px;
      text-align: right;
    }

    .col-actions {
      width: 18%;
      overflow: visible;
      white-space: nowrap;
    }

    &.is-extend {
      .col-name {
        width: 16%;
      }

      .col-desc {
        width: 26%;
      }

      .col-sample {
        width: 24%;
      }
    }
  }

  .action-link {
    margin-right: 12px;
    padding: 0;
    font-size: 12px;
    line-height: 20px;
    color: #3a84ff;
    cursor: pointer;
    background: none;
    border: none;

    &:last-child {
      margin-right: 0;
    }

    &:hover {
      opacity: .85;
    }
  }

  @media (max-width: 720px) {
    .suggest-columns {
      grid-template-columns: 1fr;
    }

    .field-table {
      table-layout: auto;
    }
  }
</style>
<style lang="postcss">
  .sec-chat-system-select-popover {
    z-index: 9999 !important;
  }
</style>
