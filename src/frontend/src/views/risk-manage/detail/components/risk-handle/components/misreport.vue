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
  <div class="reopen-mis-report-wrap">
    <span class="misreport-label">{{ t('误报说明：') }}</span>
    <!-- eslint-disable vue/no-v-html -->
    <div
      class="description-html"
      @click="handleDescriptionImageClick"
      v-html="htmlText(data.description) || '--'" />
    <editor-image-preview
      v-if="descriptionImages.length > 0"
      ref="imagePreviewRef"
      class="inline-image-preview-hidden"
      :images="descriptionImages"
      :title="t('图片')" />
  </div>
</template>

<script setup lang='ts'>
  import DOMPurify from 'dompurify';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type RiskManageModel from '@model/risk/risk';

  import { sanitizeEditorHtml } from '@views/risk-manage/detail/components/event-report/editor-utils';
  import editorImagePreview from '@/components/editor-image-preview/index.vue';

  interface Props{
    data: RiskManageModel['ticket_history'][0]
  }
  const props = defineProps<Props>();
  const { t } = useI18n();

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

  const descriptionImages = computed(() => {
    const html = props.data.description;
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

    const index = descriptionImages.value.findIndex(item => (
      item.url === src || item.url === imgEl.src
    ));
    if (index < 0) return;

    imagePreviewRef.value?.openAt(index);
  };
</script>
<style scoped lang="postcss">
.reopen-mis-report-wrap {
  padding: 10px 16px;
  font-size: 12px;
  color: #63656e;
  background: #fff;
  border: 1px solid #eaebf0;
  border-radius: 6px;
  box-shadow: 0 2px 6px 0 #0000000a;
}

.misreport-label {
  display: block;
  margin-bottom: 8px;
  color: #313238;
}

.description-html {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  line-height: 1.6;
  word-break: break-word;
  white-space: normal;

  :deep(p) {
    margin: 0 0 8px;
  }

  :deep(.ql-report-table) {
    margin: 0 0 12px;
  }

  :deep(table),
  :deep(.report-table) {
    width: 100%;
    margin: 0 0 12px;
    font-size: 12px;
    background: #fff;
    border-collapse: collapse;
    table-layout: auto;
  }

  :deep(th),
  :deep(td) {
    padding: 8px 10px;
    color: #313238;
    text-align: left;
    vertical-align: top;
    border: 1px solid #dcdee5;
  }

  :deep(thead th) {
    font-weight: 600;
    color: #313238;
    background: #f5f7fa;
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
