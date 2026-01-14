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
  // 使用 DOMPurify 清理 HTML 内容以防止 XSS
  const sanitizedContent = computed(() => DOMPurify.sanitize(concent.value));
  // 查询任务结果
  const {
    run: getTaskRiskReport,
  } = useRequest(RiskManageService.getTaskRiskReport, {
    defaultValue: null as any,
    onSuccess(data: RiskReport) {
      console.log('查询任务结果', data);

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
      console.log('报告预览', data);
      if (data.status === 'PENDING' || data.status === 'RUNNING') {
        console.log('重试');
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
    console.log('关闭');
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
      console.log('参数', params);
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

    :deep(.ql-ai-agent) {
      position: relative;
      display: block;
      width: 100%;
      height: 90px;
      padding: 0;
      margin: 10px 0;
      line-height: 1;
    }

    :deep(.ai-agent-block) {
      position: absolute;
      top: 0;
      display: flex;
      width: 100%;
      min-height: auto;
      padding: 4px 12px;
      margin: 0;
      background: #f5f7fa;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      align-items: center;
    }

    :deep(.ai-agent-content) {
      display: flex;
      height: 80px;
      padding-top: 10px;
      margin-left: 35px;
      flex: 1;
      flex-direction: column;
      gap: 2px;
    }

    :deep(.ai-agent-label) {
      font-size: 14px;
      font-weight: 700;
      line-height: 22px;
      letter-spacing: 0;
      color: #313238;
    }

    :deep(.ai-agent-prompt) {
      font-size: 12px;
      line-height: 20px;
      letter-spacing: 0;
      color: #4d4f56;
      text-align: justify;
    }

    :deep(p) {
      margin: 0 0 10px;
      line-height: 1.5;
    }
  }
}

</style>
<style lang="postcss">
.report-preview-slider-preview-content {
  .ai-agent-block {
    position: relative;
    width: 100%;
    margin-top: 10px;
    background: #f5f7fa;
    border-radius: 4px;

    .ai-agent-ai {
      position: absolute;
      top: 10px;
      left: 10px;
      width: 25px;
      height: 25px;
    }

    .ai-agent-content {
      padding: 10px 10px 10px 50px;

      .ai-agent-label {
        font-size: 14px;
        font-weight: 700;
        line-height: 22px;
        letter-spacing: 0;
        color: #313238;
      }

      .ai-agent-prompt {
        font-size: 12px;
        line-height: 20px;
        letter-spacing: 0;
        color: #4d4f56;
      }
    }

    .ai-agent-actions {
      display: none;
    }
  }}
</style>
