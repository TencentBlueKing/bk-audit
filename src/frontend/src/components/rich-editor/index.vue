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
    :active="!disabled"
    class="editor-wrap"
    :class="{ 'editor-wrap--table': enableTable }">
    <quill-editor
      ref="editorRef"
      v-model:content="content"
      content-type="html"
      disabled
      :options="options"
      :placeholder="t('请输入')"
      :style="{background: backgroundColor}"
      theme="snow"
      @ready="onEditorReady"
      @update:content="onContentChange" />
    <div
      v-if="maxLen"
      class="editor-tip-len">
      <span
        :class="{'can-edit': TiLength < maxLen}">
        {{ TiLength }}
      </span> / {{ maxLen }}
    </div>
    <insert-table-dialog
      v-if="enableTable"
      ref="insertTableDialogRef"
      @confirm="handleInsertTableConfirm" />
  </div>
</template>

<script setup lang='ts'>
  import {
    nextTick,
    onMounted,
    reactive,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { sanitizeEditorHtml } from '@views/risk-manage/detail/components/event-report/editor-utils';
  import InsertTableDialog from '@views/risk-manage/detail/components/event-report/insert-table-dialog.vue';
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import ReportTableBlot, {
    hasTableContent,
    insertReportTable,
    registerReportTableMatcher,
  } from '@views/risk-manage/detail/components/event-report/report-table-blot';
  import { QuillEditor } from '@vueup/vue-quill';

  import '@vueup/vue-quill/dist/vue-quill.snow.css';
  import '@vueup/vue-quill/dist/vue-quill.bubble.css';

  interface Emits{
    (e: 'update:content', value: string): void,
  }
  interface Props{
    disabled?: boolean;
    default?: string;
    maxLen?: number;
    height?: string;
    enableTable?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    maxLen: 0,
    default: '',
    disabled: false,
    height: 'auto',
    enableTable: false,
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const content = ref();
  const editorRef = ref();
  const insertTableDialogRef = ref<InstanceType<typeof InsertTableDialog>>();
  const TiLength = ref(0);
  const isEditorReady = ref(false);
  const isProgrammaticUpdate = ref(false);

  const openInsertTableDialog = () => {
    insertTableDialogRef.value?.show();
  };

  const buildToolbarContainer = () => {
    const lastRow: Array<string | Record<string, unknown>> = [
      'link',
      { background: [] },
      'code-block',
    ];
    if (props.enableTable) {
      lastRow.push('table');
    }
    return [
      [
        { header: 1 },
        'bold',
        'italic',
        'strike',
        'underline',
        { color: [] },
      ],
      [
        { align: '' },
        { align: 'center' },
        { align: 'right' },
        'blockquote',
        { list: 'ordered' },
        { list: 'bullet' },
      ],
      lastRow,
    ];
  };

  const options = reactive({
    modules: {
      toolbar: {
        container: buildToolbarContainer(),
        handlers: props.enableTable
          ? { table: openInsertTableDialog }
          : {},
      },
      history: {
        delay: 1000,
        maxStack: 50,
        userOnly: true,
      },
    },
  });
  const backgroundColor = ref('#fff');

  const getQuill = () => editorRef.value?.getQuill?.();

  const setupTableToolbarButton = () => {
    const quill = getQuill();
    if (!quill) return;
    const toolbar = quill.getModule('toolbar') as { container?: HTMLElement } | undefined;
    const tableButton = toolbar?.container?.querySelector('.ql-table') as HTMLElement | null;
    if (tableButton) {
      tableButton.innerHTML = t('插入表格');
      tableButton.setAttribute('title', t('插入表格'));
      tableButton.classList.add('rich-editor-table-btn');
    }
  };

  const repasteEditorHtml = (html: string) => {
    const quill = getQuill();
    if (!quill) return;
    isProgrammaticUpdate.value = true;
    quill.setText('', 'silent');
    quill.clipboard.dangerouslyPasteHTML(0, html);
    nextTick(() => {
      isProgrammaticUpdate.value = false;
      TiLength.value = quill.getLength() - 1;
    });
  };

  const applyContent = (html?: string) => {
    const value = html || '';
    if (!props.enableTable) {
      content.value = value;
      return;
    }
    const sanitized = value ? sanitizeEditorHtml(value) : '';
    content.value = sanitized;
    if (!isEditorReady.value || !sanitized) {
      return;
    }
    // 含表格或富文本结构时统一重贴，确保与预览一致
    if (hasTableContent(sanitized) || /<h[1-6]\b|<ul\b|<ol\b|<blockquote\b/i.test(sanitized)) {
      repasteEditorHtml(sanitized);
    }
  };

  const handleInsertTableConfirm = ({ rows, cols }: { rows: number; cols: number }) => {
    const quill = getQuill();
    if (!quill) return;
    insertReportTable(quill, rows, cols);
    TiLength.value = quill.getLength() - 1;
  };

  const onContentChange = (val: string) => {
    if (isProgrammaticUpdate.value) {
      return;
    }
    if (props.maxLen) {
      editorRef.value?.getQuill().deleteText(props.maxLen, 4);
    }
    if (!content.value || content.value === '') {
      TiLength.value = 0;
    } else {
      TiLength.value = editorRef.value?.getQuill().getLength() - 1;
    }
    emits('update:content', val);
  };

  const onEditorReady = () => {
    isEditorReady.value = true;
    const quill = getQuill();
    if (props.enableTable && quill) {
      registerReportTableMatcher(quill);
    }
    nextTick(() => {
      if (props.enableTable) {
        setupTableToolbarButton();
      }
      if (props.default) {
        applyContent(props.default);
      }
      TiLength.value = editorRef.value?.getQuill().getLength() - 1;
      editorRef.value?.getQuill().enable(!props?.disabled);
    });
  };

  onMounted(() => {
    if (!isEditorReady.value) {
      applyContent(props.default);
    }
  });

  watch(() => props.default, (val) => {
    if (isProgrammaticUpdate.value) return;
    const nextValue = val || '';
    if (nextValue === content.value) return;
    applyContent(nextValue);
  });

  watch(() => props.disabled, () => {
    editorRef.value?.getQuill().enable(!props.disabled);
  });

  watch(() => props.height, () => {
    if (props.height) {
      nextTick(() => {
        const el = editorRef.value?.$el?.querySelector?.('.ql-container.ql-snow') as HTMLElement | undefined;
        if (el) {
          el.style.height = props.height;
        }
      });
    }
  }, {
    immediate: true,
  });
</script>
<style lang="postcss">
.ql-toolbar {
  display: flex;
  padding: 0 !important;
  flex-wrap: wrap;
  align-items: center;
}


.ql-editor ul li:not(.ql-direction-rtl) {
  padding-left: var(--bk-theme-space-12);
}

.ql-editor ol li:not(.ql-direction-rtl) {
  padding-left: var(--bk-theme-space-16);
}

.ql-editor {
  ol,
  ul {
    padding-left: 0;
  }
}

/* 禁用时候的样式 */
.ql-disabled {
  background-color: var(--bk-theme-table-header-bg) !important;
}

:deep(.editor-wrap[active='false'] .ql-toolbar) {
  background-color: var(--bk-theme-table-header-bg);
}

/* toolbar 激活样式 */
:deep(.editor-wrap[active='true'] .ql-toolbar) {
  background-color: var(--bk-theme-surface-default);
}

.editor-wrap {
  position: relative;
  padding: var(--bk-theme-space-4) 0;
  box-sizing: border-box;

  .editor-tip-len {
    position: absolute;
    right: 5px;
    bottom: 2px;
  }

  .can-edit {
    color: green;
  }
}

.ql-container.ql-snow {
  min-height: 120px;
  padding-bottom: var(--bk-theme-space-12);
}

.editor-wrap--table .ql-editor .ql-report-table {
  margin: 0 0 var(--bk-theme-space-16);
}

.editor-wrap--table .ql-editor table {
  width: 100%;
  margin: 0 0 var(--bk-theme-space-16);
  font-size: 14px;
  border-collapse: collapse;
  table-layout: auto;
}

.editor-wrap--table .ql-editor th,
.editor-wrap--table .ql-editor td {padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
  color: var(--bk-theme-text-strong);
  text-align: left;
  vertical-align: top;
  border: 1px solid var(--bk-theme-border-default);
}

.editor-wrap--table .ql-editor thead th {
  font-weight: 600;
  color: var(--bk-theme-text-strong);
  background: var(--bk-theme-surface-subtle);
}

.editor-wrap--table .ql-editor h1,
.editor-wrap--table .ql-editor h2,
.editor-wrap--table .ql-editor h3,
.editor-wrap--table .ql-editor h4,
.editor-wrap--table .ql-editor h5,
.editor-wrap--table .ql-editor h6 {
  margin: var(--bk-theme-space-16) 0 var(--bk-theme-space-12);
  font-weight: 600;
  color: var(--bk-theme-text-strong);
}

.editor-wrap--table .ql-editor p {
  margin: 0 0 var(--bk-theme-space-12);
  line-height: 1.6;
  color: var(--bk-theme-text-strong);
}

.editor-wrap--table .ql-editor ul,
.editor-wrap--table .ql-editor ol {
  padding-left: var(--bk-theme-space-16);
  margin: 0 0 var(--bk-theme-space-12);
}

.editor-wrap--table .ql-editor li {
  margin-bottom: var(--bk-theme-space-4);
  line-height: 1.6;
}

.editor-wrap--table .ql-editor strong {
  font-weight: 600;
}

.editor-wrap--table .ql-editor blockquote {
  padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
  margin: 0 0 var(--bk-theme-space-12);
  color: var(--bk-theme-text-strong);
  background: var(--bk-theme-surface-subtle);
  border-left: 4px solid var(--bk-theme-border-default);
}

.editor-wrap--table .ql-editor hr {
  margin: var(--bk-theme-space-16) 0;
  border: 0;
  border-top: 1px solid var(--bk-theme-border-default);
}

.editor-wrap--table .ql-toolbar .rich-editor-table-btn {
  width: auto !important;
  padding: 0 var(--bk-theme-space-8) !important;
  margin: 0 var(--bk-theme-space-4);
  font-size: 14px !important;
  line-height: 24px !important;
  color: var(--bk-theme-color-brand-2) !important;
  cursor: pointer;
  background: transparent !important;
  border: none !important;
  border-radius: 0;
  box-shadow: none !important;
}

.editor-wrap--table .ql-toolbar .rich-editor-table-btn:hover {
  opacity: 80%;
}
</style>
