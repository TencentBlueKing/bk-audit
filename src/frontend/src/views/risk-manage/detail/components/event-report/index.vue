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
  <bk-loading
    class="event-report-loading"
    :loading="loading"
    mode="spin"
    size="small"
    theme="primary"
    :title="t('正在生成事件调查报告')">
    <div
      v-if="loading"
      class="event-report-loading-box" />

    <div
      v-else
      class="event-report">
      <template v-if="data.permission?.edit_risk_v2">
        <div class="event-report-section-title">
          {{ t('基本信息') }}
        </div>
        <div class="event-report-basic-info info-field-rows">
          <div class="info-field-row">
            <render-info-item
              :label="t('状态')"
              :label-width="labelWidth">
              {{ (data.report?.status === 'auto' ? t('模板生成') : t('人工编辑') ) || '--' }}
            </render-info-item>
            <render-info-item
              :label="t('更新人')"
              :label-width="labelWidth">
              {{ data.report?.updated_by || '--' }}
            </render-info-item>
          </div>
          <div class="info-field-row">
            <render-info-item
              :label="t('状态说明')"
              :label-width="labelWidth">
              {{ data.report?.status === 'auto' ? t('此报告由审计策略自动生成，并会在风险单出现新关联事件时自动更新') :
                t('此报告由审计策略自动生成并经过人工编辑或完全由人工创建，后续有新事件触发，系统不会自动覆盖您编辑的内容，需要您手动更新报告') || '--' }}
            </render-info-item>
            <render-info-item
              :label="t('更新时间')"
              :label-width="labelWidth">
              {{ data.report?.updated_at || '--' }}
            </render-info-item>
          </div>
        </div>
      </template>

      <div
        class="event-report-content-header"
        :class="{ 'is-first-section': !data.permission?.edit_risk_v2 }">
        <span class="event-report-section-title">{{ t('报告内容') }}</span>
        <span
          v-if="data.permission?.edit_risk_v2"
          class="event-report-edit-button"
          @click="handleEditReport">
          <audit-icon type="edit-fill" />
          {{ t('编辑') }}
        </span>
      </div>

      <!-- eslint-disable vue/no-v-html -- 内容经 DOMPurify 消毒 -->
      <div
        v-if="useHtmlRenderer"
        :key="`${reportRenderKey}-html`"
        class="event-report-content"
        v-html="displayHtml" />
      <quill-editor
        v-else
        :key="`${reportRenderKey}-editor`"
        ref="editorRef"
        v-model:content="content"
        content-type="html"
        disabled
        :options="options"
        theme="snow"
        @ready="handleEditorReady" />
      <edit-event-report
        :key="editReportKey"
        v-model:isShowEditEventReport="isShowEditEventReport"
        :report-content="data.report?.content || ''"
        :report-enabled="data.report_enabled"
        :status="data.report?.status"
        @update="handleUpdate" />
    </div>
  </bk-loading>
