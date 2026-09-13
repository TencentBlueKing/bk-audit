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
  <audit-sideslider
    :before-close="handleBeforeClose"
    :is-show="isShow"
    :quick-close="false"
    :show-footer="isEditing"
    show-footer-slot
    show-header-slot
    title=""
    :width="drawerWidth"
    @update:is-show="handleUpdateShow">
    <template #header>
      <div class="ai-report-header">
        <div class="ai-report-title-wrapper">
          <span class="ai-report-title-text">{{ isEditing ? t('编辑报告') : t('智能分析报告') }}</span>
          <template v-if="!isEditing && analysisTimeText">
            <span class="ai-report-title-divider" />
            <span class="ai-report-subtitle">{{ t('分析时间') }}：{{ analysisTimeText }}</span>
          </template>
        </div>
        <div
          v-if="!isEditing"
          class="ai-report-header-actions">
          <bk-button
            outline
            theme="primary"
            @click="handleEdit">
            {{ t('编辑') }}
          </bk-button>
          <bk-dropdown
            v-if="availableExportFormats.length"
            :disabled="exporting"
            placement="bottom-end"
            trigger="click">
            <bk-button
              :disabled="exporting"
              :loading="exporting">
              <audit-icon
                class="mr4"
                type="download" />
              {{ exporting ? t('导出中...') : t('导出') }}
            </bk-button>
            <template #content>
              <bk-dropdown-menu>
                <bk-dropdown-item
                  v-if="availableExportFormats.includes('PDF')"
                  :disabled="exporting"
                  @click="handleExport('PDF')">
                  {{ t('导出为PDF') }}
                </bk-dropdown-item>
                <bk-dropdown-item
                  v-if="availableExportFormats.includes('MARKDOWN')"
                  :disabled="exporting"
                  @click="handleExport('MARKDOWN')">
                  {{ t('导出为Markdown') }}
                </bk-dropdown-item>
              </bk-dropdown-menu>
            </template>
          </bk-dropdown>
          <bk-button
            v-if="isReportListEntry && report?.conversationUid"
            @click="handleLocate">
            {{ t('跳转至会话') }}
          </bk-button>
        </div>
      </div>
    </template>

    <div
      class="ai-report-preview-body log-report-preview"
      :class="{ 'is-editing': isEditing }">
      <template v-if="!isEditing">
        <div class="ai-report-meta">
          <div class="ai-report-meta-row">
            <div
              v-for="item in metaList"
              :key="item.key"
              class="ai-report-meta-item">
              <div class="label">
                {{ item.label }}
              </div>
              <div class="value">
                {{ item.value }}
              </div>
            </div>
          </div>
        </div>

        <div class="ai-report-section">
          <div class="ai-report-section-header">
            <div class="ai-report-section-title">
              <img
                alt=""
                class="ai-report-section-icon"
                :src="aiIcon">
              <span class="title">{{ displayTitle }}</span>
            </div>
          </div>
          <div class="ai-report-section-body">
            <!-- eslint-disable vue/no-v-html -->
            <div
              v-if="htmlText"
              class="markdowm-container"
              v-html="htmlText" />
            <div
              v-else
              class="report-empty">
              {{ t('暂无报告内容') }}
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="edit-form">
          <div class="edit-field">
            <div class="edit-label">
              {{ t('报告名称') }}
            </div>
            <bk-input v-model="editTitle" />
          </div>
          <div class="edit-field edit-field--content">
            <div class="edit-label">
              {{ t('报告内容') }}
            </div>
            <rich-editor
              v-model:content="editContent"
              class="edit-rich-editor"
              :default="editorInitialContent" />
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <div class="ai-report-edit-footer">
        <bk-button
          class="ai-report-save-btn"
          :loading="saving"
          theme="primary"
          @click="handleSave">
          {{ t('保存') }}
        </bk-button>
        <bk-button
          class="ai-report-cancel-btn"
          @click="handleCancelEdit">
          {{ t('取消') }}
        </bk-button>
      </div>
    </template>
  </audit-sideslider>
</template>

