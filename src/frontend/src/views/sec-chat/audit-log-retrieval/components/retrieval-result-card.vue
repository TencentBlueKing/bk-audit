<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
    10|  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div
    class="retrieval-result-wrap"
    :class="{ 'is-embedded': embedded }">
    <div
      class="retrieval-result-card"
      :class="{ 'is-embedded': embedded }">
      <!-- 已识别筛选条件：自然语言检索气泡展示，条件筛选内嵌结果不展示 -->
      <div
        v-if="!embedded"
        class="condition-section">
        <div class="condition-header">
          <audit-icon
            class="condition-icon"
            type="search1" />
          <span>{{ conditionHeaderText }}</span>
        </div>

        <!-- 可编辑：复用条件检索组件 -->
        <div
          v-if="conditionEditable"
          class="condition-editor">
          <condition-tags
            ref="conditionTagsRef"
            compact-select-popover
            :condition-list="[]"
            :event-field-items="[]"
            :field-config="fieldConfig"
            :search-model="searchModel"
            @clear-all="handleClearConditions"
            @remove="handleRemoveCondition"
            @update="handleUpdateCondition">
            <add-condition
              accent
              :event-fields="[]"
              :field-config="fieldConfig"
              :primary-field-names="commonFieldKeys"
              primary-tab-label="通用字段"
              :secondary-field-names="extendFieldKeys"
              secondary-source="config"
              secondary-tab-label="拓展字段"
              :selected-event-field-ids="[]"
              :selected-fields="selectedFieldNames"
              @add-field="handleAddField" />
          </condition-tags>

          <div class="condition-actions">
            <bk-button
              class="resubmit-btn"
              :loading="resubmitLoading"
              theme="primary"
              @click="handleResubmit">
              重新检索
            </bk-button>
          </div>
        </div>

        <!-- 兜底只读展示（无 rawCondition 或字段上下文缺失） -->
        <div
          v-else
          class="condition-tags">
          <span
            v-for="(item, index) in displayResult.conditions"
            :key="`${item.field}-${index}`"
            class="condition-tag">
            <span class="tag-label">{{ item.field }}：</span>
            <span class="tag-value">{{ item.value }}</span>
          </span>
        </div>
      </div>

      <!-- 过程信息：仅展示思考耗时，不可折叠 -->
      <div
        v-if="!embedded"
        class="process-section">
        <div class="process-row">
          <audit-icon
            class="process-arrow"
            type="angle-line-down" />
          <span>思考了 {{ displayResult.thinkSeconds }} 秒</span>
        </div>
      </div>

      <!-- 无命中：对齐条件检索空态，不展示空表/导出/分析 -->
      <div
        v-if="isEmpty"
        class="status-panel is-empty">
        <img
          alt=""
          class="empty-icon"
          :src="emptySearchIcon">
        <div class="status-title">
          检索结果为空
        </div>
        <div class="status-desc">
          可以尝试修改或减少检索条件
        </div>
      </div>

      <template v-else>
        <!-- 结果摘要 -->
        <div class="summary-section">
          <div class="summary-main">
            <h3 class="summary-title">
              {{ displayResult.title }}
            </h3>
            <p class="summary-desc">
              <template v-if="displayResult.showPreviewHint">
                共命中
                <span class="summary-num">{{ formatNumber(displayResult.totalHit) }}</span>
                条日志，数据量较大，已展示前
                <span class="summary-num">{{ displayResult.previewCount }}</span>
                条预览
              </template>
              <template v-else>
                共命中
                <span class="summary-num">{{ formatNumber(displayResult.totalHit) }}</span>
                条日志
              </template>
            </p>
          </div>
          <bk-dropdown
            class="export-dropdown"
            :disabled="!canExport || exporting"
            placement="bottom-start"
            trigger="click">
            <bk-button
              class="export-btn"
              :disabled="!canExport"
              :loading="exporting">
              <audit-icon
                class="export-icon"
                type="download" />
              {{ exporting ? '导出中…' : '导出' }}
            </bk-button>
            <template #content>
              <bk-dropdown-menu>
                <bk-dropdown-item
                  :disabled="exporting"
                  @click="handleExport('preview')">
                  导出前 {{ displayResult.previewCount }} 条数据
                </bk-dropdown-item>
                <bk-dropdown-item
                  :disabled="exporting"
                  @click="handleExport('all')">
                  导出全量数据
                </bk-dropdown-item>
              </bk-dropdown-menu>
            </template>
          </bk-dropdown>
        </div>

        <!-- 数据预览表 -->
        <div class="table-section">
          <div class="table-scroll">
            <table
              class="result-table"
              :style="{ minWidth: tableMinWidth }">
              <thead>
                <tr>
                  <th
                    v-for="col in displayResult.columns"
                    :key="col.rawName"
                    :style="getColumnStyle(col)">
                    <show-tooltips-text
                      class="cell-tip"
                      :data="col.displayName"
                      :max-width="360" />
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, index) in pageRows"
                  :key="`row-${index}`">
                  <td
                    v-for="col in displayResult.columns"
                    :key="`${col.rawName}-${index}`"
                    :class="{ 'result-code-cell': isResultCodeColumn(col) }"
                    :style="getColumnStyle(col)">
                    <render-result
                      v-if="isResultCodeColumn(col) && hasResultCodeValue(row)"
                      :data="row" />
                    <show-tooltips-text
                      v-else
                      class="cell-tip"
                      :data="formatCell(row[col.rawName])"
                      :max-width="480" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="table-pagination">
            <bk-pagination
              v-model="currentPage"
              align="right"
              :count="displayResult.rows.length"
              :layout="['total', 'limit', 'list']"
              :limit="pageSize"
              :limit-list="[10, 20, 50]"
              location="right"
              size="small"
              @change="handlePageChange"
              @limit-change="handleLimitChange" />
          </div>
        </div>

        <!-- 后续操作：本期先禁用智能分析 / 数据统计 -->
        <div class="action-section">
          <bk-button
            class="analyze-btn"
            disabled
            outline
            title="暂未开放"
            @click="analyzeDialogShow = true">
            <img
              alt=""
              class="ai-agent-ai"
              height="14"
              :src="aiSvg"
              width="24">
            智能分析
          </bk-button>
          <bk-button
            class="statistics-btn"
            disabled
            outline
            title="暂未开放"
            @click="handleStatistics">
            <audit-icon
              class="action-icon"
              type="shujutongji" />
            数据统计
          </bk-button>
        </div>

        <!-- 报告生成状态 -->
        <div
          v-if="reportItems.length"
          class="report-status-section"
          :class="{ 'is-done': hasDoneReport }">
          <div
            v-for="item in reportItems"
            :key="item.id"
            class="report-status-row">
            <template v-if="item.status === 'loading'">
              <audit-icon
                class="status-icon is-loading"
                type="loading" />
              <span class="status-text">{{ item.title }}生成中...</span>
            </template>
            <template v-else>
              <audit-icon
                class="status-icon is-success"
                type="success" />
              <span class="status-text">{{ item.title }}已生成</span>
              <span class="status-time">{{ item.createdAt }}</span>
              <button
                class="view-report-btn"
                type="button"
                @click="openReport(item)">
                <audit-icon
                  class="view-icon"
                  type="help-document-fill" />
                查看报告
              </button>
            </template>
          </div>
        </div>
      </template>

      <!-- 反馈操作：本期先不做，后续再开放 -->
      <div
        v-if="showFeedbackActions"
        class="feedback-row">
        <button
          class="feedback-btn"
          title="复制"
          type="button"
          @click="handleCopy">
          <audit-icon type="copy" />
        </button>
        <button
          class="feedback-btn"
          :class="{ 'is-active': feedback === 'up' }"
          title="有用"
          type="button"
          @click="feedback = feedback === 'up' ? '' : 'up'">
          <svg
            class="feedback-svg"
            fill="none"
            height="16"
            viewBox="0 0 16 16"
            width="16">
            <path
              :d="thumbUpPath"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.2" />
          </svg>
        </button>
        <button
          class="feedback-btn"
          :class="{ 'is-active': feedback === 'down' }"
          title="无用"
          type="button"
          @click="feedback = feedback === 'down' ? '' : 'down'">
          <svg
            class="feedback-svg"
            fill="none"
            height="16"
            viewBox="0 0 16 16"
            width="16">
            <path
              :d="thumbDownPath"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.2" />
          </svg>
        </button>
        <button
          class="feedback-btn"
          title="重新生成"
          type="button"
          @click="$emit('regenerate')">
          <audit-icon type="refresh" />
        </button>
      </div>
    </div>

    <log-analyze-dialog
      v-if="analyzeDialogShow"
      v-model="analyzeDialogShow"
      :conditions="displayResult.conditions"
      :total-hit="displayResult.totalHit"
      @select="handleAnalyzeSelect" />

    <log-statistics-dialog
      v-if="statisticsDialogShow"
      v-model="statisticsDialogShow"
      @confirm="handleStatisticsConfirm" />

    <log-report-drawer
      v-if="reportDrawerShow"
      v-model:is-show="reportDrawerShow"
      :conditions="displayResult.conditions"
      :report="activeReport"
      :systems="systemNames"
      :total-hit="displayResult.totalHit" />

    <log-statistics-drawer
      v-if="statisticsDrawerShow"
      v-model:is-show="statisticsDrawerShow"
      :created-at="statisticsCreatedAt"
      :fields="statisticsFields" />
  </div>