</template>
<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import Quill from 'quill';
  import { computed, nextTick, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import { QuillEditor } from '@vueup/vue-quill';

  import RenderInfoItem from '../render-info-item.vue';

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import AIAgentBlot from './ai-model';
  import EditEventReport from './edit-event-report.vue';
  import { sanitizeEditorHtml } from './editor-utils';
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import ReportTableBlot, { registerReportTableMatcher } from './report-table-blot';

  interface QuillInstance {
    root: HTMLElement;
    getIndex: (blot: any) => number | null;
    getText: () => string;
    deleteText: (index: number, length: number, source?: string) => void;
    insertText: (index: number, text: string, source?: string) => void;
    insertEmbed: (index: number, type: string, value: any, source?: string) => void;
    setText: (text: string, source?: string) => void;
    clipboard: {
      addMatcher: (selector: string, matcher: (node: Node) => any) => void;
      dangerouslyPasteHTML: (index: number, html: string) => void;
    };
  }
  interface expose {
    showReport: () => void;
  }


  interface Props {
    data: RiskManageModel & StrategyInfo
  }

  const props = defineProps<Props>();
  const emits = defineEmits<{
    'updated-data': [];
  }>();
  const { t, locale } = useI18n();
  const labelWidth = computed(() => (locale.value === 'en-US' ? 160 : 120));

  const loading =  computed(() => props.data.report_generating);
  const isShowEditEventReport = ref(false);
  const editorRef = ref<InstanceType<typeof QuillEditor>>();

  const quill = ref<QuillInstance | null>(null);
  const getQuillInstance = () => (editorRef.value as any)?.getQuill?.();
  // 事件调查报告内容
  const content = ref('');
  const rawContent = computed(() => props.data.report?.content);
  const reportRenderKey = computed(() => props.data.report?.updated_at || props.data.report?.content || 'empty');

  const DISPLAY_HTML_OPTIONS = {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'strong', 'em', 'code', 'hr',
      'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
      'ul', 'ol', 'li', 'span', 'div',
    ],
    ADD_ATTR: ['class', 'colspan', 'rowspan'],
  };

  const hasAiAgentContent = (html: string) => /ql-ai-agent|ai-content|data-ai-embed/i.test(html);

  const useHtmlRenderer = computed(() => {
    const html = rawContent.value || '';
    return html.length > 0 && !hasAiAgentContent(html);
  });

  const displayHtml = computed(() => {
    const html = rawContent.value;
    if (!html) return '';
    return DOMPurify.sanitize(sanitizeEditorHtml(html), DISPLAY_HTML_OPTIONS);
  });
  const editReportKey = computed(() => props.data.report?.updated_at || props.data.report?.content || 'empty');
  const aiAgentData = ref<Array<{ id: string; name: string; prompt: string }>>([]);
  const aiBlockToken = '[[AI_AGENT_BLOCK]]';
  const isEditorReady = ref(false);

  // 配置编辑器选项：不显示工具栏，只用于渲染
  const options = reactive({
    theme: 'snow',
    modules: {
      toolbar: false, // 隐藏工具栏
    },
    readOnly: true, // 只读模式
  });

  const normalizeContentWithAiBlock = (html: string) => {
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html');
    const container = doc.body.firstElementChild as HTMLElement | null;
    if (!container) {
      return { html, aiAgent: [] as typeof aiAgentData.value };
    }

    const targets = Array.from(container.querySelectorAll('.ql-ai-agent, .ai-content')) as HTMLElement[];
    if (!targets.length) {
      return { html: container.innerHTML, aiAgent: [] as typeof aiAgentData.value };
    }

    targets.forEach((targetNode) => {
      const prompt = targetNode.getAttribute('data-prompt') || targetNode.textContent || '';
      const fragment = doc.createDocumentFragment();
      const lines = prompt.split(/\r?\n/);
      lines.forEach((line) => {
        const paragraph = doc.createElement('p');
        if (line.trim() === '') {
          paragraph.innerHTML = '<br>';
        } else {
          paragraph.textContent = line;
        }
        fragment.appendChild(paragraph);
      });
      targetNode.parentNode?.replaceChild(fragment, targetNode);
    });
    return {
      html: container.innerHTML,
      aiAgent: [] as typeof aiAgentData.value,
    };
  };

  const insertAiAgentBlock = (retries = 6) => {
    if (!aiAgentData.value.length) return;
    if (!quill.value) {
      if (retries > 0) {
        setTimeout(() => insertAiAgentBlock(retries - 1), 0);
      }
      return;
    }
    const placeholders = Array.from(quill.value.root.querySelectorAll('[data-ai-placeholder="true"]')) as HTMLElement[];
    if (placeholders.length) {
      for (let i = placeholders.length - 1; i >= 0; i--) {
        const placeholder = placeholders[i];
        const dataIndex = Number(placeholder.getAttribute('data-ai-index') || i);
        const data = aiAgentData.value[dataIndex];
        if (!data) continue;
        const blot = Quill.find(placeholder);
        if (!blot) continue;
        const blotIndex = quill.value.getIndex(blot);
        if (typeof blotIndex !== 'number') continue;
        quill.value.deleteText(blotIndex, aiBlockToken.length, 'api');
        quill.value.insertEmbed(blotIndex, 'aiAgent', {
          id: data.id,
          name: data.name,
          prompt: data.prompt,
          result: '',
        }, 'api');
        quill.value.insertText(blotIndex + 1, '\n', 'api');
      }
      return;
    }
    let searchIndex = quill.value.getText().lastIndexOf(aiBlockToken);
    if (searchIndex === -1) {
      if (retries > 0) {
        setTimeout(() => insertAiAgentBlock(retries - 1), 0);
      }
      return;
    }
    for (let i = aiAgentData.value.length - 1; i >= 0 && searchIndex !== -1; i--) {
      const data = aiAgentData.value[i];
      quill.value.deleteText(searchIndex, aiBlockToken.length, 'api');
      quill.value.insertEmbed(searchIndex, 'aiAgent', {
        id: data.id,
        name: data.name,
        prompt: data.prompt,
        result: '',
      }, 'api');
      quill.value.insertText(searchIndex + 1, '\n', 'api');
      searchIndex = quill.value.getText().lastIndexOf(aiBlockToken, searchIndex - 1);
    }
  };

  const repasteEditorHtml = (html: string) => {
    if (!quill.value) return;
    quill.value.setText('', 'api');
    quill.value.clipboard.dangerouslyPasteHTML(0, html);
  };

  const applyEditorContent = (html?: string) => {
    if (!html) {
      content.value = '';
      aiAgentData.value = [];
      return;
    }
    const sanitized = sanitizeEditorHtml(html);
    const normalized = normalizeContentWithAiBlock(sanitized);
    content.value = normalized.html;
    aiAgentData.value = normalized.aiAgent;
    if (!isEditorReady.value) {
      return;
    }
    nextTick(() => {
      if (!normalized.aiAgent.length) return;
      repasteEditorHtml(normalized.html);
      insertAiAgentBlock();
    });
  };

  const handleEditorReady = () => {
    quill.value = getQuillInstance();
    if (quill.value) {
      registerReportTableMatcher(quill.value);
      const Delta = Quill.import('delta') as any;
      quill.value.clipboard.addMatcher('span[data-ai-embed="true"]', (node: Node) => {
        const element = node as HTMLElement;
        const id = element.getAttribute('data-id') || Date.now().toString();
        const name = element.getAttribute('data-name') || t('完整AI总结');
        const prompt = element.getAttribute('data-prompt') || '';
        return new Delta()
          .insert({
            aiAgent: {
              id,
              name,
              prompt,
              result: '',
            },
          });
      });
    }
    isEditorReady.value = true;
    nextTick(() => {
      applyEditorContent(rawContent.value);
    });
  };

  watch(rawContent, (newContent) => {
    if (!useHtmlRenderer.value) {
      applyEditorContent(newContent);
    }
  }, { immediate: true });

  // 监听 report_generating 状态变化，当从 true 变为 false 时通知父组件刷新
  watch(() => props.data.report_generating, (isGenerating, prevGenerating) => {
    // 当 report_generating 从 true 变为 false 时，通知父组件刷新
    if (prevGenerating && !isGenerating) {
      emits('updated-data');
    }
  });

  const  handleEditReport = () => {
    isShowEditEventReport.value = true;
  };

  const handleUpdate = () => {
    emits('updated-data');
  };

  defineExpose<expose>({
    showReport() {
      handleEditReport();
    },
  });