<script lang="ts" setup>
  import { computed, onDeactivated, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import AiAssistantManageService from '@service/ai-assistant-manage';

  import type {
    AiAttachment,
    AiAttachmentExportFormat,
  } from '@model/ai-assistant/types';

  import useMessage from '@hooks/use-message';

  import aiIcon from '@images/ai-icon.svg?inline';
  import RichEditor from '@components/rich-editor/index.vue';

  import {
    toPreviewHtml,
    toReportDisplayHtml,
  } from '@views/risk-manage/list/components/ai-analyzes-tip/report-content-utils';

  import type { RetrievalFilterCondition } from '../../types';

  export interface LogReportInfo {
    id: string;
    type: 'analyze' | 'statistics';
    title: string;
    createdAt: string;
    markdown?: string;
    exportFormats?: string[];
    conversationUid?: string;
    analysisMode?: string;
  }

  const props = withDefaults(defineProps<{
    isShow?: boolean;
    report?: LogReportInfo | null;
    totalHit?: number;
    conditions?: RetrievalFilterCondition[];
    systems?: string;
    /** 报告列表打开时额外提供「跳转至会话」；编辑、导出两入口都有 */
    entry?: 'session' | 'report-list';
  }>(), {
    isShow: false,
    report: null,
    totalHit: undefined,
    conditions: () => [],
    systems: '',
    entry: 'session',
  });

  const emit = defineEmits<{
    'update:isShow': [value: boolean];
    updated: [attachment: AiAttachment];
    locate: [conversationUid: string];
  }>();

  const { messageSuccess, messageError } = useMessage();
  const { t } = useI18n();

  const isEditing = ref(false);
  const saving = ref(false);
  const exporting = ref(false);
  const editTitle = ref('');
  const editContent = ref('');
  const editorInitialContent = ref('');
  const savedTitle = ref('');
  const savedContent = ref('');

  const isShow = computed({
    get: () => props.isShow,
    set: val => emit('update:isShow', val),
  });

  const drawerWidth = 800;

  const displayTitle = computed(() => savedTitle.value || props.report?.title || t('智能分析报告'));

  const analysisTimeText = computed(() => props.report?.createdAt || '');

  const isReportListEntry = computed(() => props.entry === 'report-list');

  const availableExportFormats = computed(() => (
    (props.report?.exportFormats || []).map(item => String(item).toUpperCase())
  ));

  const htmlText = computed(() => toPreviewHtml(savedContent.value || props.report?.markdown || ''));

  const conditionText = computed(() => {
    if (!props.conditions.length) return '--';
    return props.conditions.map(item => `${item.field}=${item.value}`).join('，');
  });

  const analysisScopeText = computed(() => (
    String(props.report?.analysisMode || '').toUpperCase() === 'CUSTOM'
      ? '自定义分析'
      : '全量命中数据'
  ));

  const hitCountText = computed(() => {
    if (props.totalHit === undefined || props.totalHit === null) return '--';
    return `${props.totalHit.toLocaleString('en-US')} 条`;
  });

  const metaList = computed(() => [
    { key: 'systems', label: '系统范围', value: props.systems || '--' },
    { key: 'conditions', label: '查询条件', value: conditionText.value },
    { key: 'total', label: '命中总量', value: hitCountText.value },
    { key: 'scope', label: '分析口径', value: analysisScopeText.value },
  ]);

  const resetEditForm = (title: string, markdown: string) => {
    editTitle.value = title;
    editorInitialContent.value = toReportDisplayHtml(markdown);
    editContent.value = editorInitialContent.value;
  };

  const syncFromReport = () => {
    savedTitle.value = props.report?.title || t('智能分析报告');
    savedContent.value = props.report?.markdown || '';
    resetEditForm(savedTitle.value, savedContent.value);
    isEditing.value = false;
  };

  watch(() => [props.isShow, props.report?.id, props.report?.markdown], () => {
    if (props.isShow && !isEditing.value) syncFromReport();
  }, { immediate: true });

  const handleUpdateShow = (val: boolean) => {
    emit('update:isShow', val);
  };

  // keep-alive 场景下失活时，关闭侧滑避免遮罩残留导致页面不可点击
  onDeactivated(() => {
    emit('update:isShow', false);
  });

  const handleEdit = () => {
    resetEditForm(savedTitle.value, savedContent.value);
    isEditing.value = true;
  };

  const handleCancelEdit = () => {
    isEditing.value = false;
    resetEditForm(savedTitle.value, savedContent.value);
  };

  const handleSave = async () => {
    if (!props.report?.id || saving.value) return;
    const nextTitle = editTitle.value.trim() || savedTitle.value;
    const nextContent = editContent.value;
    saving.value = true;
    try {
      const attachment = await AiAssistantManageService.updateAttachment({
        attachment_uid: props.report.id,
        title: nextTitle,
        output_data: {
          markdown: nextContent,
        },
      }, { catchError: true });
      savedTitle.value = attachment.title || nextTitle;
      savedContent.value = attachment.output_data?.markdown || nextContent;
      resetEditForm(savedTitle.value, savedContent.value);
      isEditing.value = false;
      emit('updated', attachment);
      messageSuccess(t('保存成功'));
    } catch (error: any) {
      messageError(error?.message || t('保存失败'));
    } finally {
      saving.value = false;
    }
  };

  const handleBeforeClose = () => {
    if (isEditing.value) {
      handleCancelEdit();
      return false;
    }
    return true;
  };

  const handleLocate = () => {
    if (!props.report?.conversationUid) return;
    emit('locate', props.report.conversationUid);
  };

  const handleExport = async (exportFormat: AiAttachmentExportFormat) => {
    if (!props.report?.id || exporting.value) return;
    exporting.value = true;
    try {
      await AiAssistantManageService.exportAttachment({
        attachment_uid: props.report.id,
        export_format: exportFormat,
      }, { catchError: true });
    } catch (error: any) {
      messageError(error?.message || t('导出失败'));
    } finally {
      exporting.value = false;
    }
  };
</script>

<style lang="postcss" scoped>
  .ai-report-header {
    position: relative;
    display: flex;
    width: 100%;
    height: 52px;
    border-bottom: 1px solid var(--audit-neutral-border-01);
    align-items: center;
    justify-content: space-between;
  }

  .ai-report-title-wrapper {
    display: flex;
    align-items: center;
    gap: var(--audit-space-8);
    min-width: 0;
  }

  .ai-report-title-text {
    font-size: var(--audit-font-size-lg);
    font-weight: var(--audit-font-weight-regular);
    line-height: var(--audit-line-height-lg);
    color: var(--audit-neutral-text-01);
  }

  .ai-report-title-divider {
    width: 1px;
    height: 12px;
    background: var(--audit-neutral-border-01);
    flex-shrink: 0;
  }

  .ai-report-subtitle {
    font-size: var(--audit-font-size-base);
    line-height: var(--audit-line-height-base);
    color: var(--audit-neutral-text-03);
    white-space: nowrap;
  }

  .ai-report-header-actions {
    position: absolute;
    right: var(--audit-space-24);
    display: flex;
    gap: var(--audit-space-8);
    align-items: center;
  }

  .mr4 {
    margin-right: var(--audit-space-4);
  }

  .ai-report-preview-body {
    display: flex;
    height: 100%;
    min-height: 0;
    font-size: var(--audit-font-size-md);
    line-height: 1.6;
    color: var(--audit-neutral-text-02);
    flex-direction: column;
    box-sizing: border-box;
  }

  .ai-report-meta {
    padding: var(--audit-space-16) var(--audit-space-40);
    background: var(--audit-neutral-bg-03);
    border: 1px solid var(--audit-neutral-border-02);
    border-bottom: none;
    border-radius: var(--audit-radius-control) var(--audit-radius-control) 0 0;
    flex-shrink: 0;
  }

  .ai-report-meta-row {
    display: flex;
    gap: var(--audit-space-24);
    align-items: flex-start;
    justify-content: space-between;
  }

  .ai-report-meta-item {
    min-width: 0;
    flex: 1;

    .label {
      margin-bottom: 6px;
      font-size: var(--audit-font-size-sm);
      color: var(--audit-neutral-text-03);
    }

    .value {
      font-size: var(--audit-font-size-md);
      line-height: var(--audit-line-height-md);
      color: var(--audit-neutral-text-01);
      word-break: break-all;
    }
  }

  .ai-report-section {
    display: flex;
    min-height: 0;
    border: 1px solid var(--audit-neutral-border-02);
    border-bottom: none;
    border-radius: 0 0 var(--audit-radius-control) var(--audit-radius-control);
    flex: 1;
    flex-direction: column;
  }

  .ai-report-section-header {
    display: flex;
    height: 48px;
    padding: 0 var(--audit-space-24);
    border-bottom: 1px solid var(--audit-neutral-border-02);
    align-items: center;
    flex-shrink: 0;
  }

  .ai-report-section-title {
    display: flex;
    align-items: center;
    gap: var(--audit-space-8);

    .ai-report-section-icon {
      width: 18px;
      height: 18px;
    }

    .title {
      font-size: var(--audit-font-size-base);
      font-weight: var(--audit-font-weight-bold);
      color: var(--audit-neutral-text-01);
    }
  }

  .ai-report-section-body {
    min-height: 0;
    padding: var(--audit-space-24) var(--audit-space-40) var(--audit-space-32);
    overflow: auto;
    flex: 1;
  }

  .report-empty {
    font-size: var(--audit-font-size-md);
    color: var(--audit-neutral-text-03);
  }

  .markdowm-container {
    font-size: var(--audit-font-size-md);
    line-height: 1.8;
    color: var(--audit-neutral-text-01);
    word-break: break-word;

    :deep(p) {
      margin: 0 0 14px;
      line-height: 1.8;
    }

    :deep(h1),
    :deep(h2),
    :deep(h3),
    :deep(h4),
    :deep(h5),
    :deep(h6),
    :deep(ul),
    :deep(ol) {
      margin: 0 0 14px;
      line-height: 1.6;
    }

    :deep(ul),
    :deep(ol) {
      padding-left: 20px;
    }
  }

  .edit-form {
    display: flex;
    width: 100%;
    min-height: 0;
    padding: var(--audit-space-24) var(--audit-space-40);
    flex: 1;
    flex-direction: column;
    box-sizing: border-box;
  }

  .edit-field {
    width: 100%;
    margin-bottom: var(--audit-space-24);
    flex-shrink: 0;

    .edit-label {
      margin-bottom: 6px;
      flex-shrink: 0;
      font-size: var(--audit-font-size-sm);
      line-height: var(--audit-line-height-sm);
      color: var(--audit-neutral-text-02);
    }
  }

  .edit-field--content {
    display: flex;
    min-height: 0;
    margin-bottom: 0;
    flex: 1;
    flex-direction: column;

    :deep(.edit-rich-editor) {
      display: flex;
      width: 100%;
      min-height: 0;
      padding: 0;
      flex: 1;
      flex-direction: column;
    }

    /* Quill 把 toolbar 作为 container 的兄弟插进 editor-wrap，两者都得显式定尺寸 */
    :deep(.ql-toolbar.ql-snow) {
      height: 40px;
      padding: 0 var(--audit-space-16);
      box-sizing: border-box;
      border-color: var(--audit-neutral-border-01);
      border-radius: var(--audit-radius-control) var(--audit-radius-control) 0 0;
      flex: 0 0 40px;
    }

    :deep(.ql-container.ql-snow) {
      /* height 被组件按 height prop 写成了行内 auto，只能用 important 夺回 */
      min-height: 0;
      height: auto !important;
      padding-bottom: 0;
      flex: 1 1 0;
      border-color: var(--audit-neutral-border-01);
      border-radius: 0 0 var(--audit-radius-control) var(--audit-radius-control);
    }

    :deep(.ql-editor) {
      min-height: 0;
      padding: var(--audit-space-12) var(--audit-space-16);
      overflow-y: auto;
    }
  }

  .ai-report-edit-footer {
    display: flex;
    width: 100%;
    align-items: center;
    justify-content: flex-start;
    gap: var(--audit-space-8);
  }

  .ai-report-save-btn,
  .ai-report-cancel-btn {
    min-width: 88px;
  }
</style>

<style lang="postcss">
  .bk-sideslider .bk-modal-content:has(.log-report-preview:not(.is-editing)),
  .bk-sideslider .bk-sideslider-content:has(.log-report-preview:not(.is-editing)) {
    height: 100%;
    min-height: calc(100vh - 52px);
  }

  /* bk-modal-body 有确定高度但不是弹性容器，不铺这一层下面的 flex:1 全部落空，编辑器会塌成 0 高 */
  .bk-sideslider .bk-modal-body:has(.log-report-preview.is-editing) {
    display: flex;
    flex-direction: column;
    .bk-sideslider-content > div {
      height: 100%;
    }
  }

  .bk-sideslider .bk-modal-body:has(.log-report-preview.is-editing) .bk-sideslider-header {
    flex-shrink: 0;
  }

  .bk-sideslider .bk-modal-content:has(.log-report-preview.is-editing),
  .bk-sideslider .bk-sideslider-content:has(.log-report-preview.is-editing) {
    display: flex;
    height: auto;
    min-height: 0;
    overflow: hidden;
    flex: 1;
    flex-direction: column;
  }

  .bk-sideslider .audit-sideslider-content:has(.log-report-preview.is-editing) {
    min-height: 0;
    flex: 1;
  }

  .bk-sideslider:has(.log-report-preview.is-editing)  {
    .bk-modal-content > div {
      height: 100%;
    }
    .bk-sideslider-content {
      height: 100%;
    }
  }

  .bk-sideslider:has(.log-report-preview.is-editing) .bk-modal-footer {
    flex-shrink: 0;
  }

  /* 稿 3573:25180：48px 固定操作栏，灰底 + 上边框，按钮左对齐留 40px */
  .bk-sideslider:has(.log-report-preview.is-editing) .bk-sideslider-footer {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    height: 48px;
    padding: 0 var(--audit-space-40);
    /* 默认 footer 带 margin-top:24，贴底后会顶出一条空隙 */
    margin: 0;
    flex-shrink: 0;
    background: var(--audit-neutral-bg-02);
    border-top: 1px solid var(--audit-neutral-border-01);
    box-sizing: border-box;
  }
</style>
