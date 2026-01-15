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
  <bk-sideslider
    v-model:isShow="isShowRight"
    :class="isPreviewExpanded ? 'ai-agent-drawer ai-agent-drawer-preview' : 'ai-agent-drawer'"
    quick-close
    :title="t('引用 AI 智能体')"
    transfer
    :width="740"
    @closed="handleClose">
    <template #default>
      <div
        :class="isPreviewExpanded ? `ai-agent-drawer-content-preview` : `ai-agent-drawer-content`">
        <div
          v-if="riskLisks.length === 0"
          class="tips-title">
          <audit-icon
            class="info-fill-icon"
            type="info-fill" />
          <span>{{ t('当前策略尚未产生风险单，暂时无法预览 AI 生成的内容') }}</span>
        </div>

        <bk-form
          ref="formRef"
          class="example"
          form-type="vertical"
          :model="formData"
          :rules="rules">
          <bk-form-item
            :label="t('名称')"
            property="name"
            required>
            <bk-input
              v-model="formData.name"
              clearable
              placeholder="请输入" />
          </bk-form-item>
          <bk-form-item
            :label="t('AI 提示词')"
            property="prompt_template"
            required>
            <bk-input
              v-model="formData.prompt_template"
              class="ai-prompt-textarea"
              :placeholder="t('请输入 AI 提示词，指导 AI 如何生成这部分内容')"
              :resize="false"
              :rows="textareaRows"
              style="border-radius: 4px;"
              type="textarea" />
          </bk-form-item>

          <bk-form-item
            v-if="riskLisks.length > 0"
            :label="t('关联审计风险单')">
            <bk-select
              v-model="formData.risk_id"
              class="risks-bk-select">
              <bk-option
                v-for="item in riskLisks"
                :id="item.risk_id"
                :key="item.risk_id"
                :name="`${item.title}(${item.risk_id})`" />
            </bk-select>
          </bk-form-item>
        </bk-form>
        <div class="ai-agent-drawer-footer">
          <div
            v-if="isShowConfirm"
            class="ai-agent-insert-btn mr8"
            @click="handleConfirm">
            {{ t('插入') }}
          </div>
          <div
            v-else
            class="ai-disabled-btn mr8">
            {{ t('插入') }}
          </div>
          <bk-button
            v-if="riskLisks.length > 0"
            v-bk-tooltips="{
              disabled: formData.risk_id !== '',
              content: t('请选择关联审计风险单'),
            }"
            class="mr8"
            :disabled="formData.risk_id === ''"
            outline
            theme="primary"
            @click="handlePreview">
            {{ t('预览') }}
          </bk-button>
          <bk-button
            class="ai-agent-cancel-btn"
            @click="handleClose">
            {{ t('取消') }}
          </bk-button>
        </div>
      </div>
    </template>
    <template #footer>
      <div :class="isPreviewExpanded ? 'footer': ''">
        <div
          class="preview"
          :class="{ 'expanded': isPreviewExpanded }"
          @click="handlePreviewFooter">
          <audit-icon
            class="preview-angle-line-up"
            :class="{ 'rotated': isPreviewExpanded }"
            type="angle-line-up" />
          <div class="preview-title">
            <span>{{ t('AI 生成内容预览') }}</span>
          </div>
        </div>
        <div
          v-if="isPreviewExpanded"
          class="preview-div" />
        <div
          v-if="isPreviewExpanded"
          class="preview-concent">
          <bk-loading :loading="isLoading">
            <div class="preview-concent-box">
              {{ concent }}
            </div>
          </bk-loading>
        </div>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import RiskManageService from '@service/risk-manage';

  import useRequest from '@hooks/use-request';

  interface riskItem {
    risk_id: string,
    title: string,
    strategy_id: number,
    created_at: string,
  }

  interface aiPreviewData {
    task_id: string,
    status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILURE'
  }

  interface RiskReport {
    task_id: string,
    status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILURE'
    result: {
      description: string;
    },
  }

  interface info {
    name: string,
    prompt_template: string,
    result: string,
  }
  interface Props {
    visible: boolean;
    initialPrompt?: info | null;
    riskLisks: Array<riskItem>;
  }
  interface Emits {
    (e: 'update:visible', value: boolean): void;
    (e: 'confirm', value: info): void;
  }
  const props = withDefaults(defineProps<Props>(), {
    initialPrompt: (): info => ({
      name: '',
      prompt_template: '',
      result: '',
    }),
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  // const isEditMode = route.name === 'strategyEdit';
  const isShowRight = ref(false);
  const formRef = ref();
  const textareaRows = ref(6);
  const isPreviewExpanded = ref(false);
  const isShowConfirm = ref(false);
  const isLoading = ref(true);
  const formData = ref({
    name: '',
    prompt_template: '',
    risk_id: '',
  });
  const rules = ref({});

  const concent = ref('');
  const timerId = ref<number | null>(null);
  const aiInfo = ref({
    name: '',
    prompt_template: '',
    result: '',
  });
  const handleClose = () => {
    isShowRight.value = false;
    if (timerId.value !== null) {
      clearTimeout(timerId.value);
      timerId.value = null;
    }
  };

  const handleConfirm = () => {
    // 如果不是编辑模式
    aiInfo.value = {
      name: formData.value.name,
      prompt_template: formData.value.prompt_template,
      result: '',
    };

    emit('confirm', aiInfo.value);
    isShowRight.value = false;
  };

  // 查询任务结果
  const {
    run: getTaskRiskReport,
  } = useRequest(RiskManageService.getTaskRiskReport, {
    defaultValue: null as any,
    onSuccess(data: RiskReport) {
      isLoading.value = false;
      isShowConfirm.value = false;
      concent.value = data.result.description;
    },
  });

  // Ai预览
  const {
    run: getAiPreview,
  } = useRequest(RiskManageService.getAiPreview, {
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
          getAiPreview({
            id: route.params.id,
            risk_id: formData.value.risk_id,
            ai_variables: [{
              name: `ai.${formData.value.name}`,
              prompt_template: formData.value.prompt_template,
            }],
          });
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
        isLoading.value = false;
        // 失败
        concent.value = '失败';
        // 清除定时器
        if (timerId.value !== null) {
          clearTimeout(timerId.value);
          timerId.value = null;
        }
      }
    },
  });

  const handlePreview = () => {
    formRef.value.validate().then(() => {
      isLoading.value = true;
      isPreviewExpanded.value = true;
      // 延迟计算 rows，让高度过渡动画先完成，使过渡更平滑
      nextTick(() => {
        setTimeout(() => {
          calculateTextareaRows();
          getAiPreview({
            id: route.params.id,
            risk_id: formData.value.risk_id,
            ai_variables: [{
              name: `ai.${formData.value.name}`,
              prompt_template: formData.value.prompt_template,
            }],
          }).finally(() => {
            isLoading.value = false;
          });
        }, 0);
      });
    });
  };

  const handlePreviewFooter = () => {
    isLoading.value = false;
    isPreviewExpanded.value = !isPreviewExpanded.value;
    // 延迟计算 rows，让高度过渡动画先完成，使过渡更平滑
    nextTick(() => {
      setTimeout(() => {
        calculateTextareaRows();
      }, 300);
    });
  };

  // 计算 textarea 的 rows 值（基于页面高度的 50%）
  const calculateTextareaRows = () => {
    if (isPreviewExpanded.value) {
      textareaRows.value = 3;
      return;
    }
    // 获取视口高度
    const viewportHeight = window.innerHeight;
    // 计算目标高度（视口高度的 50%）
    const targetHeight = viewportHeight *  0.6;
    // textarea 每行高度大约为 22px（包括行间距和 padding）
    const lineHeight = 22;
    // 计算行数
    const calculatedRows = Math.floor(targetHeight / lineHeight);
    // 设置最小和最大行数限制
    textareaRows.value = Math.max(10, Math.min(calculatedRows, 50));
  };

  // 窗口大小变化时重新计算
  const handleResize = () => {
    calculateTextareaRows();
  };

  // 初始化表单数据的函数
  const initializeFormData = () => {
    if (props.initialPrompt) {
      formData.value = {
        name: props.initialPrompt.name || '',
        prompt_template: props.initialPrompt.prompt_template || '',
        risk_id: '',
      };
      aiInfo.value = { ...props.initialPrompt };
    } else {
      // 重置为默认值
      formData.value = {
        name: '',
        prompt_template: '',
        risk_id: '',
      };
      aiInfo.value = {
        name: '',
        prompt_template: '',
        result: '',
      };
    }
    // 重置预览状态
    isPreviewExpanded.value = false;
  };
  // 同步 visible 和 isShowRight
  watch(() => props.visible, (newVal) => {
    isShowRight.value = newVal;
    if (newVal) {
      initializeFormData();
      nextTick(() => {
        formRef.value.clearValidate();
      });
    }
  }, { immediate: true });

  // 监听 initialPrompt 变化，确保编辑时表单能正确更新
  watch(() => props.initialPrompt, () => {
    if (props.visible && isShowRight.value) {
      initializeFormData();
    }
  }, { deep: true });

  watch(() => isShowRight.value, (newVal) => {
    if (!newVal) {
      emit('update:visible', false);
    } else {
      // 弹窗打开时重新计算 rows
      setTimeout(() => {
        calculateTextareaRows();
      }, 100);
    }
  });

  // 组件挂载时计算并监听窗口大小变化
  onMounted(() => {
    calculateTextareaRows();
    window.addEventListener('resize', handleResize);
    nextTick(() => {
      formRef.value?.clearValidate();
      isShowConfirm.value = !(props.riskLisks.length > 0);
    });
  });

  // 组件卸载时移除事件监听和清除定时器
  onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
    // 清除定时器
    if (timerId.value !== null) {
      clearTimeout(timerId.value);
      timerId.value = null;
    }
  });
