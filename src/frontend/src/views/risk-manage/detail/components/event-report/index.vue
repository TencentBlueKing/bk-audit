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
  <div class="event-report">
    <render-info-block
      v-if="data.permission?.edit_risk_v2"
      class="flex mt16">
      <render-info-item label="状态">
        {{ (data.report?.status === 'auto' ? t('自动生成') : t('人工编辑') ) || '--' }}
      </render-info-item>
      <render-info-item label="更新人">
        {{ data.report?.updated_by || '--' }}
      </render-info-item>
    </render-info-block>
    <render-info-block
      v-if="data.permission?.edit_risk_v2"
      class="flex mt16">
      <render-info-item label="状态说明">
        {{ data.report?.status === 'auto' ? t('此报告由审计策略自动生成，并会在风险单出现新关联事件时自动更新') :
          t('此报告由审计策略自动生成并经过人工编辑或完全由人工创建，后续有新事件触发，系统不会自动覆盖您编辑的内容，需要您手动更新报告') || '--' }}
      </render-info-item>
      <render-info-item label="更新时间">
        {{ data.report?.updated_at || '--' }}
      </render-info-item>
    </render-info-block>
    <quill-editor
      :key="reportRenderKey"
      ref="editorRef"
      v-model:content="content"
      content-type="html"
      disabled
      :options="options"
      theme="snow"
      @ready="handleEditorReady" />
    <bk-button
      v-if="data.permission?.edit_risk_v2"
      class="event-report-edit-button"
      outline
      theme="primary"
      @click="handleEditReport">
      {{ t('编辑') }}
    </bk-button>
    <edit-event-report
      :key="editReportKey"
      v-model:isShowEditEventReport="isShowEditEventReport"
      :report-content="data.report?.content || ''"
      :report-enabled="data.report_enabled"
      :status="data.report?.status"
      @update="handleUpdate" />
  </div>
</template>
<script setup lang="ts">
  import Quill from 'quill';
  import { computed, nextTick, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';

  import { QuillEditor } from '@vueup/vue-quill';

  import RenderInfoItem from '../render-info-item.vue';

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import AIAgentBlot from './ai-model';
  import EditEventReport from './edit-event-report.vue';
  import { sanitizeEditorHtml } from './editor-utils';

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
  const { t } = useI18n();

  const isShowEditEventReport = ref(false);
  const editorRef = ref<InstanceType<typeof QuillEditor>>();

  const quill = ref<QuillInstance | null>(null);
  const getQuillInstance = () => (editorRef.value as any)?.getQuill?.();
  // 事件调查报告内容
  const content = ref('');
  const rawContent = computed(() => props.data.report?.content);
  const reportRenderKey = computed(() => props.data.report?.updated_at || props.data.report?.content || 'empty');
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
      if (quill.value) {
        quill.value.setText('', 'api');
        quill.value.clipboard.dangerouslyPasteHTML(0, normalized.html);
      }
      if (normalized.aiAgent.length) {
        insertAiAgentBlock();
      }
    });
  };

  const handleEditorReady = () => {
    const quill = getQuillInstance();
    if (quill) {
      const Delta = Quill.import('delta') as any;
      quill.clipboard.addMatcher('span[data-ai-embed="true"]', (node: Node) => {
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
    isEditorReady.value = true;
    nextTick(() => {
      applyEditorContent(rawContent.value);
    });
  };

  watch(rawContent, (newContent) => {
    applyEditorContent(newContent);
  }, { immediate: true });

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
.event-report {
  position: relative;
  padding: 10px;
  margin-bottom: 10px;

  .event-report-edit-button {
    position: absolute;
    top: 0;
    right: 0;
  }

  .render-info-item {
    min-width: 50%;
    align-items: flex-start;
  }

  :deep(.ql-disabled) {
    background-color: #fff !important;
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

}
</style>