</template>

<script lang="ts" setup>
  import dayjs from 'dayjs';
  import { computed, nextTick, onBeforeUnmount, onDeactivated, ref, watch } from 'vue';

  import useMessage from '@hooks/use-message';

  import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

  import AddCondition from '@views/risk-manage/list/components/nl-search-box/components/add-condition.vue';
  import ConditionTags from '@views/risk-manage/list/components/nl-search-box/components/condition-tags.vue';
  import RenderResult from '@views/analysis-manage/list/components/search-result-table/components/render-field/result.vue';
  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  import aiSvg from '@images/ai.svg';
  import emptySearchIcon from '@images/empty-search.svg';

  import { useSecChatStore } from '../../composables/use-sec-chat-store';
  import type { RetrievalResultPayload, SelectedSystem, SystemFieldRow } from '../../types';
  import {
    buildAiSearchCondition,
    appendSearchModelField,
    createConditionFieldConfigFromSystemFields,
    createDefaultDatetime,
    createDefaultDatetimeOrigin,
    getConditionDefaultValue,
    getPrimaryFieldNames,
    getSecondaryFieldNames,
    parseAiSearchConditionToSearchModel,
  } from '../config/condition-fields';
  import {
    exportLogSearchFull,
    exportLogSearchPreview,
  } from '../utils/export-log-search';

  import LogAnalyzeDialog from './log-analyze-dialog.vue';
  import LogReportDrawer, { type LogReportInfo } from './log-report-drawer.vue';
  import LogStatisticsDialog from './log-statistics-dialog.vue';
  import LogStatisticsDrawer from './log-statistics-drawer.vue';

  const props = withDefaults(defineProps<{
    result: RetrievalResultPayload;
    /** LOG_SEARCH 成功消息 uid，导出接口必填 */
    messageUid?: string;
    embedded?: boolean;
    standardFields?: SystemFieldRow[];
    extensionFields?: SystemFieldRow[];
    systems?: SelectedSystem[];
  }>(), {
    messageUid: '',
    embedded: false,
    standardFields: () => [],
    extensionFields: () => [],
    systems: () => [],
  });

  const emit = defineEmits<{
    export: [mode: 'preview' | 'all'];
    analyze: [];
    statistics: [];
    regenerate: [];
  }>();

  const { appendConditionSearch } = useSecChatStore();

  /** 当前卡片展示的结果；二次检索会追加新消息卡，本卡保持原结果不变 */
  const displayResult = ref<RetrievalResultPayload>({ ...props.result });
  const displayMessageUid = ref(props.messageUid || '');

  /** 本期先隐藏底部反馈操作行 */
  const showFeedbackActions = false;

  interface ReportStatusItem extends LogReportInfo {
    status: 'loading' | 'done';
  }

  /** 多列时保证列宽可读，超出横向滚动 */
  const COLUMN_MIN_WIDTH = 140;
  const TIME_COLUMN_MIN_WIDTH = 220;

  const isTimeColumn = (col: { rawName: string; displayName: string }) => {
    const text = `${col.rawName} ${col.displayName}`;
    return /时间|time|date|datetime/i.test(text);
  };

  const getColumnWidth = (col: { rawName: string; displayName: string }) => (
    isTimeColumn(col) ? TIME_COLUMN_MIN_WIDTH : COLUMN_MIN_WIDTH
  );

  const getColumnStyle = (col: { rawName: string; displayName: string }) => {
    const width = getColumnWidth(col);
    return {
      width: `${width}px`,
      minWidth: `${width}px`,
      maxWidth: isTimeColumn(col) ? '260px' : '280px',
    };
  };

  const { messageSuccess, messageError, messageWarn } = useMessage();
  const exporting = ref(false);
  const resubmitLoading = ref(false);
  const conditionTagsRef = ref<{ startEditField?:(fieldName: string) => void }>();
  const searchModel = ref<Record<string, any>>({
    datetime: createDefaultDatetime(),
    datetime_origin: createDefaultDatetimeOrigin(),
  });

  const fieldConfig = computed(() => createConditionFieldConfigFromSystemFields(
    props.standardFields,
    props.extensionFields,
  ));
  const commonFieldKeys = computed(() => getPrimaryFieldNames(props.standardFields));
  const extendFieldKeys = computed(() => getSecondaryFieldNames(props.extensionFields));
  const selectedFieldNames = computed(() => Object.keys(searchModel.value)
    .filter(key => key !== 'datetime_origin' && fieldConfig.value[key]));

  const conditionEditable = computed(() => (
    Boolean(displayResult.value.rawCondition)
    && Object.keys(fieldConfig.value).length > 1
  ));

  const activeConditionCount = computed(() => (
    Object.keys(searchModel.value).filter(key => (
      key !== 'datetime_origin' && key !== 'sort' && fieldConfig.value[key]
    )).length
  ));

  const conditionHeaderText = computed(() => {
    if (conditionEditable.value) {
      return `已识别到 ${activeConditionCount.value} 个筛选条件，可修改后重新检索`;
    }
    return `已识别到 ${displayResult.value.conditions.length} 个筛选条件进行检索`;
  });

  const syncSearchModelFromResult = () => {
    const { rawCondition } = displayResult.value;
    if (!rawCondition) return;
    searchModel.value = parseAiSearchConditionToSearchModel(
      rawCondition,
      fieldConfig.value,
    );
  };

  watch(
    () => props.messageUid,
    () => {
      displayResult.value = props.result;
      displayMessageUid.value = props.messageUid || '';
      syncSearchModelFromResult();
    },
    { immediate: true },
  );

  watch(
    () => [props.standardFields, props.extensionFields] as const,
    () => {
      syncSearchModelFromResult();
    },
    { deep: true },
  );

  const getDefaultValue = (config: IFieldConfig) => getConditionDefaultValue(config);

  const appendField = (fieldName: string, value: any) => {
    searchModel.value = appendSearchModelField(
      searchModel.value,
      fieldName,
      value,
      {
        datetime: createDefaultDatetime(),
        datetimeOrigin: createDefaultDatetimeOrigin(),
      },
    );
  };

  const handleAddField = async (fieldName: string, config: IFieldConfig, initialValue?: any) => {
    if (fieldName !== 'datetime' && searchModel.value[fieldName] !== undefined) {
      conditionTagsRef.value?.startEditField?.(fieldName);
      return;
    }
    const value = initialValue !== undefined ? initialValue : getDefaultValue(config);
    appendField(fieldName, value);
    conditionTagsRef.value?.startEditField?.(fieldName);
    await nextTick();
  };

  const handleRemoveCondition = (fieldName: string) => {
    if (fieldName === 'datetime') return;
    const next = { ...searchModel.value };
    delete next[fieldName];
    searchModel.value = next;
  };

  const handleUpdateCondition = (fieldName: string, value: any) => {
    if (fieldName === 'datetime') {
      if (Array.isArray(value) && value.length >= 2) {
        const formatted = value.map((item: any) => (
          typeof item === 'number' || item instanceof Date
            ? dayjs(item).format('YYYY-MM-DD HH:mm:ss')
            : item
        ));
        searchModel.value.datetime = formatted;
        searchModel.value.datetime_origin = formatted;
      }
      return;
    }
    if (fieldName === 'datetime_origin') {
      searchModel.value.datetime_origin = value;
      return;
    }
    searchModel.value[fieldName] = value;
  };

  const handleClearConditions = () => {
    searchModel.value = {
      datetime: createDefaultDatetime(),
      datetime_origin: createDefaultDatetimeOrigin(),
    };
  };

  const handleResubmit = async () => {
    if (resubmitLoading.value) return;

    const scopeId = displayResult.value.rawCondition?.scope_id || props.systems[0]?.id || '';
    const condition = buildAiSearchCondition({
      scopeId,
      searchModel: searchModel.value,
      fieldConfig: fieldConfig.value,
    });
    if (!condition) {
      messageWarn(scopeId ? '请至少选择时间范围' : '请先选择系统');
      return;
    }

    resubmitLoading.value = true;
    try {
      const chatMessage = await appendConditionSearch(condition);
      if (chatMessage.apiStatus === 'FAILED') {
        messageError(chatMessage.errorMessage || '检索失败');
        return;
      }
      // 新卡已追加；旧卡条件还原为本卡原始结果，避免展示与表格不一致的新条件
      syncSearchModelFromResult();
    } catch (error: any) {
      messageError(error?.message || '检索失败，请稍后重试');
    } finally {
      resubmitLoading.value = false;
    }
  };

  const isEmpty = computed(() => displayResult.value.totalHit <= 0);
  const canExport = computed(() => (
    Boolean(displayMessageUid.value)
    && displayResult.value.totalHit > 0
  ));

  const thumbUpPath = 'M5.2 14.5H3.4c-.5 0-.9-.4-.9-.9V7.8c0-.5.4-.9.9-.9h1.8v7.6z'
    + 'M13.4 6.9H9.7l.5-2.4c.1-.6-.1-1.2-.5-1.6L9 2.2c-.2-.2-.5-.2-.7 0l-.2.2'
    + 'c-.2.2-.3.5-.2.8l.6 2.4H6.1v7.6h5.8c.7 0 1.3-.5 1.4-1.2l.7-4.2'
    + 'c.1-.7-.4-1.4-1.2-1.4h-.4z';
  const thumbDownPath = 'M10.8 1.5h1.8c.5 0 .9.4.9.9v5.8c0 .5-.4.9-.9.9h-1.8V1.5z'
    + 'M2.6 9.1h3.7l-.5 2.4c-.1.6.1 1.2.5 1.6l.7.7c.2.2.5.2.7 0l.2-.2'
    + 'c.2-.2.3-.5.2-.8l-.6-2.4h2.4V1.5H4.1c-.7 0-1.3.5-1.4 1.2L2 6.9'
    + 'c-.1.7.4 1.4 1.2 1.4h-.6z';

  const currentPage = ref(1);
  const pageSize = ref(10);
  const feedback = ref<'up' | 'down' | ''>('');
  const analyzeDialogShow = ref(false);
  const statisticsDialogShow = ref(false);
  const reportItems = ref<ReportStatusItem[]>([]);
  const reportDrawerShow = ref(false);
  const activeReport = ref<LogReportInfo | null>(null);
  const statisticsDrawerShow = ref(false);
  const statisticsCreatedAt = ref('');
  const statisticsFields = ref<string[]>([]);
  let generateTimer: ReturnType<typeof setTimeout> | null = null;

  const pageRows = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value;
    return displayResult.value.rows.slice(start, start + pageSize.value);
  });

  const tableMinWidth = computed(() => {
    const total = displayResult.value.columns.reduce((sum, col) => sum + getColumnWidth(col), 0);
    return `${Math.max(total, 760)}px`;
  });

  const hasDoneReport = computed(() => reportItems.value.some(item => item.status === 'done'));

  const systemNames = computed(() => {
    const systemCond = displayResult.value.conditions.find(item => item.field === '来源系统');
    return systemCond?.value || '已选系统';
  });

  watch(() => displayResult.value, () => {
    currentPage.value = 1;
    feedback.value = '';
    reportItems.value = [];
    reportDrawerShow.value = false;
    activeReport.value = null;
    statisticsDrawerShow.value = false;
    statisticsFields.value = [];
    if (generateTimer) {
      clearTimeout(generateTimer);
      generateTimer = null;
    }
  });

  onBeforeUnmount(() => {
    if (generateTimer) clearTimeout(generateTimer);
  });

  // keep-alive 失活时卸载弹层，避免消息多时大量 teleport/sideslider 残留导致切回白屏
  onDeactivated(() => {
    analyzeDialogShow.value = false;
    statisticsDialogShow.value = false;
    reportDrawerShow.value = false;
    statisticsDrawerShow.value = false;
  });

  const formatNumber = (num: number) => num.toLocaleString('en-US');

  const isResultCodeColumn = (col: { rawName: string }) => col.rawName === 'result_code';

  const hasResultCodeValue = (row: Record<string, any>) => {
    const value = row.result_code;
    return value !== undefined && value !== null && value !== '';
  };

  const formatCell = (value: any) => {
    if (value === undefined || value === null || value === '') return '—';
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
    return String(value);
  };

  const formatNow = () => {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };

  const handlePageChange = (page: number) => {
    currentPage.value = page;
  };

  const handleLimitChange = (limit: number) => {
    pageSize.value = limit;
    currentPage.value = 1;
  };

  const handleExport = async (mode: 'preview' | 'all') => {
    if (!canExport.value || exporting.value) return;
    if (!displayMessageUid.value) {
      messageWarn('缺少消息标识，无法导出');
      return;
    }

    exporting.value = true;
    emit('export', mode);
    try {
      if (mode === 'preview') {
        await exportLogSearchPreview(displayMessageUid.value);
        messageSuccess(`已导出前 ${displayResult.value.previewCount} 条数据`);
      } else {
        await exportLogSearchFull(displayMessageUid.value);
        messageSuccess('导出任务已创建，结果将发送至邮箱，请注意查收');
      }
    } catch (error: any) {
      messageError(error?.message || '导出失败，请稍后重试');
    } finally {
      exporting.value = false;
    }
  };

  const startGenerate = (
    items: Array<{ id: string; type: 'analyze' | 'statistics'; title: string }>,
    options?: { openStatistics?: boolean; fields?: string[] },
  ) => {
    if (generateTimer) clearTimeout(generateTimer);
    reportItems.value = items.map(item => ({
      ...item,
      status: 'loading',
      createdAt: '',
    }));
    generateTimer = setTimeout(() => {
      const createdAt = formatNow();
      reportItems.value = reportItems.value.map(item => ({
        ...item,
        status: 'done',
        createdAt,
      }));
      if (options?.openStatistics) {
        statisticsFields.value = options.fields || [];
        statisticsCreatedAt.value = createdAt;
        statisticsDrawerShow.value = true;
      } else {
        const primary = reportItems.value.find(item => item.type === 'analyze') || reportItems.value[0];
        if (primary) openReport(primary);
      }
      generateTimer = null;
    }, 1600);
  };

  const handleAnalyzeSelect = (payload: { type: 'recommend' | 'custom'; title: string; prompt?: string }) => {
    emit('analyze');
    void payload;
    startGenerate([
      { id: `analyze-${Date.now()}`, type: 'analyze', title: '智能分析报告' },
      { id: `stats-${Date.now()}`, type: 'statistics', title: '数据统计报告' },
    ]);
  };

  const handleStatistics = () => {
    statisticsDialogShow.value = true;
  };

  const handleStatisticsConfirm = (payload: { fields: string[]; customPrompt?: string }) => {
    emit('statistics');
    void payload.customPrompt;
    startGenerate(
      [{ id: `stats-${Date.now()}`, type: 'statistics', title: '数据统计报告' }],
      { openStatistics: true, fields: payload.fields },
    );
  };

  const openReport = (item: ReportStatusItem | LogReportInfo) => {
    if (item.type === 'statistics') {
      statisticsFields.value = statisticsFields.value.length ? statisticsFields.value : [];
      statisticsCreatedAt.value = ('createdAt' in item && item.createdAt) ? item.createdAt : formatNow();
      statisticsDrawerShow.value = true;
      return;
    }
    activeReport.value = {
      id: item.id,
      type: item.type,
      title: item.title,
      createdAt: 'createdAt' in item ? item.createdAt : formatNow(),
    };
    reportDrawerShow.value = true;
  };

  const handleCopy = async () => {
    const text = [
      displayResult.value.title,
      `共命中 ${displayResult.value.totalHit} 条`,
      ...displayResult.value.conditions.map(item => `${item.field}：${item.value}`),
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
      messageSuccess('已复制');
    } catch {
      // ignore
    }
  };