</script>

<style lang="postcss" scoped>
.ai-agent-drawer-content,
.ai-agent-drawer-content-preview {
  width: calc(100% - 100px);
  margin-left: 50px;
  overflow: hidden;
  transition: height .4s cubic-bezier(.4, 0, .2, 1);
}

.ai-agent-drawer-content {
  height: calc(100vh - 130px);
}

.ai-agent-drawer-content-preview {
  height: 40vh;
}

.tips-title {
  display: flex;
  width: 100%;
  height: 32px;
  margin-top: 28px;
  font-size: 12px;
  line-height: 32px;
  color: #4d4f56;
  background: #f0f5ff;
  border: 1px solid #a3c5fd;
  border-radius: 2px;

  .info-fill-icon {
    margin-right: 9px;
    margin-left: 9px;
    font-size: 14px;
    line-height: 32px;
    color: #3a84ff;
  }
}

.example {
  margin-top: 20px;
  transition: opacity .3s ease;
}


.ai-agent-drawer-footer {
  display: flex;

  .ai-agent-insert-btn {
    width: 88px;
    height: 32px;
    font-size: 14px;
    line-height: 32px;
    color: #fff;
    text-align: center;
    cursor: pointer;
    background: linear-gradient(117deg, #235dfa 26%, #eb8cec 100%);
    border: none;
    border-radius: 2px;
    box-shadow: 0 1px 2px rgb(0 0 0 / 8%);
  }

  .ai-disabled-btn {
    width: 88px;
    height: 32px;
    font-size: 14px;
    line-height: 32px;
    color: #fff;
    text-align: center;
    cursor: pointer;
    background-color: #dcdee5;
    border: none;
    border-radius: 2px;
    box-shadow: 0 1px 2px rgb(0 0 0 / 8%);
  }
}

.footer {
  position: relative;
  width: 765px;
  height: 55vh;
  margin-left: -25px;
}

.preview {
  width: 700px;
  height: 48px;
  margin-left: 20px;
  line-height: 48px;
  cursor: pointer;
  border-top: 1px solid #dde4eb;
  transition: background-color .2s ease;

  .preview-angle-line-up {
    position: absolute;
    left: 20px;
    font-size: 14px;
    line-height: 52px;
    transition: transform .4s cubic-bezier(.4, 0, .2, 1);
    transform-origin: center;

    &.rotated {
      transform: rotate(180deg);
    }
  }

  .preview-title {
    margin-left: 15px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0;
    color: #4d4f56;
  }
}

.preview-div {
  width: 765px;
  height: 20px;
  margin-left: -25px;
  background-color: #fff;
}

.preview-concent {
  width: 765px;
  height: 100%;
  padding-bottom: 20px;
  margin-left: -25px;
  background-color: #fff;
}

.preview-concent-box {
  width: 740px;
  height: calc( 100% - 70px);
  padding: 0 40px;
  margin-left: 25px;
  overflow-y: auto;
}

.ai-agent-drawer-preview {
  :deep(.bk-modal-footer) {
    height: 52px;
    background-color: rgb(255 86 245 / 8%) !important;

    .bk-sideslider-footer {
      background-color: rgb(255 86 245 / 8%) !important;
    }
  }
}

.ai-agent-drawer {
  :deep(.bk-modal-body) {
    position: relative;
    padding-bottom: 52px; /* 为底部 preview 预留空间 */
    background-color: #f5f7fa;
  }

  :deep(.bk-modal-footer) {
    height: 52px;
    margin-top: -5px;
    background-color: #fff ;

    .bk-sideslider-footer {
      margin-top: -5px;
      background-color: #fff ;
    }
  }
}
</style>
