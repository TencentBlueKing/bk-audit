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
      <bk-loading :loading="isLoading">
        <div class="report-preview-slider-preview-content">
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


  interface RiskReport {
    task_id: string,
    status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILURE'
    result: {
      description: string;
    },
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
  const paramsInfo = ref<aiPreviewParams>({
    risk_id: '',
    report_config: {
      template: '',
      frontend_template: '',
      ai_variables: [],
    },
  });
  // 使用 DOMPurify 清理 HTML 内容以防止 XSS（允许插入图片）
  const sanitizedContent = computed(() => DOMPurify.sanitize(concent.value, {
    ADD_TAGS: ['img'],
    ADD_ATTR: ['src', 'alt', 'width', 'height', 'title', 'style'],
  }));
  // 查询任务结果
  const {
    run: getTaskRiskReport,
  } = useRequest(RiskManageService.getTaskRiskReport, {
    defaultValue: null as any,
    onSuccess(data: RiskReport) {
      isLoading.value = false;
      concent.value = data.result.description;
    },
  });

  // 报告预览
  const {
    run: getReportPreview,
  } = useRequest(RiskManageService.getReportPreview, {
    defaultValue: null as any,
    onSuccess(data: aiPreviewData) {
      if (data.status === 'PENDING' || data.status === 'RUNNING') {
        isLoading.value = true;
        // 清除之前的定时器（如果存在）
        if (timerId.value !== null) {
          clearTimeout(timerId.value);
        }
        // 创建定时器 3秒后重试
        timerId.value = window.setTimeout(() => {
          getReportPreview(paramsInfo.value);
          timerId.value = null;
        }, 3000);
      } else if (data.status === 'SUCCESS') {
        // 清除定时器
        if (timerId.value !== null) {
          clearTimeout(timerId.value);
          timerId.value = null;
        }
        // 成功
        getTaskRiskReport({ task_id: data.task_id });
      } else if (data.status === 'FAILURE') {
        // 清除定时器
        if (timerId.value !== null) {
          clearTimeout(timerId.value);
          timerId.value = null;
        }
        isLoading.value = false;
        // 失败
        concent.value = '失败';
      }
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
.report-preview-slider-preview-content {
  width: 880px;
  height: calc(100vh - 120px);
  margin-top: 20px;
  margin-left: 40px;
  overflow-y: auto;

  .preview-info {
    padding: 12px;
    margin-bottom: 20px;
    background: #f5f7fa;
    border-radius: 2px;

    p {
      margin: 0;
      font-size: 14px;
      color: #63656e;
    }
  }

  .preview-html {
    min-height: 400px;
    padding: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }
}

</style>
<style lang="postcss">
.report-preview-slider-preview-content {
  .ai-concent {
    position: relative;
    width: 100%;
    padding: 8px 12px 8px 36px;
    margin-top: 10px;
    font-size: 12px;
    line-height: 20px;
    color: #4d4f56;
    background: #f5f7fa;
    border-radius: 4px;
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
