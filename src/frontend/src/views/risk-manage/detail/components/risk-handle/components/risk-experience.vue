<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="approve-wrap risk-experience-wrap">
    <div class="mis-content">
      <render-info-item
        :label="t('评论人')"
        :label-width="labelWidth">
        <span>{{ experience.created_by || '--' }}</span>
        <audit-icon
          v-if="showEditBtn"
          class="edit-icon"
          type="edit-fill"
          @click="emits('edit')" />
      </render-info-item>
      <render-info-item
        class="mt8"
        :label="t('评论内容')"
        :label-width="labelWidth">
        <!-- eslint-disable vue/no-v-html -->
        <div
          class="description-html"
          @click="handleDescriptionImageClick"
          v-html="htmlText(experience.content) || '--'" />
        <editor-image-preview
          v-if="contentImages.length > 0"
          ref="imagePreviewRef"
          class="inline-image-preview-hidden"
          :images="contentImages"
          :title="t('图片')" />
      </render-info-item>
    </div>
  </div>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import { computed, ref, withDefaults } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type RiskExperienceManageModel from '@model/risk-experience/experience';

  import RenderInfoItem from '@views/risk-manage/detail/components/render-info-item.vue';
  import { sanitizeEditorHtml } from '@views/risk-manage/detail/components/event-report/editor-utils';
  import editorImagePreview from '@/components/editor-image-preview/index.vue';

  interface TimelineExperienceItem {
    action: 'RiskExperience';
    time: string;
    experience: RiskExperienceManageModel;
  }

  interface Props {
    data: TimelineExperienceItem;
    showEditBtn?: boolean;
  }

  interface Emits {
    (e: 'edit'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    showEditBtn: false,
  });
  const emits = defineEmits<Emits>();
  const { t, locale } = useI18n();

  const experience = computed(() => props.data.experience);
  const labelWidth = computed(() => (locale.value === 'en-US' ? 100 : 80));

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
    const html = experience.value.content;
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
.edit-icon {
  margin-left: 8px;
  color: #3a84ff;
  cursor: pointer;
}

.description-html {
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

  :deep(ul) {
    padding-left: 15px;

    li {
      list-style: disc !important;
    }
  }

  :deep(ol) {
    padding-left: 13px;

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
