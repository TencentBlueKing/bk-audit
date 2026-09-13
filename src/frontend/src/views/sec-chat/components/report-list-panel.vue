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
  <div
    class="report-list-panel"
    :style="{ width: `${panelWidth}px` }">
    <div
      class="panel-resize-trigger"
      @mousedown="handlePanelDragStart">
      <div
        aria-hidden="true"
        class="panel-drag-handle">
        <span
          v-for="dot in 5"
          :key="dot"
          class="drag-dot" />
      </div>
    </div>

    <div class="panel-header">
      <span class="title">{{ t('报告列表') }}</span>
      <button
        class="close-btn"
        type="button"
        @click="$emit('close')">
        <img
          alt=""
          class="close-icon"
          draggable="false"
          :src="reportListCloseIcon">
      </button>
    </div>

    <div class="panel-toolbar">
      <bk-input
        v-model="searchKeyword"
        class="panel-search-input"
        clearable
        :placeholder="t('搜索报告标题')">
        <template #suffix>
          <search class="search-icon" />
        </template>
      </bk-input>
      <bk-button
        class="collapse-all-btn"
        size="small"
        @click="collapseAll">
        <plus class="collapse-all-icon" />
        {{ t('一键收起') }}
      </bk-button>
    </div>

    <div
      ref="listScrollRef"
      class="panel-content"
      @scroll="handleListScroll">
      <bk-loading :loading="loading">
        <div
          v-if="!loading && !groupedReports.length"
          class="panel-empty">
          {{ t('暂无报告') }}
        </div>
        <div
          v-for="group in groupedReports"
          :key="group.id"
          class="report-group">
          <button
            class="group-header"
            type="button"
            @click="toggleGroup(group.id)">
            <audit-icon
              class="group-arrow"
              :type="collapsedGroups.has(group.id) ? 'angle-fill-rignt' : 'angle-fill-down'" />
            <span class="group-name">{{ group.name }}</span>
            <span class="group-count">{{ group.reports.length }}</span>
          </button>
          <div
            v-show="!collapsedGroups.has(group.id)"
            class="report-rows">
            <div
              v-for="report in group.reports"
              :key="report.uid"
              class="report-row"
              @click="handleReportClick(report)">
              <img
                alt=""
                class="report-file-icon"
                :src="reportListFileIcon">
              <span class="report-name">{{ report.title || t('智能分析报告') }}</span>
              <span class="report-time">{{ formatReportTime(report.created_at) }}</span>
              <div
                class="report-hover-actions"
                @click.stop>
                <button
                  v-bk-tooltips="t('导出')"
                  class="hover-action"
                  type="button"
                  @click="handleExport(report)">
                  <audit-icon type="download" />
                </button>
                <button
                  v-bk-tooltips="t('跳转至会话')"
                  class="hover-action"
                  type="button"
                  @click="handleLocate(report)">
                  <audit-icon type="jump-link" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </bk-loading>
    </div>

    <log-report-drawer
      v-if="reportDrawerShow"
      v-model:is-show="reportDrawerShow"
      entry="report-list"
      :report="activeReport"
      @locate="handleLocateFromDrawer"
      @updated="handleReportUpdated" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { Plus, Search } from 'bkui-vue/lib/icon';
  import dayjs from 'dayjs';

  import AiAssistantManageService from '@service/ai-assistant-manage';

  import type { AiAttachment, AiAttachmentListItem } from '@model/ai-assistant/types';

  import useMessage from '@hooks/use-message';

  import reportListCloseIcon from '@images/report-list-close.svg';
  import reportListFileIcon from '@images/report-list-file.svg';

  import LogReportDrawer, { type LogReportInfo } from '../audit-log-retrieval/components/log-report-drawer.vue';

  type ReportCategoryId = 'audit-log' | 'risk' | 'other';

  interface ReportGroup {
    id: ReportCategoryId;
    name: string;
    reports: AiAttachmentListItem[];
  }

  const PAGE_SIZE = 20;
  const PANEL_DEFAULT_WIDTH = 400;
  const PANEL_MIN_WIDTH = 400;
  const PANEL_MAX_WIDTH = 600;
  const SEARCH_DEBOUNCE_MS = 300;

  const emit = defineEmits<{
    close: [];
    select: [conversationUid: string];
  }>();

  const { t } = useI18n();
  const { messageError, messageWarn } = useMessage();

  const loading = ref(false);
  const searchKeyword = ref('');
  const allReports = ref<AiAttachmentListItem[]>([]);
  const visibleCount = ref(PAGE_SIZE);
  const collapsedGroups = ref<Set<ReportCategoryId>>(new Set());
  const panelWidth = ref(PANEL_DEFAULT_WIDTH);
  const listScrollRef = ref<HTMLElement | null>(null);
  const reportDrawerShow = ref(false);
  const activeReport = ref<(LogReportInfo & { conversationUid?: string }) | null>(null);

  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  const categoryMeta: { id: ReportCategoryId; name: string }[] = [
    { id: 'audit-log', name: t('审计日志检索') },
    { id: 'risk', name: t('风险分析') },
    { id: 'other', name: t('其他') },
  ];

  const resolveCategory = (item: AiAttachmentListItem): ReportCategoryId => {
    const messageType = String(item.source_message?.message_type || '').toUpperCase();
    if (
      messageType === 'LOG_SEARCH'
      || messageType === 'NATURAL_LANGUAGE_SEARCH'
      || messageType === 'USER_INTENT'
    ) {
      return 'audit-log';
    }
    if (messageType.includes('RISK') || messageType.includes('ALARM')) {
      return 'risk';
    }
    return 'other';
  };

  const displayedReports = computed(() => allReports.value.slice(0, visibleCount.value));

  const groupedReports = computed((): ReportGroup[] => {
    const buckets: Record<ReportCategoryId, AiAttachmentListItem[]> = {
      'audit-log': [],
      risk: [],
      other: [],
    };
    displayedReports.value.forEach((item) => {
      buckets[resolveCategory(item)].push(item);
    });
    return categoryMeta
      .map(meta => ({
        id: meta.id,
        name: meta.name,
        reports: buckets[meta.id],
      }))
      .filter(group => group.reports.length > 0);
  });

  const formatReportTime = (value?: string) => {
    if (!value) return '';
    const parsed = dayjs(value);
    return parsed.isValid() ? parsed.format('YYYY-MM-DD  HH:mm') : value;
  };

  const fetchReports = async () => {
    loading.value = true;
    try {
      const list = await AiAssistantManageService.fetchAttachments({
        keyword: searchKeyword.value.trim() || undefined,
      }, { catchError: true });
      allReports.value = [...list].sort((a, b) => {
        const aTime = dayjs(a.created_at).valueOf() || 0;
        const bTime = dayjs(b.created_at).valueOf() || 0;
        return bTime - aTime;
      });
      visibleCount.value = PAGE_SIZE;
    } catch (error: any) {
      allReports.value = [];
      messageError(error?.message || t('报告列表加载失败'));
    } finally {
      loading.value = false;
    }
  };

  const collapseAll = () => {
    collapsedGroups.value = new Set(groupedReports.value.map(group => group.id));
  };

  const toggleGroup = (id: ReportCategoryId) => {
    const next = new Set(collapsedGroups.value);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    collapsedGroups.value = next;
  };

  const handleListScroll = () => {
    const el = listScrollRef.value;
    if (!el || loading.value) return;
    if (visibleCount.value >= allReports.value.length) return;
    const remain = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (remain < 48) {
      visibleCount.value = Math.min(allReports.value.length, visibleCount.value + PAGE_SIZE);
    }
  };

  const handleReportClick = async (item: AiAttachmentListItem) => {
    let markdown = '';
    let exportFormats = item.export_formats || [];
    let title = item.title || t('智能分析报告');
    let createdAt = formatReportTime(item.created_at);
    try {
      const detail = await AiAssistantManageService.fetchAttachment({
        attachment_uid: item.uid,
      }, { catchError: true });
      markdown = detail.output_data?.markdown || '';
      exportFormats = detail.export_formats || exportFormats;
      title = detail.title || title;
      createdAt = formatReportTime(detail.created_at || detail.content_updated_at || '') || createdAt;
    } catch {
      // 列表摘要仍可打开空内容抽屉
    }
    activeReport.value = {
      id: item.uid,
      type: 'analyze',
      title,
      createdAt,
      markdown,
      exportFormats,
      conversationUid: item.conversation?.uid,
    };
    reportDrawerShow.value = true;
  };

  const handleExport = async (item: AiAttachmentListItem) => {
    const format = (item.export_formats || []).map(value => String(value).toUpperCase())
      .includes('MARKDOWN')
      ? 'MARKDOWN'
      : (item.export_formats?.[0] || 'MARKDOWN');
    try {
      await AiAssistantManageService.exportAttachment({
        attachment_uid: item.uid,
        export_format: format,
      }, { catchError: true });
    } catch (error: any) {
      messageError(error?.message || t('导出失败'));
    }
  };

  const handleLocate = (item: AiAttachmentListItem) => {
    const conversationUid = item.conversation?.uid;
    if (!conversationUid) {
      messageWarn(t('未找到关联会话'));
      return;
    }
    emit('select', conversationUid);
  };

  const handleLocateFromDrawer = (conversationUid: string) => {
    emit('select', conversationUid);
  };

  const handleReportUpdated = (attachment: AiAttachment) => {
    allReports.value = allReports.value.map((item) => {
      if (item.uid !== attachment.uid) return item;
      return {
        ...item,
        title: attachment.title || item.title,
        status: attachment.status,
      };
    });
    if (activeReport.value?.id === attachment.uid) {
      activeReport.value = {
        ...activeReport.value,
        title: attachment.title || activeReport.value.title,
        markdown: attachment.output_data?.markdown || activeReport.value.markdown,
        exportFormats: attachment.export_formats || activeReport.value.exportFormats,
      };
    }
  };

  const handlePanelDragStart = (e: MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = panelWidth.value;
    const onDragMove = (moveEvent: MouseEvent) => {
      panelWidth.value = Math.min(
        PANEL_MAX_WIDTH,
        Math.max(PANEL_MIN_WIDTH, startWidth + (moveEvent.clientX - startX)),
      );
    };
    const onDragEnd = () => {
      document.removeEventListener('mousemove', onDragMove);
      document.removeEventListener('mouseup', onDragEnd);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', onDragEnd);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  watch(searchKeyword, () => {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      void fetchReports();
    }, SEARCH_DEBOUNCE_MS);
  });

  onMounted(() => {
    void fetchReports();
  });

  onBeforeUnmount(() => {
    if (searchTimer) clearTimeout(searchTimer);
  });
