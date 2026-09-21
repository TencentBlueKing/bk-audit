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
        :placeholder="t('搜索报告标题')"
        @clear="handleSearchClear"
        @compositionend="handleSearchCompositionEnd"
        @compositionstart="isComposing = true">
        <template #suffix>
          <search class="search-icon" />
        </template>
      </bk-input>
      <div
        class="collapse-all-wrap"
        :class="{ 'is-hidden': isCollapseAllHidden }">
        <bk-button
          class="collapse-all-btn"
          size="small"
          @click="toggleCollapseAll">
          <audit-icon
            class="collapse-all-icon"
            :type="isAllCollapsed ? 'full-screen' : 'zoom-out'" />
          {{ isAllCollapsed ? t('一键展开') : t('一键收起') }}
        </bk-button>
      </div>
    </div>

    <div
      ref="listScrollRef"
      class="panel-content">
      <bk-loading :loading="loading">
        <div
          v-if="!loading && !renderBlocks.length"
          class="panel-empty">
          {{ t('暂无报告') }}
        </div>
        <div
          v-for="block in renderBlocks"
          :key="block.key"
          class="report-group"
          :data-session-uid="block.session ? block.session.uid : undefined">
          <button
            v-if="block.session"
            class="group-header"
            type="button"
            @click="toggleGroup(block.session.uid)">
            <audit-icon
              class="group-arrow"
              :type="collapsedSessions.has(block.session.uid) ? 'angle-fill-rignt' : 'angle-fill-down'" />
            <span class="group-name">{{ block.session.title || t('未命名会话') }}</span>
            <span
              v-if="block.session.loaded"
              class="group-count">
              {{ groupCountText(block.session) }}
            </span>
          </button>
          <div
            v-show="!block.session || !collapsedSessions.has(block.session.uid)"
            class="report-rows">
            <div
              v-for="report in block.reports"
              :key="report.uid"
              class="report-row"
              :class="{
                'is-export-open': exportMenuUid === report.uid,
                'is-exporting': exportingUid === report.uid,
              }"
              @click="handleReportClick(report)">
              <audit-icon
                class="report-file-icon"
                type="report" />
              <span class="report-name">{{ report.title || t('智能分析报告') }}</span>
              <span class="report-time">{{ reportTimeText(report) }}</span>
              <div
                class="report-hover-actions"
                @click.stop>
                <bk-dropdown
                  v-if="getExportFormats(report).length"
                  class="hover-export-dropdown"
                  :disabled="exportingUid === report.uid"
                  placement="bottom-end"
                  :popover-options="exportPopoverOptions"
                  trigger="click"
                  @hide="handleExportMenuHide(report.uid)"
                  @show="handleExportMenuShow(report.uid)">
                  <button
                    v-bk-tooltips="{
                      content: exportingUid === report.uid ? t('导出中...') : t('导出'),
                      disabled: exportMenuUid === report.uid && exportingUid !== report.uid,
                    }"
                    class="hover-action"
                    :class="{ 'is-loading': exportingUid === report.uid }"
                    :disabled="exportingUid === report.uid"
                    type="button">
                    <span
                      v-if="exportingUid === report.uid"
                      class="hover-action-spinner" />
                    <audit-icon
                      v-else
                      type="download" />
                  </button>
                  <template #content>
                    <bk-dropdown-menu>
                      <bk-dropdown-item
                        v-if="getExportFormats(report).includes('PDF')"
                        :disabled="exportingUid === report.uid"
                        @click="handleExport(report, 'PDF')">
                        {{ t('导出为PDF') }}
                      </bk-dropdown-item>
                      <bk-dropdown-item
                        v-if="getExportFormats(report).includes('MARKDOWN')"
                        :disabled="exportingUid === report.uid"
                        @click="handleExport(report, 'MARKDOWN')">
                        {{ t('导出为Markdown') }}
                      </bk-dropdown-item>
                    </bk-dropdown-menu>
                  </template>
                </bk-dropdown>
                <button
                  v-bk-tooltips="t('跳转至会话')"
                  class="hover-action"
                  type="button"
                  @click="handleLocate(report)">
                  <audit-icon type="huihua" />
                </button>
              </div>
            </div>
            <button
              v-if="block.session && block.session.loaded && !block.session.allLoaded"
              class="load-all-btn"
              :disabled="block.session.loadingAll"
              type="button"
              @click="handleLoadAll(block.session)">
              {{ t('点击加载全部') }}
            </button>
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
  import axios, { type CancelTokenSource } from 'axios';
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { Search } from 'bkui-vue/lib/icon';
  import dayjs from 'dayjs';

  import AiAssistantManageService from '@service/ai-assistant-manage';

  import type {
    AiAttachment,
    AiAttachmentExportFormat,
    AiAttachmentListItem,
  } from '@model/ai-assistant/types';

  import useMessage from '@hooks/use-message';

  import reportListCloseIcon from '@images/report-list-close.svg';

  import LogReportDrawer, { type LogReportInfo } from '../audit-log-retrieval/components/log-report-drawer.vue';

  interface ReportSession {
    uid: string;
    title: string;
    reports: AiAttachmentListItem[];
    /** 首屏已拉回来了（不是「已发起请求」，否则计数和加载全部会先冒出来再改） */
    loaded: boolean;
    /** 首屏请求进行中 */
    loading: boolean;
    /** 该会话报告是否已全部在列 */
    allLoaded: boolean;
    loadingAll: boolean;
  }

  interface RenderBlock {
    key: string;
    /** 搜索态平铺，没有会话头 */
    session: ReportSession | null;
    reports: AiAttachmentListItem[];
  }

  const emit = defineEmits<{
    close: [];
    select: [conversationUid: string];
  }>();
  const SESSION_PAGE_SIZE = 10;
  const PANEL_DEFAULT_WIDTH = 400;
  const PANEL_MIN_WIDTH = 400;
  const PANEL_MAX_WIDTH = 600;
  const SEARCH_DEBOUNCE_MS = 300;
  const { CancelToken } = axios;

  const { t } = useI18n();
  const { messageError, messageWarn } = useMessage();

  const loading = ref(false);
  const searchKeyword = ref('');
  const sessions = ref<ReportSession[]>([]);
  const searchResults = ref<AiAttachmentListItem[]>([]);
  const collapsedSessions = ref<Set<string>>(new Set());
  const panelWidth = ref(PANEL_DEFAULT_WIDTH);
  const listScrollRef = ref<HTMLElement | null>(null);
  const reportDrawerShow = ref(false);
  const activeReport = ref<(LogReportInfo & { conversationUid?: string }) | null>(null);
  const exportMenuUid = ref('');
  const exportingUid = ref('');
  const exportPopoverOptions = {
    clickContentAutoHide: true,
  };
  const DEFAULT_EXPORT_FORMATS: AiAttachmentExportFormat[] = ['PDF', 'MARKDOWN'];

  const isComposing = ref(false);
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let searchCancelSource: CancelTokenSource | null = null;
  let lastIssuedKeyword: string | null = null;
  /** 会话列表可能被清空搜索、重复点击并发触发，只认最后一次 */
  let sessionsFetchToken = 0;
  const activeSearchKeyword = ref('');

  const isSearching = computed(() => Boolean(activeSearchKeyword.value));

  const renderBlocks = computed((): RenderBlock[] => {
    if (isSearching.value) {
      return searchResults.value.length
        ? [{ key: 'search-flat', session: null, reports: searchResults.value }]
        : [];
    }
    return sessions.value
      // 会话按「有 AI_ANALYSIS 附件」筛出，但只有失败/生成中报告的会话取不到成功项，不展示空分组
      .filter(session => !(session.allLoaded && !session.reports.length))
      .map(session => ({
        key: session.uid,
        session,
        reports: session.reports,
      }));
  });

  /** 首屏只取一页，没取全时用 n+ 表示还有更多 */
  const groupCountText = (session: ReportSession) => (
    session.allLoaded ? `${session.reports.length}` : `${session.reports.length}+`
  );

  const formatReportTime = (value?: string | null) => {
    if (!value) return '';
    const parsed = dayjs(value);
    return parsed.isValid() ? parsed.format('YYYY-MM-DD  HH:mm') : value;
  };

  /** 列表默认按 content_updated_at 排序，行上时间同步展示内容更新时间 */
  const reportTimeText = (item: AiAttachmentListItem) => (
    formatReportTime(item.content_updated_at || item.created_at)
  );

  const fetchSessionReports = (conversationUid: string, limit?: number) => (
    AiAssistantManageService.fetchAttachments({
      conversation_uid: conversationUid,
      attachment_type: 'AI_ANALYSIS',
      status: 'SUCCESS',
      ...(limit ? { limit } : {}),
    }, { catchError: true })
  );

  /**
   * 会话上的 attachment_counts_by_type 含所有状态，与只取 SUCCESS 的列表对不上，
   * 只能按「是否取满一页」判断还有没有更多。
   */
  const resolveAllLoaded = (loadedCount: number) => loadedCount < SESSION_PAGE_SIZE;

  const patchSession = (uid: string, patch: Partial<ReportSession>) => {
    sessions.value = sessions.value.map(item => (
      item.uid === uid ? { ...item, ...patch } : item
    ));
  };

  /** 首屏只取 10 条，按会话进入视口时触发 */
  const loadSessionReports = async (session: ReportSession) => {
    if (session.loaded || session.loading || session.loadingAll) return;
    patchSession(session.uid, { loading: true });
    try {
      const list = await fetchSessionReports(session.uid, SESSION_PAGE_SIZE);
      patchSession(session.uid, {
        reports: list,
        loaded: true,
        loading: false,
        allLoaded: resolveAllLoaded(list.length),
      });
    } catch {
      // 单个会话拉取失败不影响其他会话，重新进入视口可再试
      patchSession(session.uid, { loading: false });
    }
  };

  const handleLoadAll = async (session: ReportSession) => {
    if (session.loadingAll) return;
    patchSession(session.uid, { loadingAll: true });
    try {
      const reports = await fetchSessionReports(session.uid);
      // 不带 limit 即全量，无需再按计数判断
      patchSession(session.uid, {
        reports,
        allLoaded: true,
      });
    } catch (error: any) {
      messageError(error?.message || t('报告列表加载失败'));
    } finally {
      patchSession(session.uid, { loadingAll: false });
    }
  };

  const fetchSessions = async () => {
    sessionsFetchToken += 1;
    const token = sessionsFetchToken;
    loading.value = true;
    try {
      const list = await AiAssistantManageService.fetchConversationList({
        has_attachments: true,
        attachment_type: 'AI_ANALYSIS',
      }, { catchError: true });
      if (token !== sessionsFetchToken) return;
      sessions.value = list.map(item => ({
        uid: item.uid,
        title: item.title,
        reports: [],
        loaded: false,
        loading: false,
        allLoaded: false,
        loadingAll: false,
      }));
      collapsedSessions.value = new Set();
      /*
       * 会话整体换了新对象，reports 全被重置回空。
       * 视口内的会话 intersection 状态没变化，不重新 observe 就永远等不到回调，
       * 分组会一直空着。
       */
      void nextTick(observeSessions);
    } catch (error: any) {
      if (token !== sessionsFetchToken) return;
      sessions.value = [];
      messageError(error?.message || t('报告列表加载失败'));
    } finally {
      if (token === sessionsFetchToken) {
        loading.value = false;
      }
    }
  };

  const fetchSearchResults = async () => {
    const keyword = searchKeyword.value.trim();
    const previousKeyword = lastIssuedKeyword;
    if (keyword === previousKeyword) return;

    lastIssuedKeyword = keyword;
    searchCancelSource?.cancel('report-list search aborted');
    searchCancelSource = null;

    if (!keyword) {
      activeSearchKeyword.value = '';
      searchResults.value = [];
      await fetchSessions();
      return;
    }

    // 先盖 loading，再切到搜索列表，避免空数组先画出「暂无报告」
    loading.value = true;
    activeSearchKeyword.value = keyword;

    const source = CancelToken.source();
    searchCancelSource = source;
    try {
      const list = await AiAssistantManageService.fetchAttachments({
        attachment_type: 'AI_ANALYSIS',
        status: 'SUCCESS',
        keyword,
      }, {
        catchError: true,
        cancelTokenSource: source,
      });
      if (source !== searchCancelSource) return;
      searchResults.value = list;
    } catch (error: any) {
      if (error?.code === 'CANCEL' || source !== searchCancelSource) return;
      searchResults.value = [];
      messageError(error?.message || t('报告列表加载失败'));
    } finally {
      if (source === searchCancelSource) {
        loading.value = false;
      }
    }
  };

  const scheduleSearch = () => {
    if (searchTimer) clearTimeout(searchTimer);
    const pendingKeyword = searchKeyword.value.trim();
    searchTimer = setTimeout(() => {
      if (isComposing.value) return;
      // 排队期间关键词又变了（典型是被清空），这一次作废，避免打出旧词
      if (searchKeyword.value.trim() !== pendingKeyword) return;
      void fetchSearchResults();
    }, SEARCH_DEBOUNCE_MS);
  };

  const handleSearchCompositionEnd = () => {
    isComposing.value = false;
    scheduleSearch();
  };

  const handleSearchClear = () => {
    isComposing.value = false;
    if (searchTimer) clearTimeout(searchTimer);
    searchKeyword.value = '';
    void fetchSearchResults();
  };

  const isAllCollapsed = computed(() => {
    if (!sessions.value.length) return false;
    return sessions.value.every(session => collapsedSessions.value.has(session.uid));
  });

  /** 分组列表才显示；搜索中 / 暂无报告都 display:none，loading 时也不要闪回来 */
  const isCollapseAllHidden = computed(() => (
    // 拉列表期间 renderBlocks 会短暂为空，此时别动显隐，否则每次搜索都闪一下
    isSearching.value || (!loading.value && !renderBlocks.value.length)
  ));

  const toggleCollapseAll = () => {
    if (isSearching.value) return;
    if (isAllCollapsed.value) {
      collapsedSessions.value = new Set();
      return;
    }
    collapsedSessions.value = new Set(sessions.value.map(session => session.uid));
  };

  const toggleGroup = (uid: string) => {
    const next = new Set(collapsedSessions.value);
    if (next.has(uid)) {
      next.delete(uid);
    } else {
      next.add(uid);
    }
    collapsedSessions.value = next;
  };

  const handleReportClick = async (item: AiAttachmentListItem) => {
    let markdown = '';
    let exportFormats = item.export_formats || [];
    let title = item.title || t('智能分析报告');
    let createdAt = formatReportTime(item.created_at);
    let analysisMode = '';
    try {
      const detail = await AiAssistantManageService.fetchAttachment({
        attachment_uid: item.uid,
      }, { catchError: true });
      markdown = detail.output_data?.markdown || '';
      exportFormats = detail.export_formats || exportFormats;
      title = detail.title || title;
      createdAt = formatReportTime(detail.created_at || detail.content_updated_at || '') || createdAt;
      analysisMode = String(detail.input_data?.analysis_mode || '');
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
      analysisMode,
    };
    reportDrawerShow.value = true;
  };

  const getExportFormats = (item: AiAttachmentListItem): AiAttachmentExportFormat[] => {
    const formats = (item.export_formats || [])
      .map(value => String(value).toUpperCase())
      .filter((value): value is AiAttachmentExportFormat => (
        DEFAULT_EXPORT_FORMATS.includes(value as AiAttachmentExportFormat)
      ));
    return formats.length ? formats : DEFAULT_EXPORT_FORMATS;
  };

  const handleExportMenuShow = (uid: string) => {
    exportMenuUid.value = uid;
  };

  const handleExportMenuHide = (uid: string) => {
    if (exportMenuUid.value === uid) {
      exportMenuUid.value = '';
    }
  };

  const handleExport = async (item: AiAttachmentListItem, exportFormat: AiAttachmentExportFormat) => {
    if (exportingUid.value === item.uid) return;
    exportingUid.value = item.uid;
    try {
      await AiAssistantManageService.exportAttachment({
        attachment_uid: item.uid,
        export_format: exportFormat,
      }, { catchError: true });
    } catch (error: any) {
      messageError(error?.message || t('导出失败'));
    } finally {
      exportingUid.value = '';
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
    const mergeItem = (item: AiAttachmentListItem) => (
      item.uid === attachment.uid
        ? { ...item, title: attachment.title || item.title, status: attachment.status }
        : item
    );
    sessions.value = sessions.value.map(session => ({
      ...session,
      reports: session.reports.map(mergeItem),
    }));
    searchResults.value = searchResults.value.map(mergeItem);
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

  let sessionObserver: IntersectionObserver | null = null;

  const observeSessions = () => {
    const root = listScrollRef.value;
    if (!sessionObserver || !root) return;
    sessionObserver.disconnect();
    if (isSearching.value) return;
    root.querySelectorAll('[data-session-uid]').forEach((el) => {
      sessionObserver?.observe(el);
    });
  };

  watch(searchKeyword, (value) => {
    if (isComposing.value) return;
    // 点清空是明确操作，立刻回到会话列表，不再等防抖
    if (!String(value).trim()) {
      if (searchTimer) clearTimeout(searchTimer);
      void fetchSearchResults();
      return;
    }
    scheduleSearch();
  });

  watch([() => sessions.value.length, isSearching], () => {
    void nextTick(observeSessions);
  });

  onMounted(() => {
    sessionObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const uid = (entry.target as HTMLElement).dataset.sessionUid;
        const session = sessions.value.find(item => item.uid === uid);
        if (session) void loadSessionReports(session);
      });
    }, {
      root: listScrollRef.value,
      rootMargin: '120px',
    });
    void fetchSessions();
  });

  onBeforeUnmount(() => {
    if (searchTimer) clearTimeout(searchTimer);
    searchCancelSource?.cancel('report-list search aborted');
    sessionObserver?.disconnect();
    sessionObserver = null;
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

        .bk-input--suffix,
        .bk-input--suffix-icon,
        .bk-input--clear-icon,
        .clear-icon {
          background: transparent !important;
          background-color: transparent !important;
        }
      }

      .bk-input--text {
        height: 32px;
        font-size: var(--audit-font-size-sm);
        line-height: var(--audit-line-height-sm);
        background: transparent;
      }

      .bk-input--suffix,
      .bk-input--suffix-icon,
      .bk-input--clear-icon,
      .clear-icon {
        background: transparent !important;
        background-color: transparent !important;
      }
    }

    .search-icon {
      margin-right: var(--audit-space-8);
      font-size: 16px;
      color: var(--audit-neutral-text-03);
    }

    .collapse-all-wrap {
      &.is-hidden {
        display: none;
      }
    }

    :deep(.collapse-all-btn) {
      min-width: 100px;
      height: 26px;
      padding: 3px 12px;
      color: var(--audit-neutral-text-02);
      border-color: var(--audit-neutral-text-04);
      border-radius: var(--audit-radius-control);
    }

    .collapse-all-icon {
      margin-right: var(--audit-space-4);
      font-size: 16px;

      /* iconcool 里 full-screen 重名两次，字体后一条会盖成四角全屏；这里用与 zoom-out 成对的那颗 */
      &.audit-icon-full-screen::before {
        content: '\e1c0';
      }
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

  .load-all-btn {
    padding: 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-brand-02);
    text-align: center;
    cursor: pointer;
    background: none;
    border: none;
    align-self: center;

    &:hover {
      color: var(--audit-brand-03);
    }

    &:disabled {
      color: var(--audit-neutral-text-04);
      cursor: not-allowed;
    }
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

    &:hover,
    &.is-export-open,
    &.is-exporting {
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
      font-size: 16px;
      color: var(--audit-neutral-text-03);
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

    .hover-export-dropdown {
      display: inline-flex;
      line-height: 1;
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

      &:disabled {
        cursor: not-allowed;
      }
    }

    .hover-action-spinner {
      width: 14px;
      height: 14px;
      border: 2px solid var(--audit-neutral-border-01);
      border-top-color: var(--audit-brand-02);
      border-radius: 50%;
      animation: report-export-spin 0.8s linear infinite;
    }
  }

  @keyframes report-export-spin {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }
</style>