</script>
<style lang="postcss" scoped>
.event-report-loading-box {
  position: relative;
  height: 300px;
}

.event-report {
  /* 有 Tab 时，页签到「基本信息」24px；底部留 16px */
  padding: var(--bk-theme-space-24) var(--bk-theme-space-16) var(--bk-theme-space-16);
  margin-bottom: var(--bk-theme-space-12);

  .event-report-section-title {
    font-family: 'Microsoft YaHei', '微软雅黑', sans-serif;
    font-size: 12px;
    font-style: normal;
    font-weight: 700;
    line-height: 20px;
    letter-spacing: 0;
    color: var(--bk-theme-text-default);
  }

  .event-report-basic-info {
    padding-bottom: var(--bk-theme-space-24);
    margin-top: var(--bk-theme-space-12);
    margin-bottom: var(--bk-theme-space-24);
    border-bottom: 1px solid var(--bk-theme-border-default);

    .render-info-item {
      align-items: flex-start;
    }
  }

  .event-report-content-header {
    display: flex;
    align-items: center;
    margin-bottom: var(--bk-theme-space-12);

    &.is-first-section {
      margin-top: 0;
    }
  }

  .event-report-edit-button {
    display: inline-flex;
    margin-left: var(--bk-theme-space-12);
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-color-brand-2);
    cursor: pointer;
    align-items: center;
    gap: var(--bk-theme-space-2);

    &:hover {
      color: var(--bk-theme-color-brand-3);
    }
  }

  .event-report-content,
  :deep(.ql-editor) {
    line-height: 1.5;
    color: var(--bk-theme-text-strong);
  }

  /* v-html 渲染区：补齐原 Quill 容器边框 */
  .event-report-content {
    min-height: 120px;padding: var(--bk-theme-space-12) var(--bk-theme-space-16);
    background: var(--bk-theme-surface-default);
    border: 1px solid var(--bk-theme-border-default);
    border-radius: var(--bk-theme-tag-radius);
    box-sizing: border-box;

    :deep(strong) {
      display: inline;
    }

    :deep(p) {
      margin: 0 0 var(--bk-theme-space-12);
      line-height: 1.5;
    }

    :deep(h1),
    :deep(h2),
    :deep(h3),
    :deep(h4),
    :deep(h5),
    :deep(h6),
    :deep(ul),
    :deep(ol) {
      margin: 0 0 var(--bk-theme-space-12);
    }

    :deep(ul),
    :deep(ol) {
      padding-left: var(--bk-theme-space-16);
    }

    :deep(li) {
      margin-bottom: var(--bk-theme-space-4);
    }

    :deep(.report-blockquote) {
      padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
      margin: 0 0 var(--bk-theme-space-12);
      color: var(--bk-theme-text-strong);
      background: var(--bk-theme-surface-subtle);
      border-left: 4px solid var(--bk-theme-border-default);
    }

    :deep(code) {
      padding: var(--bk-theme-space-2) var(--bk-theme-space-4);
      font-family: Consolas, Monaco, monospace;
      font-size: .9em;
      background: var(--bk-theme-surface-muted);
      border-radius: var(--bk-theme-tag-radius);
    }

    :deep(hr) {
      margin: var(--bk-theme-space-16) 0;
      border: 0;
      border-top: 1px solid var(--bk-theme-border-default);
    }

    :deep(.ql-report-table) {
      margin: 0 0 var(--bk-theme-space-16);
    }

    :deep(table) {
      width: 100%;
      margin: 0;
      font-size: 14px;
      border-collapse: collapse;
      table-layout: auto;
    }

    :deep(th),
    :deep(td) {padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
      color: var(--bk-theme-text-strong);
      text-align: left;
      vertical-align: top;
      border: 1px solid var(--bk-theme-border-default);
    }

    :deep(thead th) {
      font-weight: 600;
      color: var(--bk-theme-text-strong);
      background: var(--bk-theme-surface-subtle);
    }
  }

  :deep(.quill-editor .ql-container.ql-snow) {
    background: var(--bk-theme-surface-default);
    border: 1px solid var(--bk-theme-border-default);
    border-radius: var(--bk-theme-tag-radius);
  }

  :deep(.ql-disabled) {
    background-color: var(--bk-theme-surface-default) !important;
  }

  :deep(.ql-editor li p) {
    display: inline !important;
    margin: 0 !important;
  }

  :deep(.ql-editor li p + p::before) {
    content: ' ';
  }

  :deep(.ql-editor strong) {
    display: inline !important;
  }

  :deep(.ql-editor p) {
    margin: 0 0 var(--bk-theme-space-12);
    line-height: 1.5;
  }

  :deep(.ql-editor h1),
  :deep(.ql-editor h2),
  :deep(.ql-editor h3),
  :deep(.ql-editor h4),
  :deep(.ql-editor h5),
  :deep(.ql-editor h6),
  :deep(.ql-editor ul),
  :deep(.ql-editor ol) {
    margin: 0 0 var(--bk-theme-space-12);
  }

  :deep(.ql-editor ul),
  :deep(.ql-editor ol) {
    padding-left: var(--bk-theme-space-16);
  }

  :deep(.ql-editor li) {
    margin-bottom: var(--bk-theme-space-4);
  }

  :deep(.ql-editor .report-blockquote) {
    padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
    margin: 0 0 var(--bk-theme-space-12);
    color: var(--bk-theme-text-strong);
    background: var(--bk-theme-surface-subtle);
    border-left: 4px solid var(--bk-theme-border-default);
  }

  :deep(.ql-editor code) {
    padding: var(--bk-theme-space-2) var(--bk-theme-space-4);
    font-family: Consolas, Monaco, monospace;
    font-size: .9em;
    background: var(--bk-theme-surface-muted);
    border-radius: var(--bk-theme-tag-radius);
  }

  :deep(.ql-editor hr) {
    margin: var(--bk-theme-space-16) 0;
    border: 0;
    border-top: 1px solid var(--bk-theme-border-default);
  }

  :deep(.ql-editor .ql-report-table) {
    margin: 0 0 var(--bk-theme-space-16);
  }

  :deep(.ql-editor table) {
    width: 100%;
    margin: 0 0 var(--bk-theme-space-16);
    font-size: 14px;
    border-collapse: collapse;
    table-layout: auto;
  }

  :deep(.ql-editor th),
  :deep(.ql-editor td) {padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
    color: var(--bk-theme-text-strong);
    text-align: left;
    vertical-align: top;
    border: 1px solid var(--bk-theme-border-default);
  }

  :deep(.ql-editor thead th) {
    font-weight: 600;
    color: var(--bk-theme-text-strong);
    background: var(--bk-theme-surface-subtle);
  }

}

.event-report-loading {
  :deep(.bk-loading-title) {
    margin-left: -var(--bk-theme-space-32);
  }
}
</style>
