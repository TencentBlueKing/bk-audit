<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="reopen-mis-report-wrap">
    <div class="mis-content">
      <render-info-item :label="t('确认说明')">
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
      </render-info-item>
    </div>
  </div>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type RiskManageModel from '@model/risk/risk';

  import { sanitizeEditorHtml } from '@views/risk-manage/detail/components/event-report/editor-utils';
  import RenderInfoItem from '@views/risk-manage/detail/components/render-info-item.vue';
  import editorImagePreview from '@/components/editor-image-preview/index.vue';

  interface Props {
    data: RiskManageModel['ticket_history'][number],
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
  padding: 0;
  font-size: 12px;
  color: #63656e;
  background: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;

  > .mis-content {
    padding: 12px 8px 12px 12px;
    background: #f5f7fa;
    border-radius: 2px;

    .render-info-item {
      align-items: flex-start;

      :deep(.info-label) {
        width: auto !important;
        max-width: none !important;
        min-width: 0 !important;
        line-height: 20px;
        text-align: left;
        word-break: keep-all;
        white-space: nowrap;
        flex: 0 0 auto !important;
      }

      :deep(.info-value) {
        min-width: 0;
        padding-left: 4px;
        line-height: 20px;
        flex: 1;
      }
    }
  }
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
