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
<!-- eslint-disable vue/no-v-html -->
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
            <div
              class="prompt_template-link"
              @click="handleJumpLink">
              <span>{{ t('提示词最佳实践') }} </span>
              <audit-icon
                class="preview-angle-jump-link"
                type="jump-link" />
            </div>
            <bk-input
              v-model="formData.prompt_template"
              :class="isPreviewExpanded ? '' : 'ai-prompt-textarea'"
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
              class="risks-bk-select"
              filterable
              :no-match-text="t('无匹配数据')"
              :prefix="t('审计风险工单')"
              :search-placeholder="t('请输入风险标题或风险ID')">
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
            v-if="canSave"
            class="ai-agent-insert-btn mr8"
            @click="handleConfirm">
            {{ primaryButtonText }}
          </div>
          <div
            v-else
            class="ai-disabled-btn mr8">
            {{ primaryButtonText }}
          </div>
          <bk-button
            v-if="riskLisks.length > 0"
            v-bk-tooltips="{
              disabled: formData.risk_id !== '',
              content: t('请选择关联审计风险单'),
            }"
            class="mr8"
            :disabled="formData.risk_id === '' || isPreviewing"
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
      <div
        v-if="riskLisks.length !== 0"
        :class="isPreviewExpanded ? 'footer': ''">
        <div
          class="preview"
          :class="{ 'expanded': isPreviewExpanded }"
          @click="handlePreviewFooter">
          <audit-icon
            class="preview-angle-line-up"
            :class="{ 'rotated': isPreviewExpanded }"
            type="angle-line-up" />
          <div class="preview-title">
            <span>{{ t('AI 生成内容预览') }}
            </span>
          </div>
        </div>
        <div
          v-if="isPreviewExpanded"
          class="preview-div" />
        <div
          v-if="isPreviewExpanded"
          class="preview-concent">
          <bk-loading
            :class="isLoading ? 'preview-loading' : ''"
            :loading="isLoading"
            mode="spin"
            size="small"
            theme="primary"
            :title="t('正在使用AI生成报告内容')">
            <audit-icon
              v-if="getContent(concent) !== ''"
              v-bk-tooltips="t('复制所有')"
              class="preview-angle-copy"
              type="copy"
              @click="handleCopy" />
            <div class="preview-concent-box">
              <div v-html="getContent(concent)" />
            </div>
          </bk-loading>
        </div>
      </div>
      <div
        v-else
        class="footer-elese" />
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';
  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  import { execCopy } from '@utils/assist';

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
      ai: any;
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
  const taskId = ref('');
  // const isEditMode = route.name === 'strategyEdit';
  const isShowRight = ref(false);
  const formRef = ref();
  const textareaRows = ref(3);
  const isPreviewExpanded = ref(false);
  const initialFormSnapshot = ref({
    name: '',
    prompt_template: '',
  });
  const isLoading = ref(true);
  const isPreviewing = ref(false);
  const formData = ref({
    name: '',
    prompt_template: '',
    risk_id: '',
  });
  const namePattern = /^[a-zA-Z_\u4e00-\u9fa5][a-zA-Z0-9_\u4e00-\u9fa5]*$/;
  const rules = ref({
    name: [
      {
        validator: (value: string) => {
          const trimmed = (value || '').trim();
          if (!trimmed) {
            return true;
          }
          return namePattern.test(trimmed);
        },
        message: t('名称需以字母、下划线或中文开头，只能包含字母、数字、下划线和中文'),
        trigger: 'blur',
      },
    ],
  });

  const concent = ref('');
  const timerId = ref<number | null>(null);
  const aiInfo = ref({
    name: '',
    prompt_template: '',
    result: '',
  });

  const trimmedName = computed(() => formData.value.name.trim());
  const trimmedPrompt = computed(() => formData.value.prompt_template.trim());
  const hasRequiredFields = computed(() => trimmedName.value !== '' && trimmedPrompt.value !== '');
  const isInsertMode = computed(() => props.initialPrompt === null);
  const primaryButtonText = computed(() => (isInsertMode.value ? t('插入') : t('保存')));
  const isChangedFromInitial = computed(() => (
    trimmedName.value !== initialFormSnapshot.value.name
    || trimmedPrompt.value !== initialFormSnapshot.value.prompt_template
  ));
  const canSave = computed(() => {
    if (!hasRequiredFields.value) {
      return false;
    }
    const initialEmpty = initialFormSnapshot.value.name === ''
      && initialFormSnapshot.value.prompt_template === '';
    return initialEmpty || isChangedFromInitial.value;
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

  // 全局数据
  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });
  // 跳转链接新窗口
  const handleJumpLink = () => {
    if (configData.value) {
      window.open(configData.value.help_info.ai_practices.ai_summary, '_blank');
    }
  };

  const updateInitialSnapshot = () => {
    initialFormSnapshot.value = {
      name: formData.value.name.trim(),
      prompt_template: formData.value.prompt_template.trim(),
    };
  };

  const getContent = (content: string) => {
    const normalized = String(content ?? '').replace(/\\n/g, '\n');
    const hasHtmlTag = /<\/?[a-z][\s\S]*>/i.test(normalized);
    if (!hasHtmlTag) {
      const escaped = normalized
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      return DOMPurify.sanitize(escaped.replace(/\n/g, '<br/>'));
    }
    return DOMPurify.sanitize(normalized);
  };
  const handleClose = () => {
    isShowRight.value = false;
    if (timerId.value !== null) {
      clearTimeout(timerId.value);
      timerId.value = null;
    }
  };

  const handleConfirm = () => {
    formRef.value?.validate?.().then(() => {
      // 如果不是编辑模式
      aiInfo.value = {
        name: formData.value.name,
        prompt_template: formData.value.prompt_template,
        result: '',
      };

      emit('confirm', aiInfo.value);
      isShowRight.value = false;
    });
  };

  // 查询任务结果
  const {
    run: getTaskRiskReport,
  } = useRequest(RiskManageService.getTaskRiskReport, {
    defaultValue: null as any,
    onSuccess(data: RiskReport) {
      if (data.status === 'PENDING' || data.status === 'RUNNING') {
        isLoading.value = true;
        isPreviewing.value = true;
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
        isPreviewing.value = false;
        const aiResult = data.result?.ai || {};
        concent.value =   Object.values(aiResult).length === 0 ? '暂无数据' : String(Object.values(aiResult)[0]);
        // 成功
      } else if (data.status === 'FAILURE') {
        isLoading.value = false;
        isPreviewing.value = false;
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

  // Ai预览
  const {
    run: getAiPreview,
  } = useRequest(RiskManageService.getAiPreview, {
    defaultValue: null as any,
    onSuccess(data: aiPreviewData) {
      taskId.value = data.task_id;
      getTaskRiskReport({ task_id: data.task_id });
    },
  });

  const handlePreview = () => {
    formRef.value.validate().then(() => {
      concent.value = '';
      isLoading.value = true;
      isPreviewExpanded.value = true;
      isPreviewing.value = true;
      // 延迟计算 rows，让高度过渡动画先完成，使过渡更平滑
      nextTick(() => {
        setTimeout(() => {
          calculateTextareaRows();
          getAiPreview({
            id: formData.value.risk_id,
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

  // 计算 textarea 的 rows 值（基于页面高度的 70%）
  const calculateTextareaRows = () => {
    if (isPreviewExpanded.value) {
      textareaRows.value = 4;
      return;
    }
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
    updateInitialSnapshot();
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
      console.log('!(props.riskLisks.length > 0)', !(props.riskLisks.length > 0));
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
  position: relative;
  width: 765px;
  height: calc(55vh - 68px);
  padding-bottom: 20px;
  margin-left: -25px;
  overflow: hidden;
  background-color: #fff;

  :deep(.bk-loading),
  :deep(.bk-loading-wrapper) {
    display: block;
    height: 100%;
  }
}

.preview-loading {
  position: absolute;
  top: 0%;
  left: 55%;
  transform: translateX(-50%);

  :deep(.bk-loading-title) {
    margin-left: -50px !important;
  }
}

.preview-concent-box {
  width: 740px;
  height: auto;
  max-height: calc(55vh - 68px);
  padding: 0 40px;
  padding-bottom: 20px;
  margin-left: 25px;
  overflow: hidden auto;
  word-break: break-word;
  white-space: pre-wrap;

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4),
  :deep(h5),
  :deep(h6),
  :deep(p),
  :deep(ul),
  :deep(ol) {
    margin: 0 0 12px;
  }

  :deep(ul),
  :deep(ol) {
    padding-left: 20px;
  }

  :deep(li) {
    margin-bottom: 4px;
  }

  :deep(table) {
    width: 100%;
    margin: 8px 0 12px;
    border-collapse: collapse;
  }

  :deep(th),
  :deep(td) {
    padding: 8px 12px;
    word-break: break-word;
    vertical-align: top;
    border: 1px solid #dcdee5;
  }

  :deep(thead th) {
    font-weight: 600;
    background: #f5f7fa;
  }
}

.preview-angle-copy {
  position: absolute;
  top: 10px;
  right: 20px;
  font-size: 18px;
  cursor: pointer;

  &:hover {
    color: #3a84ff;
  }
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

.footer-elese {
  position: absolute;
  width: 100%;
  height: 52px;
  margin-left: -25px;
  background-color: #f5f7fa;
}

:deep(.ai-prompt-textarea.bk-textarea > textarea) {
  height: calc(100vh - 400px) !important;
}

.prompt_template-link {
  position: absolute;
  top: -30px;
  right: 0;
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;

  .preview-angle-jump-link {
    margin-left: 5px;
    font-size: 14px;
    color: #3a84ff;
    cursor: pointer;
  }
}
</style>
