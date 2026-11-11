<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <bk-sideslider
    v-model:isShow="isShow"
    class="report-preview-slider"
    quick-close
    :title="t('报告预览')"
    transfer
    :width="960"
    @closed="handleClose">
    <template #default>
      <bk-loading
        class="report-preview-slider-loading"
        :loading="isLoading"
        mode="spin"
        size="small"
        theme="primary"
        :title="t('正在使用模版生成报告内容')">
        <div class="report-preview-slider-preview-content">
          <audit-icon
            v-bk-tooltips="t('复制所有')"
            class="preview-copy-icon"
            type="copy"
            @click="handleCopy" />
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-html="sanitizedContent" />
        </div>
      </bk-loading>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useRequest from '@hooks/use-request';

  import { execCopy } from '@utils/assist';


  interface RiskReport {
    task_id: string,
    status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILURE'
    result: string,
  }

  interface aiPreviewParams {
    risk_id: string,
    report_config: {
      template: string,
      frontend_template: string,
      ai_variables: Array<{
        name: string,
        prompt_template: string
      }>
    }
  }

  interface aiPreviewData {
    task_id: string,
    status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILURE'
  }

  interface Props {
    visible: boolean;
  }
  interface Emits {
    (e: 'update:visible', value: boolean): void;
  }
  interface Exposes {
    setContent: (params: aiPreviewParams) => void
  }

  const props = withDefaults(defineProps<Props>(), {
  });

  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const isShow = ref(false);
  const concent = ref('');
  const isLoading = ref(false);
  const timerId = ref<number | null>(null);
  const taskId = ref('');
  const paramsInfo = ref<aiPreviewParams>({
    risk_id: '',
    report_config: {
      template: '',
      frontend_template: '',
      ai_variables: [],
    },
  });
  const getCopyText = (content: string) => {
    const normalized = String(content ?? '').replace(/\\n/g, '\n');
    const hasHtmlTag = /<\/?[a-z][\s\S]*>/i.test(normalized);
    if (!hasHtmlTag) {
      return normalized;
    }
    const container = document.createElement('div');
    container.innerHTML = normalized;
    return (container.innerText || '').trim();
  };
  const handleCopy = () => {
    execCopy(getCopyText(concent.value), t('复制成功'));
  };
  // 使用 DOMPurify 清理 HTML 内容以防止 XSS（允许插入图片）
  const sanitizedContent = computed(() => {
    const normalized = String(concent.value ?? '').replace(/\\n/g, '\n');
    const hasHtmlTag = /<\/?[a-z][\s\S]*>/i.test(normalized);
    if (!hasHtmlTag) {
      const escaped = normalized
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      return DOMPurify.sanitize(escaped.replace(/\n/g, '<br/>'), {
        ADD_TAGS: ['img'],
        ADD_ATTR: ['src', 'alt', 'width', 'height', 'title', 'style'],
      });
    }
    return DOMPurify.sanitize(normalized, {
      ADD_TAGS: ['img'],
      ADD_ATTR: ['src', 'alt', 'width', 'height', 'title', 'style'],
    });
  });
  // 查询任务结果
  const {
    run: getTaskRiskReport,
  } = useRequest(RiskManageService.getTaskRiskReport, {
    defaultValue: null as any,
    onSuccess(data: RiskReport) {
      if (data.status === 'PENDING' || data.status === 'RUNNING') {
        isLoading.value = true;
        // 清除之前的定时器（如果存在）
        if (timerId.value !== null) {
          clearTimeout(timerId.value);
        }
        // 创建定时器 3秒后重试
        timerId.value = window.setTimeout(() => {
          getTaskRiskReport({ task_id: taskId.value  });
          timerId.value = null;
        }, 3000);
      } else if (data.status === 'SUCCESS') {
        // 清除定时器
        if (timerId.value !== null) {
          clearTimeout(timerId.value);
          timerId.value = null;
        }
        isLoading.value = false;
        concent.value = data.result;
        // 成功
      } else if (data.status === 'FAILURE') {
        isLoading.value = false;
        // 失败
        concent.value = t('失败');
        // 清除定时器
        if (timerId.value !== null) {
          clearTimeout(timerId.value);
          timerId.value = null;
        }
      }
    },
  });

  // 报告预览
  const {
    run: getReportPreview,
  } = useRequest(RiskManageService.getReportPreview, {
    defaultValue: null as any,
    onSuccess(data: aiPreviewData) {
      taskId.value = data.task_id;
      getTaskRiskReport({ task_id: data.task_id });
    },
  });
  // 关闭
  const handleClose = () => {
    isShow.value = false;
    isLoading.value = false;

    // 清除定时器
    if (timerId.value !== null) {
      clearTimeout(timerId.value);
      timerId.value = null;
    }
  };
  // 同步 visible 和 isShow
  watch(() => props.visible, (newVal: boolean) => {
    isShow.value = newVal;
  }, { immediate: true });

  watch(() => isShow.value, (newVal: boolean) => {
    if (!newVal) {
      emits('update:visible', false);
    }
  });
  defineExpose<Exposes>({
    setContent: (params: aiPreviewParams) => {
      paramsInfo.value = params;
      isLoading.value = true;
      // 清除定时器
      if (timerId.value !== null) {
        clearTimeout(timerId.value);
        timerId.value = null;
      }
      getReportPreview(params);
    },
  });