</script>

<style lang="postcss" scoped>
  .report-list-panel {
    position: absolute;
    top: 0;
    left: 100%;
    z-index: 20;
    display: flex;
    height: 100%;
    background: var(--audit-neutral-bg-04);
    border-right: 1px solid var(--audit-neutral-border-01);
    border-left: 1px solid var(--audit-neutral-border-01);
    box-shadow: none;
    box-sizing: border-box;
    flex-direction: column;
  }

  .panel-resize-trigger {
    position: absolute;
    top: 0;
    right: -2px;
    z-index: 2;
    width: 5px;
    height: 100%;
    cursor: col-resize;
    user-select: none;
  }

  .panel-drag-handle {
    position: absolute;
    top: 50%;
    left: 50%;
    display: flex;
    width: 10px;
    height: 18px;
    padding: 0 4px;
    box-shadow: none;
    transform: translate(-50%, -50%);
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    box-sizing: border-box;

    .drag-dot {
      display: block;
      width: 2px;
      height: 2px;
      background: var(--audit-neutral-text-02);
      flex-shrink: 0;
    }
  }

  .panel-header {
    display: flex;
    height: 52px;
    padding: 0 var(--audit-space-16) 0 var(--audit-space-24);
    background: var(--audit-neutral-bg-04);
    border-bottom: 1px solid var(--audit-neutral-border-02);
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;

    .title {
      font-size: var(--audit-font-size-base);
      font-weight: var(--audit-font-weight-regular);
      line-height: var(--audit-line-height-base);
      color: var(--audit-neutral-text-01);
    }

    .close-btn {
      display: flex;
      width: 20px;
      height: 20px;
      padding: 0;
      cursor: pointer;
      background: transparent;
      border: none;
      outline: none;
      box-shadow: none;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .close-icon {
      display: block;
      width: 20px;
      height: 20px;
      pointer-events: none;
    }
  }

  .panel-toolbar {
    display: flex;
    padding: 0 var(--audit-space-24);
    margin-top: var(--audit-space-16);
    flex-direction: column;
    align-items: flex-start;
    gap: var(--audit-space-16);
    flex-shrink: 0;

    :deep(.panel-search-input) {
      width: 100%;
      height: 32px;
      padding: 0 var(--audit-space-8);
      background: var(--audit-neutral-bg-01);
      border: 0;
      border-radius: var(--audit-radius-container);
      box-shadow: none;

      &:hover,
      &:focus-within,
      &.is-focused,
      &.is-focused:hover,
      &.is-focused:not(.is-readonly) {
        background: var(--audit-neutral-bg-01);
        border: 0;
        outline: none;
        box-shadow: none;
      }

      .bk-input--text {
        height: 32px;
        font-size: var(--audit-font-size-sm);
        line-height: var(--audit-line-height-sm);
        background: transparent;
      }
    }

    .search-icon {
      margin-right: var(--audit-space-8);
      font-size: 16px;
      color: var(--audit-neutral-text-03);
    }

    :deep(.collapse-all-btn) {
      min-width: 92px;
      height: 26px;
      padding: 3px 12px;
      color: var(--audit-neutral-text-02);
      border-color: var(--audit-neutral-text-04);
      border-radius: var(--audit-radius-control);
    }

    .collapse-all-icon {
      margin-right: var(--audit-space-4);
      font-size: 16px;
    }
  }

  .panel-content {
    min-height: 0;
    padding: var(--audit-space-16) var(--audit-space-24) var(--audit-space-24);
    overflow: auto;
    flex: 1;
  }

  .panel-empty {
    padding-top: var(--audit-space-24);
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-03);
    text-align: center;
  }

  .report-group {
    display: flex;
    margin-bottom: var(--audit-space-24);
    flex-direction: column;
    gap: var(--audit-space-8);

    &:last-child {
      margin-bottom: 0;
    }
  }

  .group-header {
    display: flex;
    padding: 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-01);
    cursor: pointer;
    background: none;
    border: none;
    align-items: center;
    gap: var(--audit-space-8);

    .group-arrow {
      font-size: 12px;
      color: var(--audit-neutral-text-03);
    }

    .group-name {
      font-weight: var(--audit-font-weight-bold);
    }

    .group-count {
      display: inline-flex;
      height: 16px;
      padding: 0 6px;
      font-size: var(--audit-font-size-mini);
      font-weight: var(--audit-font-weight-regular);
      line-height: var(--audit-line-height-mini);
      color: var(--audit-neutral-text-02);
      background: var(--audit-neutral-bg-01);
      border-radius: 8px;
      align-items: center;
    }
  }

  .report-rows {
    display: flex;
    flex-direction: column;
    gap: var(--audit-space-8);
  }

  .report-row {
    display: flex;
    height: 32px;
    padding: 5px var(--audit-space-16) 5px var(--audit-space-12);
    cursor: pointer;
    background: var(--audit-neutral-bg-03);
    border-radius: var(--audit-radius-container);
    align-items: center;
    gap: var(--audit-space-8);

    &:hover {
      background: var(--audit-neutral-border-02);

      .report-time {
        display: none;
      }

      .report-hover-actions {
        display: inline-flex;
      }
    }

    .report-file-icon {
      width: 16px;
      height: 16px;
      flex-shrink: 0;
    }

    .report-name {
      min-width: 0;
      overflow: hidden;
      font-size: var(--audit-font-size-sm);
      line-height: var(--audit-line-height-sm);
      color: var(--audit-neutral-text-01);
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
    }

    .report-time {
      font-size: var(--audit-font-size-sm);
      line-height: var(--audit-line-height-sm);
      color: var(--audit-neutral-text-03);
      white-space: nowrap;
      flex-shrink: 0;
    }

    .report-hover-actions {
      display: none;
      align-items: center;
      gap: var(--audit-space-16);
      flex-shrink: 0;
    }

    .hover-action {
      display: inline-flex;
      padding: 0;
      font-size: 16px;
      color: var(--audit-neutral-text-03);
      cursor: pointer;
      background: none;
      border: none;
      align-items: center;
      justify-content: center;

      &:hover {
        color: var(--audit-brand-02);
      }
    }
  }
</style>
