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
      <!-- 已选系统 -->
      <div class="systems-section">
        <div
          class="systems-header"
          @click="systemsExpanded = !systemsExpanded">
          <div class="systems-title">
            <img
              alt=""
              class="title-icon"
              :src="wenhaoIcon">
            <span>已选系统</span>
          </div>
          <audit-icon
            class="expand-icon"
            :class="{ 'is-collapsed': !systemsExpanded }"
            type="angle-line-down" />
        </div>
        <template v-if="systemsExpanded">
          <div class="system-tags">
            <span
              v-for="item in systems"
              :key="item.id"
              class="system-tag">
              {{ item.name }}({{ item.id }})
            </span>
          </div>
          <div
            class="reselect-link"
            @click.stop="$emit('reselect')">
            <audit-icon
              class="reselect-icon"
              type="refresh" />
            <span>重新选择</span>
          </div>
        </template>
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
                <th>检索方式</th>
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

    <div
      v-if="filterCardShow"
      ref="filterCardAnchorRef"
      class="condition-filter-slot">
      <condition-filter-card
        ref="filterCardRef"
        :extension-fields="extensionFields"
        :standard-fields="standardFields"
        :systems="systems"
        @searched="scrollFilterCardIntoView" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, nextTick, ref } from 'vue';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  import ConditionFilterCard from './condition-filter-card.vue';
  import { formatSampleValue } from '../../utils/map-ai-message';
  import type { SelectedSystem, SystemFieldRow } from '../../types';

  import wenhaoIcon from '@images/wenhao.svg';

  const props = withDefaults(defineProps<{
    systems: SelectedSystem[];
    commonOperations?: string[];
    historicalOperations?: string[];
    standardFields?: SystemFieldRow[];
    extensionFields?: SystemFieldRow[];
  }>(), {
    commonOperations: () => [],
    historicalOperations: () => [],
    standardFields: () => [],
    extensionFields: () => [],
  });

  const emit = defineEmits<{
    reselect: [];
    'select-suggestion': [text: string];
  }>();

  interface FieldRow {
    name: string;
    desc: string;
    sample: string;
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

  const systemsExpanded = ref(true);
  const fieldExpanded = ref(true);
  const fieldTab = ref<'common' | 'extend'>('common');
  const filterCardShow = ref(false);
  const filterCardRef = ref<{
    addOrFocusField?:(fieldName: string, sample?: string) => Promise<void> | void
  } | null>(null);
  const filterCardAnchorRef = ref<HTMLElement | null>(null);

  const fallbackCommonSuggestions = [
    '查询「替换为实际用户」近7天的删除操作',
    '查询「替换为实际安装包」近7天的下载操作',
    '查询「替换为实际安装包」近7天的成功操作',
    '查询「替换为实际用户」近30天的API操作',
  ];

  const commonSuggestions = computed(() => (
    (props.commonOperations.length ? props.commonOperations : fallbackCommonSuggestions)
      .slice(0, SUGGESTION_LIMIT)
  ));

  const historySuggestions = computed(() => (
    props.historicalOperations.slice(0, SUGGESTION_LIMIT)
  ));

  const mapToFieldRow = (field: SystemFieldRow): FieldRow => ({
    name: field.displayName || field.rawName,
    desc: field.description || '',
    sample: formatSampleValue(field.sampleValue),
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

  const scrollFilterCardIntoView = async () => {
    await nextTick();
    requestAnimationFrame(() => {
      filterCardAnchorRef.value?.scrollIntoView({
        behavior: 'smooth',
        block: 'end',
      });
    });
  };

  const handleFieldSearch = async (row: FieldRow, mode: 'nl' | 'filter') => {
    if (mode === 'filter') {
      filterCardShow.value = true;
      await nextTick();
      await filterCardRef.value?.addOrFocusField?.(row.rawName || row.name, row.sample);
      scrollFilterCardIntoView();
      return;
    }
    const sampleText = row.sample || '替换为实际值';
    // 文档：自然语言用 nl_name + sample_value → `{nl_name}为{sample_value}`
    emit('select-suggestion', `${row.nlName}为${sampleText}`);
  };
</script>

<style lang="postcss" scoped>
  .retrieval-guide-wrap {
    display: flex;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    flex-direction: column;
    gap: 16px;
    box-sizing: border-box;
  }

  .condition-filter-slot {
    width: 100%;
  }

  .retrieval-guide-card {
    display: flex;
    width: 100%;
    max-width: 100%;
    /* 撑满消息区剩余视口，减少卡片与输入框之间的大片空白 */
    height: calc(100vh - 160px);
    max-height: calc(100vh - 160px);
    min-height: 620px;
    padding: 20px 24px 24px;
    overflow: hidden;
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

  .systems-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
  }

  .systems-title {
    display: flex;
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

  .expand-icon {
    font-size: 14px;
    color: #979ba5;
    transition: transform .2s;

    &.is-collapsed {
      transform: rotate(-90deg);
    }
  }

  .system-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
    padding: 12px;
    background: #f0f5ff;
    border-radius: 4px;
  }

  .system-tag {
    display: inline-flex;
    max-width: 100%;
    height: 22px;
    padding: 0 8px;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-sizing: border-box;
  }

  .reselect-link {
    display: inline-flex;
    margin-top: 12px;
    color: #3a84ff;
    cursor: pointer;
    align-items: center;
    gap: 4px;

    &:hover {
      opacity: .85;
    }

    .reselect-icon {
      font-size: 14px;
    }
  }

  .suggest-section {
    margin-bottom: 8px;
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
    grid-template-columns: 1fr 1fr;
    gap: 16px 24px;
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
      width: 100%;
      color: inherit;
    }
  }

  .field-section {
    display: flex;
    margin-top: 16px;
    min-height: 0;
    flex: 1;
    flex-direction: column;
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
    flex: 1;
    min-height: 0;
    margin-top: 12px;
    overflow: auto;
    border: 1px solid #dcdee5;
    border-radius: 2px;
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
      border-bottom: 1px solid #dcdee5;
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
    }

    td {
      height: 42px;
      color: #63656e;
      background: #fff;
    }

    tbody tr:nth-child(even) td {
      background: #fafbfd;
    }

    tbody tr:last-child td {
      border-bottom: none;
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

    .col-actions {
      width: 20%;
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

      .col-actions {
        width: 18%;
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
