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
  <div class="risk-content-item">
    <div class="risk-content-title">
      <span style="color: #63656e;">{{ data.created_by }} {{ t('添加风险总结') }}</span>
      <span style=" margin-left: 8px;color: #979ba5;">{{ data.created_at }}</span>
      <audit-icon
        v-if="showEditBtn"
        style="margin-left: 5px;color: #3a84ff;cursor: pointer;"
        type="edit-fill"
        @click="handleEdit" />
    </div>
    <!-- eslint-disable vue/no-v-html -->
    <div
      class="description-html"
      @click="handleDescriptionImageClick"
      v-html="htmlText(data.content) || '--'" />

    <editor-image-preview
      v-if="contentImages.length > 0"
      ref="imagePreviewRef"
      class="inline-image-preview-hidden"
      :images="contentImages"
      :title="t('图片')" />
  </div>
</template>

<script setup lang='ts'>
  import DOMPurify from 'dompurify';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type RiskExperienceManageModel from '@model/risk-experience/experience';

  import { sanitizeEditorHtml } from '@views/risk-manage/detail/components/event-report/editor-utils';
  import editorImagePreview from '@/components/editor-image-preview/index.vue';

  interface Emits{
    (e:'edit'):void,
  }

  interface Props{
    data: RiskExperienceManageModel,
    showEditBtn: boolean,
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const handleEdit = () => {
    emits('edit');
  };

  const DISPLAY_HTML_OPTIONS = {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'strong', 'em', 'u', 's', 'strike', 'code', 'hr', 'pre', 'blockquote',
      'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
      'ul', 'ol', 'li', 'span', 'div', 'a', 'img', 'sub', 'sup', 'iframe',
    ],
    ALLOWED_ATTR: [
      'class', 'colspan', 'rowspan', 'href', 'target', 'rel',
      'src', 'alt', 'width', 'height', 'style',
      'frameborder', 'allowfullscreen',
    ],
  };

  const htmlText = (value: string) => {
    if (!value) return '';
    const sanitized = sanitizeEditorHtml(value);
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${sanitized}</div>`, 'text/html');
    const container = doc.body.firstElementChild;
    const imageNodes = container?.querySelectorAll('img');
    if (imageNodes) {
      for (let index = 0; index < imageNodes.length; index += 1) {
        const imageElement = imageNodes[index] as HTMLImageElement;
        imageElement.removeAttribute('width');
        imageElement.removeAttribute('height');
        imageElement.style.maxWidth = '100%';
        imageElement.style.height = 'auto';
        imageElement.style.verticalAlign = 'bottom';
      }
    }
    const normalizedHtml = container?.innerHTML || sanitized;
    return DOMPurify.sanitize(normalizedHtml, DISPLAY_HTML_OPTIONS);
  };

  const contentImages = computed(() => {
    const html = props.data.content;
    if (!html) return [];

    const sanitized = sanitizeEditorHtml(html);
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${sanitized}</div>`, 'text/html');
    const imgElements = doc.querySelectorAll('img') as NodeListOf<HTMLImageElement>;

    return Array.from(imgElements)
      .map(img => ({ url: img.src }))
      .filter(item => item.url);
  });

  const imagePreviewRef = ref<InstanceType<typeof editorImagePreview> | null>(null);

  const handleDescriptionImageClick = (event: MouseEvent) => {
    const target = event.target as HTMLElement | null;
    if (!target) return;

    const imgEl = target.closest('img') as HTMLImageElement | null;
    if (!imgEl) return;

    const src = imgEl.getAttribute('src');
    if (!src) return;

    const index = contentImages.value.findIndex(item => (
      item.url === src || item.url === imgEl.src
    ));
    if (index < 0) return;

    imagePreviewRef.value?.openAt(index);
  };
</script>
<style scoped lang="postcss">
.risk-content-item {padding: var(--bk-theme-space-8) var(--bk-theme-space-16);
  background: var(--bk-theme-surface-default);
  border: 1px solid var(--bk-theme-border-weak);
  border-radius: var(--bk-theme-control-radius);
  box-shadow: var(--bk-theme-card-shadow);

  .risk-content-title {
    display: flex;
    font-size: 12px;
    align-items: center;
  }
}

.description-html {
  padding: var(--bk-theme-space-8);
  margin-top: var(--bk-theme-space-8);
  overflow-x: auto;
  line-height: 1.6;
  word-break: break-word;
  white-space: normal;
  background: var(--bk-theme-surface-subtle);
  border-radius: var(--bk-theme-tag-radius);

  :deep(p) {
    margin: 0 0 var(--bk-theme-space-8);
  }

  :deep(.ql-report-table) {
    margin: 0 0 var(--bk-theme-space-12);
  }

  :deep(table),
  :deep(.report-table) {
    width: 100%;
    margin: 0 0 var(--bk-theme-space-12);
    font-size: 12px;
    background: var(--bk-theme-surface-default);
    border-collapse: collapse;
    table-layout: auto;
  }

  :deep(th),
  :deep(td) {padding: var(--bk-theme-space-8) var(--bk-theme-space-8);
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

  :deep(ul) {
    padding-left: var(--bk-theme-space-16);

    li {
      list-style: disc !important;
    }
  }

  :deep(ol) {
    padding-left: var(--bk-theme-space-12);

    li {
      list-style: decimal;
    }
  }

  :deep(img) {
    display: inline;
    height: auto;
    max-width: 100%;
    vertical-align: bottom;
    cursor: zoom-in;
  }
}

.inline-image-preview-hidden {
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;

  :deep(.preview-header) {
    display: none;
  }

  :deep(.preview-grid) {
    display: none;
  }
}
</style>
