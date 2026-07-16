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
    <div class="mis-title">
      <span style="color: #313238">{{ data.operator }}</span>
      <span
        class="ml8"
        style="color: #979ba5">{{ data.time }}</span>
    </div>
    <div class="mis-content">
      <render-info-item
        :label="t('处理方法')">
        <span v-if="data.custom_action === 'CloseRisk'">{{ t('人工关单') }}</span>
        <span v-else-if="data.custom_action === 'TransOperator'">
          {{ t('转单给') }} {{ data.new_operators?.join(',') }}
        </span>
        <span v-else>{{ t('处理套餐') }} </span>
      </render-info-item>
      <template v-if="data.custom_action === 'AutoProcess'">
        <div class="mis-pa-params">
          <render-info-item
            v-for="field in paParamDisplayFields"
            :key="field.key"
            :label="field.label">
            <edit-tag
              v-if="field.displayType === 'tag'"
              :data="field.displayValue"
              :show-copy="false"
              style="display: inline-block;" />
            <span v-else>{{ field.displayValue || '--' }}</span>
          </render-info-item>
        </div>
      </template>
      <render-info-item
        v-else
        class="mt8"
        :label="t('处理说明')">
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

<script setup lang='ts'>
  import DOMPurify from 'dompurify';
  import {
    computed,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import type RiskManageModel from '@model/risk/risk';

  import EditTag from '@components/edit-box/tag.vue';

  import RenderInfoItem from '@views/risk-manage/detail/components/render-info-item.vue';
  import { sanitizeEditorHtml } from '@views/risk-manage/detail/components/event-report/editor-utils';
  import editorImagePreview from '@/components/editor-image-preview/index.vue';


  interface Props{
    data: RiskManageModel['ticket_history'][0],
    processApplicationList: Array<{
      id: string,
      name: string,
      sops_template_id: number,
    }>,
    riskFieldMap: Record<string, string>,
    // 处理套餐详情
    processDetail: Record<string, any>
  }
  const props = defineProps<Props>();
  const { t } = useI18n();

  // 与编辑器内容一致展示（含图片、表格等），只做安全过滤
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

  const processPackageDetail = computed(() => {
    if (props.data && props.processDetail) {
      const ret = props.processDetail[props.data.pa_id] || {};
      return ret;
    }
    return {};
  });

  const sortedPaParamKeys = computed(() => {
    if (!props.data.pa_params) {
      return [];
    }
    return Object.keys(props.data.pa_params)
      .filter(key => processPackageDetail.value[key]?.show_type === 'show')
      .sort((a, b) => {
        const indexA = processPackageDetail.value[a]?.index ?? 0;
        const indexB = processPackageDetail.value[b]?.index ?? 0;
        return indexA - indexB;
      });
  });

  interface PaParamDisplayField {
    key: string,
    label: string,
    displayType: 'text' | 'tag',
    displayValue: string | string[],
  }

  const getSelectDisplayText = (config: Record<string, any>, rawValue: any) => {
    if (rawValue === '' || rawValue === null || rawValue === undefined) {
      return '';
    }
    try {
      const valueConfig = typeof config.value === 'string'
        ? JSON.parse(config.value)
        : config.value;
      const itemsText = valueConfig?.items_text;
      if (!itemsText) {
        return String(rawValue);
      }
      const items = typeof itemsText === 'string'
        ? JSON.parse(itemsText)
        : itemsText;
      if (!Array.isArray(items)) {
        return String(rawValue);
      }
      const matched = items.find((item: { value: string | number, text: string }) => (
        String(item.value) === String(rawValue)
      ));
      return matched?.text ?? String(rawValue);
    } catch {
      return String(rawValue);
    }
  };

  const isFieldRef = (param: { field?: string | number, value?: any }) => {
    const field = param?.field;
    return field !== '' && field !== null && field !== undefined;
  };

  const normalizeTagValue = (value: any) => {
    if (Array.isArray(value)) {
      return value.filter(item => item !== '' && item !== null && item !== undefined);
    }
    if (typeof value === 'string' && value.includes(',')) {
      return value.split(',').map(item => item.trim())
        .filter(Boolean);
    }
    return value;
  };

  const getPaParamDisplayField = (key: string): PaParamDisplayField => {
    const config = processPackageDetail.value[key] || {};
    const param = props.data.pa_params?.[key] || { field: '', value: '' };
    const label = config.name || key;
    const isUserSelector = config.custom_type === 'bk_user_selector';
    const isSelect = config.custom_type === 'select';

    if (isFieldRef(param)) {
      const fieldKey = String(param.field);
      return {
        key,
        label,
        displayType: 'text',
        displayValue: props.riskFieldMap[fieldKey] || fieldKey,
      };
    }

    if (isUserSelector) {
      const tagValue = normalizeTagValue(param.value);
      return {
        key,
        label,
        displayType: 'tag',
        displayValue: tagValue,
      };
    }

    if (isSelect) {
      return {
        key,
        label,
        displayType: 'text',
        displayValue: getSelectDisplayText(config, param.value),
      };
    }

    const textValue = Array.isArray(param.value)
      ? param.value.join(', ')
      : (param.value ?? '');

    return {
      key,
      label,
      displayType: 'text',
      displayValue: String(textValue),
    };
  };

  const paParamDisplayFields = computed(() => [
    {
      key: '__pa_id__',
      label: t('选择套餐'),
      displayType: 'text' as const,
      displayValue: props.processApplicationList
        .find(item => item.id === props.data.pa_id)?.name
        || props.data.pa_id
        || '',
    },
    ...sortedPaParamKeys.value.map(key => getPaParamDisplayField(key)),
    {
      key: '__auto_close__',
      label: t('套餐执行成功后自动关单'),
      displayType: 'text' as const,
      displayValue: props.data.auto_close_risk ? t('是') : t('否'),
    },
  ]);
</script>
<style scoped lang="postcss">
.reopen-mis-report-wrap {
  padding: 10px 16px;
  background: #fff;
  border: 1px solid #eaebf0;
  border-radius: 6px;
  box-shadow: 0 2px 6px 0 #0000000a;

  .mis-title {
    font-size: 12px;
  }

  >.mis-content {
    padding: 12px 0;
    margin-top: 8px;
    background: #f5f7fa;
    border-radius: 4px;

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

        .tips {
          border-bottom: none;
        }
      }

      :deep(.info-value) {
        min-width: 0;
        padding-left: 4px;
        line-height: 20px;
        flex: 1;
      }
    }

    .mis-pa-params {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 8px;

      .render-info-item {
        width: 100%;
      }
    }
  }
}

.description-html {
  width: 100%;
  max-width: 100%;
  padding: 0;
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

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4),
  :deep(h5),
  :deep(h6) {
    margin: 8px 0;
    font-weight: 600;
    color: #313238;
  }

  :deep(ul),
  :deep(ol) {
    padding-left: 20px;
    margin: 0 0 8px;
  }

  :deep(blockquote),
  :deep(.report-blockquote) {
    padding: 6px 10px;
    margin: 0 0 8px;
    color: #63656e;
    background: #f0f1f5;
    border-left: 4px solid #dcdee5;
  }

  :deep(img) {
    display: inline;
    height: auto;
    max-width: 100%;
    vertical-align: bottom;
    cursor: zoom-in;
  }

  :deep(iframe) {
    max-width: 100%;
    margin: 8px 0;
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