</script>

<style lang="postcss" scoped>
.report-preview-slider-loading {
  :deep(.bk-loading-title) {
    margin-left: -var(--bk-theme-space-32) !important;
  }
}

.report-preview-slider-preview-content {
  position: relative;
  width: 880px;
  height: calc(100vh - 120px);
  margin-top: var(--bk-theme-space-16);
  margin-left: var(--bk-theme-space-32);
  overflow: hidden auto;
  word-break: break-word;
  word-wrap: break-word;
  white-space: pre-wrap;

  .preview-copy-icon {
    position: absolute;
    top: 6px;
    right: 6px;
    font-size: 16px;
    color: var(--bk-theme-text-default);
    cursor: pointer;
    transition: color .2s;

    &:hover {
      color: var(--bk-theme-color-brand-2);
    }
  }

  .preview-info {
    padding: var(--bk-theme-space-12);
    margin-bottom: var(--bk-theme-space-16);
    background: var(--bk-theme-surface-subtle);
    border-radius: var(--bk-theme-tag-radius);

    p {
      margin: 0;
      font-size: 14px;
      color: var(--bk-theme-text-default);
    }
  }

  .preview-html {
    min-height: 400px;
    padding: var(--bk-theme-space-16);
    background: var(--bk-theme-surface-default);
    border: 1px solid var(--bk-theme-border-default);
    border-radius: var(--bk-theme-tag-radius);
  }

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4),
  :deep(h5),
  :deep(h6),
  :deep(p),
  :deep(ul),
  :deep(ol) {
    margin: 0 0 var(--bk-theme-space-12);
    word-break: break-word;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }

  :deep(img) {
    height: auto;
    max-width: 100%;
  }

  :deep(pre),
  :deep(code) {
    max-width: 100%;
    overflow-x: auto;
    word-break: break-word;
    word-wrap: break-word;
    white-space: pre-wrap;
    overflow-wrap: break-word;
  }

  :deep(ul),
  :deep(ol) {
    padding-left: var(--bk-theme-space-16);
  }

  :deep(li) {
    margin-bottom: var(--bk-theme-space-4);
  }

  :deep(table) {
    width: 100%;
    max-width: 100%;
    margin: var(--bk-theme-space-8) 0 var(--bk-theme-space-12);
    border-collapse: collapse;
    table-layout: fixed;
  }

  :deep(th),
  :deep(td) {
    padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
    word-break: break-word;
    word-wrap: break-word;
    overflow-wrap: break-word;
    vertical-align: top;
    border: 1px solid var(--bk-theme-border-default);
  }

  :deep(thead th) {
    font-weight: 600;
    background: var(--bk-theme-surface-subtle);
  }
}

</style>
<style lang="postcss">
.report-preview-slider-preview-content {
  .ai-content {
    position: relative;
    width: 100%;
    padding: var(--bk-theme-space-8) var(--bk-theme-space-12) var(--bk-theme-space-8) 36px;
    margin-top: var(--bk-theme-space-12);
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-text-default);
    background: var(--bk-theme-surface-subtle);
    border-radius: var(--bk-theme-tag-radius);
    box-sizing: border-box;

    &::before {
      position: absolute;
      top: 10px;
      left: 12px;
      width: 18px;
      height: 18px;
      background: url('@images/ai.svg') center center / contain no-repeat;
      content: '';
    }

    img {
      display: block;
      height: auto;
      max-width: 100%;
    }
  }}
</style>