</script>

<style lang="postcss" scoped>
  .retrieval-result-wrap {
    display: flex;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    flex-direction: column;
    box-sizing: border-box;

    &.is-embedded {
      width: 100%;
    }
  }

  .retrieval-result-card {
    width: 100%;
    padding: 20px 24px 24px;
    font-size: 14px;
    line-height: 22px;
    color: #63656e;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;

    &.is-embedded {
      padding: 0;
      background: transparent;
      border: none;
      border-radius: 0;
      box-shadow: none;
    }
  }

  .condition-section {
    margin-bottom: 16px;
  }

  .condition-header {
    display: flex;
    margin-bottom: 12px;
    font-size: 14px;
    line-height: 22px;
    color: #313238;
    align-items: center;
    gap: 8px;

    .condition-icon {
      font-size: 18px;
      color: #979ba5;
    }
  }

  .condition-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .condition-editor {
    min-height: 32px;
  }

  .condition-actions {
    display: flex;
    margin-top: 12px;
    justify-content: flex-start;

    .resubmit-btn {
      min-width: 88px;
      height: 32px;
    }
  }

  .condition-tag {
    display: inline-flex;
    height: 32px;
    padding: 0 12px;
    font-size: 12px;
    line-height: 30px;
    color: #63656e;
    background: #f0f1f5;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    align-items: center;
    box-sizing: border-box;

    .tag-value {
      font-weight: 700;
      color: #313238;
    }
  }

  .process-section {
    margin-bottom: 20px;
  }

  .process-row {
    display: flex;
    height: 28px;
    font-size: 12px;
    line-height: 28px;
    color: #979ba5;
    align-items: center;
    gap: 4px;

    .process-arrow {
      font-size: 14px;
    }
  }

  .status-panel {
    display: flex;
    margin-top: 12px;
    margin-bottom: 8px;
    min-height: 200px;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-sizing: border-box;
  }

  .status-panel.is-empty {
    .empty-icon {
      display: block;
      width: 98px;
      height: 88px;
    }

    .status-title {
      margin-top: 8px;
      font-size: 14px;
      line-height: 22px;
      color: #313238;
    }

    .status-desc {
      font-size: 12px;
      line-height: 18px;
      color: #4d4f56;
      text-align: center;
    }
  }

  .summary-section {
    display: flex;
    margin-bottom: 16px;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }

  .summary-main {
    min-width: 0;
    flex: 1;
  }

  .summary-title {
    margin: 0 0 19px;
    font-size: 20px;
    font-weight: 700;
    line-height: 24px;
    color: #313238;
  }

  .summary-desc {
    margin: 0;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;

    .summary-num {
      font-weight: 700;
      color: #313238;
    }
  }

  .export-dropdown {
    flex-shrink: 0;
  }

  .export-btn {
    height: 32px;
    padding: 0 12px;
    color: #63656e;
    background: #fff;
    border-color: #dcdee5;

    &:hover {
      color: #3a84ff;
      border-color: #3a84ff;
    }

    .export-icon {
      margin-right: 4px;
      font-size: 14px;
    }
  }

  .table-section {
    margin-bottom: 20px;
    overflow: hidden;
  }

  .table-scroll {
    width: 100%;
    overflow: auto;
    scrollbar-width: thin;
    scrollbar-color: #dcdee5 transparent;

    &::-webkit-scrollbar {
      height: 4px;
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;
    }
  }

  .result-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;

    th,
    td {
      width: 140px;
      min-width: 140px;
      max-width: 280px;
      height: 42px;
      padding: 0 12px;
      overflow: hidden;
      font-size: 12px;
      line-height: 42px;
      color: #63656e;
      text-align: left;
      border: none;
      box-sizing: border-box;
    }

    .cell-tip {
      width: 100%;
      max-width: 100%;
      line-height: 20px;
      vertical-align: middle;
    }

    .result-code-cell {
      overflow: visible;
    }

    .empty-cell {
      color: #979ba5;
      text-align: center;
    }

    th {
      font-weight: 400;
      color: #313238;
      background: #fafbfd;
      border-bottom: 1px solid #dcdee5;
    }

    td {
      background: #fff;
    }

    tbody tr:nth-child(even) td {
      background: #fafbfd;
    }
  }

  .table-pagination {
    display: flex;
    padding: 8px 12px;
    background: #fff;
    border-top: 1px solid #dcdee5;
    align-items: center;
    justify-content: flex-end;
  }

  .action-section {
    display: flex;
    margin-bottom: 0;
    gap: 12px;
  }

  .analyze-btn {
    color: #7b29ff;
    border-color: #7b29ff;

    &:not(.is-disabled, [disabled]):hover {
      color: #9b5cff;
      border-color: #9b5cff;
    }

    &.is-disabled,
    &[disabled] {
      color: #c4c6cc;
      cursor: not-allowed;
      border-color: #dcdee5;
      opacity: 1;

      .ai-agent-ai {
        opacity: 40%;
      }
    }

    .ai-agent-ai {
      margin-right: 4px;
    }
  }

  .statistics-btn {
    color: #63656e;
    border-color: #dcdee5;

    .action-icon {
      margin-right: 4px;
      font-size: 16px;
    }

    &:not(.is-disabled, [disabled]):hover {
      color: #3a84ff;
      border-color: #3a84ff;
    }

    &.is-disabled,
    &[disabled] {
      color: #c4c6cc;
      cursor: not-allowed;
      border-color: #dcdee5;
      opacity: 1;
    }
  }

  .report-status-section {
    margin-top: 16px;

    &.is-done {
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 2px;
    }
  }

  .report-status-row {
    display: flex;
    min-height: 32px;
    align-items: center;
    gap: 8px;

    & + .report-status-row {
      margin-top: 4px;
    }

    .status-icon {
      font-size: 16px;
      flex-shrink: 0;

      &.is-loading {
        color: #3a84ff;
        animation: log-report-spin 1s linear infinite;
      }

      &.is-success {
        color: #2dcb56;
      }
    }

    .status-text {
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
    }

    .status-time {
      margin-left: 8px;
      font-size: 12px;
      color: #979ba5;
    }

    .view-report-btn {
      display: inline-flex;
      margin-left: auto;
      padding: 0;
      font-size: 12px;
      line-height: 20px;
      color: #3a84ff;
      cursor: pointer;
      background: none;
      border: none;
      align-items: center;
      gap: 4px;

      .view-icon {
        font-size: 14px;
      }

      &:hover {
        color: #699df4;
      }
    }
  }

  @keyframes log-report-spin {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  .feedback-row {
    display: flex;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #dcdee5;
    align-items: center;
    gap: 8px;
  }

  .feedback-btn {
    display: inline-flex;
    width: 28px;
    height: 28px;
    font-size: 16px;
    color: #c4c6cc;
    cursor: pointer;
    background: transparent;
    border: none;
    border-radius: 2px;
    align-items: center;
    justify-content: center;

    .feedback-svg {
      display: block;
    }

    &:hover,
    &.is-active {
      color: #3a84ff;
      background: #f0f5ff;
    }
  }
</style>
<style lang="postcss">
  /* 结果卡内可编辑条件：与条件筛选卡视觉对齐 */
  .retrieval-result-card .condition-editor {
    .nl-condition-tags-first-row,
    .nl-condition-tags-content {
      align-items: center;
    }

    .condition-tag-item {
      height: 32px;
      padding: 0 8px 0 12px;
      background: #f0f1f5;
      border: 1px solid #dcdee5;
      box-sizing: border-box;

      &:hover {
        .tag-value-wrapper {
          background: transparent;
        }
      }
    }

    .nl-tag-input-item.is-editing {
      height: auto;
      min-height: 32px;
    }

    .nl-add-condition-trigger {
      height: 32px;
      padding: 0 12px;
      box-sizing: border-box;

      &.is-accent {
        background: #f0f5ff;
      }
    }

    .condition-clear-btn {
      height: 32px;
    }

    .nl-tag-user-selector-item.is-editing.condition-tag-item:not(.has-users),
    .nl-tag-user-selector-item.is-editing.condition-tag-item.has-users {
      height: 32px !important;
      max-height: 32px !important;
      min-height: 32px !important;
    }
  }
</style>
