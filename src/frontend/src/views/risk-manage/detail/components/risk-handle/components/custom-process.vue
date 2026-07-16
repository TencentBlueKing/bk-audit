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
          class="ql-editor"
          v-html="htmlText(data.description) || '--'" />
        <editor-image-preview
          v-if="editorImages.length > 0"
          :images="editorImages"
          :title="t('图片')" />
      </render-info-item>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import type RiskManageModel from '@model/risk/risk';

  import EditTag from '@components/edit-box/tag.vue';

  import RenderInfoItem from '@views/risk-manage/detail/components/render-info-item.vue';

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
  const editorImages = computed(() => {
    const htmlContent = props.data.description;

    if (!htmlContent) {
      return [];
    }

    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlContent, 'text/html');
    const imgElements = doc.querySelectorAll('img');

    const images = Array.from(imgElements).map(img => ({
      url: img.src,
    }));

    return images;
  });

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
  const htmlText = (value: string) => value.replace(/<img[^>]*>/g, '');
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
        padding-left: 4px;
        line-height: 20px;
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

.ql-editor {
  max-width: 160px;
  padding: 0;
  white-space: pre-wrap;
}
</style>
