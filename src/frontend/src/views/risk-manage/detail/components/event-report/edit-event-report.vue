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
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="isShowEditEventReport"
    show-footer-slot
    :title="reportContent ? '编辑事件调查报告' : '创建事件调查报告'"
    :width="1100">
    <div class="edit-event-report-content">
      <bk-button
        v-if="reportEnabled"
        class="mb16"
        outline
        theme="primary"
        @click="handleGenerateReport">
        {{ t('使用模版生成') }}
      </bk-button>
      <span
        v-if="reportEnabled"
        class="template-generate-tip">
        <audit-icon
          class="info-fill-icon"
          type="info-fill" />
        {{ t('使用该风险对应的审计策略中配置的事件调查报告模板自动填充内容') }}
      </span>
      <bk-loading
        class="edit-event-report-editor"
        :loading="riskReportGenerateLoading || isPollingLoading"
        mode="spin"
        size="small"
        theme="primary"
        :title="t('正在使用模版生成报告内容')">
        <quill-editor
          ref="quillEditorRef"
          v-model:content="localeReportContent"
          content-type="html"
          :options="editorOptions"
          style="height: 1000px;"
          @ready="handleEditorReady"
          @text-change="handleTextChange" />
      </bk-loading>
    </div>
    <template #footer>
      <bk-button
        class="w88"
        :disabled="isApiLoading"
        :loading="saveRiskReportLoading"
        theme="primary"
        @click="handleSubmit">
        {{ reportContent ? t('保存') : t('创建') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="closeDialog">
        {{ t('取消') }}
      </bk-button>
    </template>
    <save-report-dialog
      ref="saveReportDialogRef"
      :status="status"
      @submit="handleSaveReportSubmit" />
  </audit-sideslider>
</template>
<script setup lang="tsx">
  import {
    InfoBox,
  } from 'bkui-vue';
  import Quill from 'quill';
  import {
    h,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import RiskReportService from '@service/risk-report';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import { QuillEditor } from '@vueup/vue-quill';

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import AIAgentBlot from './ai-model';
  import { sanitizeEditorHtml } from './editor-utils';
  import saveReportDialog from './save-report-dialog.vue';

  import useMessage from '@/hooks/use-message';


  interface Props {
    reportContent?: string;
    status: string | undefined;
    reportEnabled: boolean;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<{
    update: [];
  }>();
  const { t } = useI18n();
  const {
    replaceSearchParams,
  } = useUrlSearch();
  const route = useRoute();
  const { messageSuccess } = useMessage();
  const isApiLoading = ref(false);
  const isRegetVal = ref(false);
  const isChangeVal = ref(false);
  const baseReportContent = ref<string>('');
  const saveReportDialogRef = ref();
  const editorOptions = {
    theme: 'snow',
    modules: {
      toolbar: {
        container: [
          [{ header: [1, 2, 3, 4, 5, 6, false] }],
          [{ font: [] }],
          [{ size: [] }],
          ['bold', 'italic', 'underline', 'strike'],
          [{ color: [] }, { background: [] }],
          [{ script: 'sub' }, { script: 'super' }],
          [{ header: 1 }, { header: 2 }, 'blockquote', 'code-block'],
          [{ list: 'ordered' }, { list: 'bullet' }, { indent: '-1' }, { indent: '+1' }],
          [{ direction: 'rtl' }, { align: [] }],
          ['link', 'image', 'video'],
          ['clean'],
        ],
      },
    },
    placeholder: '开始输入...',
  };

  const quillEditFlag = ref(false);
  const isProgrammaticUpdate = ref(false);
  const quillEditorRef = ref<InstanceType<typeof QuillEditor>>();
  const aiAgentData = ref<Array<{ id: string; name: string; prompt: string }>>([]);
  const aiBlockToken = '[[AI_AGENT_BLOCK]]';
  const localeReportContent = ref<string>('');
  const isEditorReady = ref(false);

  const getQuillInstance = () => (quillEditorRef.value as any)?.getQuill?.();

  const normalizeContentWithAiBlock = (content: string) => {
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${content}</div>`, 'text/html');
    const container = doc.body.firstElementChild as HTMLElement | null;
    if (!container) {
      return { html: content, aiAgent: [] as typeof aiAgentData.value };
    }

    const targets = Array.from(container.querySelectorAll('.ql-ai-agent, .ai-content')) as HTMLElement[];
    if (!targets.length) {
      return { html: container.innerHTML, aiAgent: [] as typeof aiAgentData.value };
    }

    const aiAgents: Array<{ id: string; name: string; prompt: string }> = [];
    targets.forEach((targetNode, index) => {
      const prompt = targetNode.getAttribute('data-prompt') || targetNode.textContent || '';
      const name = targetNode.getAttribute('data-name') || t('完整AI总结');
      const id = targetNode.getAttribute('data-id') || `ai-summary-${index + 1}`;
      const placeholder = doc.createElement('span');
      placeholder.setAttribute('data-ai-placeholder', 'true');
      placeholder.setAttribute('data-ai-embed', 'true');
      placeholder.setAttribute('data-id', id);
      placeholder.setAttribute('data-name', name);
      placeholder.setAttribute('data-prompt', prompt);
      placeholder.setAttribute('data-ai-index', String(index));
      placeholder.textContent = aiBlockToken;
      targetNode.parentNode?.replaceChild(placeholder, targetNode);
      aiAgents.push({ id, name, prompt });
    });

    return {
      html: container.innerHTML,
      aiAgent: aiAgents,
    };
  };

  const insertAiAgentBlock = (retries = 6) => {
    if (!aiAgentData.value.length) return;
    const quill = getQuillInstance();
    if (!quill) {
      if (retries > 0) {
        setTimeout(() => insertAiAgentBlock(retries - 1), 0);
      }
      return;
    }
    const placeholders = Array.from(quill.root.querySelectorAll('[data-ai-placeholder="true"]')) as HTMLElement[];
    isProgrammaticUpdate.value = true;
    if (placeholders.length) {
      for (let i = placeholders.length - 1; i >= 0; i--) {
        const placeholder = placeholders[i];
        const dataIndex = Number(placeholder.getAttribute('data-ai-index') || i);
        const data = aiAgentData.value[dataIndex];
        if (!data) continue;
        const blot = Quill.find(placeholder);
        if (!blot) continue;
        const blotIndex = quill.getIndex(blot);
        if (typeof blotIndex !== 'number') continue;
        quill.deleteText(blotIndex, aiBlockToken.length, 'api');
        quill.insertEmbed(blotIndex, 'aiAgent', {
          id: data.id,
          name: data.name,
          prompt: data.prompt,
          result: '',
        }, 'api');
        // 不额外插入换行，避免智能体块后出现空白行
      }
    } else {
      let searchIndex = quill.getText().lastIndexOf(aiBlockToken);
      if (searchIndex === -1) {
        if (retries > 0) {
          setTimeout(() => insertAiAgentBlock(retries - 1), 0);
        }
        return;
      }
      for (let i = aiAgentData.value.length - 1; i >= 0 && searchIndex !== -1; i--) {
        const data = aiAgentData.value[i];
        quill.deleteText(searchIndex, aiBlockToken.length, 'api');
        quill.insertEmbed(searchIndex, 'aiAgent', {
          id: data.id,
          name: data.name,
          prompt: data.prompt,
          result: '',
        }, 'api');
        // 不额外插入换行，避免智能体块后出现空白行
        searchIndex = quill.getText().lastIndexOf(aiBlockToken, searchIndex - 1);
      }
    }
    nextTick(() => {
      isProgrammaticUpdate.value = false;
      quillEditFlag.value = false;
    });
  };

  const applyEditorContent = (content: string) => {
    const sanitized = sanitizeEditorHtml(content);
    const normalized = normalizeContentWithAiBlock(sanitized);
    localeReportContent.value = normalized.html;
    baseReportContent.value = normalized.html;
    isApiLoading.value = localeReportContent.value === baseReportContent.value;
    aiAgentData.value = normalized.aiAgent;
    if (!isEditorReady.value) return;
    nextTick(() => {
      if (normalized.aiAgent.length) {
        insertAiAgentBlock();
      } else {
        nextTick(() => {
          isProgrammaticUpdate.value = false;
          quillEditFlag.value = false;
        });
      }
    });
  };

  const restoreAiContentBlocks = (content: string) => {
    if (!content) return content;
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${content}</div>`, 'text/html');
    const container = doc.body.firstElementChild as HTMLElement | null;
    if (!container) return content;
    const legacyBlocks = Array.from(container.querySelectorAll('.ai-agent-block')) as HTMLElement[];
    legacyBlocks.forEach((block) => {
      block.parentNode?.removeChild(block);
    });
    const targets = Array.from(container.querySelectorAll('.ql-ai-agent')) as HTMLElement[];
    targets.forEach((targetNode) => {
      const prompt = targetNode.getAttribute('data-prompt') || targetNode.textContent || '';
      const block = doc.createElement('div');
      block.className = 'ai-content';
      block.textContent = prompt;
      targetNode.parentNode?.replaceChild(block, targetNode);
    });
    const normalizedChildren = Array.from(container.children) as HTMLElement[];
    let pendingBreak = false;
    normalizedChildren.forEach((node) => {
      const isEmptyParagraph = node.tagName.toLowerCase() === 'p'
        && node.innerHTML
          .replace(/<br\s*\/?>/gi, '')
          .replace(/\uFEFF/g, '')
          .trim() === '';
      if (!isEmptyParagraph) {
        pendingBreak = false;
        return;
      }
      if (pendingBreak) {
        node.parentNode?.removeChild(node);
      } else {
        pendingBreak = true;
      }
    });
    return container.innerHTML;
  };

  const handleEditorReady = () => {
    const quill = getQuillInstance();
    if (quill) {
      const Delta = Quill.import('delta') as any;
      quill.clipboard.addMatcher('span[data-ai-embed="true"]', (node: Node) => {
        const element = node as HTMLElement;
        const id = element.getAttribute('data-id') || Date.now().toString();
        const name = element.getAttribute('data-name') || t('完整AI总结');
        const prompt = element.getAttribute('data-prompt') || '';
        return new Delta()
          .insert({
            aiAgent: {
              id,
              name,
              prompt,
              result: '',
            },
          });
      });
    }
    isEditorReady.value = true;
    nextTick(() => {
      if (aiAgentData.value.length) {
        insertAiAgentBlock();
      }
    });
  };

  // 监听 props 变化，更新本地内容
  watch(() => props.reportContent, (newContent) => {
    if (newContent !== undefined) {
      nextTick(() => {
        applyEditorContent(newContent);
        isChangeVal.value = false;
      });
    }
  }, { immediate: true });

  const isShowEditEventReport = defineModel<boolean>('isShowEditEventReport', {
    required: true,
  });
  watch(isShowEditEventReport, (show) => {
    if (!show) return;
    nextTick(() => {
      if (props.reportContent !== undefined) {
        applyEditorContent(props.reportContent);
      } else {
        applyEditorContent('');
      }
    });
  });

  const {
    run: saveOrUpdateRiskReport,
    loading: saveRiskReportLoading,
  } = useRequest(props.reportContent ? RiskReportService.updateRiskReport : RiskReportService.saveRiskReport, {
    defaultValue: {},
    onSuccess: () => {
      props.reportEnabled ? messageSuccess(t('编辑成功')) : messageSuccess(t('创建成功'));
      // 通知父组件刷新数据
      emits('update');
      // 关闭对话框
      closeDialog();
    },
  });

  // 轮询控制
  let pollTimer: number | null = null;
  let isPolling = false;
  let currentTaskId: string | null = null;
  const isPollingLoading = ref(false); // 轮询过程中的 loading 状态

  const {
    run: riskReportGenerate,
    loading: riskReportGenerateLoading,
  } = useRequest(RiskReportService.riskReportGenerate, {
    defaultValue: {
      task_id: '',
      status: '',
    },
    onSuccess: (data) => {
      // 轮询查询任务结果，直到status为SUCCESS或者FAILURE
      if (data?.task_id) {
        startPolling(data.task_id);
      }
    },
  });

  const {
    run: fetchRiskReport,
  } = useRequest(RiskReportService.fetchRiskReport, {
    defaultValue: {
      task_id: '',
      status: '',
      result: '',
    },
    onSuccess: (data) => {
      if (!data) return;

      const { status, result } = data;
      if (status === 'SUCCESS' || status === 'FAILURE') {
        // 任务完成，停止轮询
        stopPolling();

        if (status === 'SUCCESS' && result) {
          // 更新报告内容
          applyEditorContent(result);
        } else if (status === 'FAILURE') {
          // 任务失败，提示用户
          InfoBox({
            type: 'danger',
            title: t('生成报告失败'),
            subTitle: t('报告生成过程中出现错误，请稍后重试'),
            confirmText: t('确定'),
          });
        }
      } else {
        // 任务还在进行中，继续轮询
        continuePolling();
      }
    },
  });

  // 开始轮询
  const startPolling = (taskId: string) => {
    if (isPolling) {
      stopPolling();
    }
    isPolling = true;
    isPollingLoading.value = true; // 开始轮询时设置 loading
    currentTaskId = taskId;

    // 立即查询一次
    fetchRiskReport({
      task_id: taskId,
      risk_id: route.params.riskId as string,
    });
  };

  // 继续轮询
  const continuePolling = () => {
    if (!isPolling || !currentTaskId) return;

    // 清除之前的定时器
    if (pollTimer) {
      clearTimeout(pollTimer);
    }

    // 2秒后再次查询
    pollTimer = setTimeout(() => {
      if (!isPolling || !currentTaskId) return;
      fetchRiskReport({
        task_id: currentTaskId,
        risk_id: route.params.riskId as string,
      });
    }, 1000) as unknown as number;
  };

  // 停止轮询
  const stopPolling = () => {
    isPolling = false;
    isApiLoading.value = localeReportContent.value === baseReportContent.value;
    isPollingLoading.value = false; // 停止轮询时取消 loading
    currentTaskId = null;
    setTimeout(() => {
      quillEditFlag.value = false;
      isChangeVal.value = false;
    }, 1000);
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  };

  const handleGenerateReport = () => {
    const typeText = '模版生成';
    const titleText = `确认使用${typeText}报告`;
    const subTitleText =  t('系统将根据最新的审计策略配置和风险信息自动填充内容，在生成报告之前，当前报告内容将被清空，请谨慎操作');

    InfoBox({
      type: 'warning',
      title: t(titleText),
      subTitle: () => h('div', {
        style: {
          color: '#4D4F56',
          backgroundColor: '#f5f6fa',
          padding: '12px 16px',
          borderRadius: '2px',
          fontSize: '14px',
          textAlign: 'left',
        },
      }, t(subTitleText)),
      confirmText: t('生成报告'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        // 清空当前报告内容
        applyEditorContent('');
        isApiLoading.value = true;
        quillEditFlag.value = false;
        isRegetVal.value = true;
        isChangeVal.value = false;
        // 获取task_id
        riskReportGenerate({
          risk_id: route.params.riskId,
        }).finally(() => {
          isChangeVal.value = false;
        });
      },
    });
  };

  const handleTextChange = () => {
    isChangeVal.value = true;
    if (!isProgrammaticUpdate.value) {
      quillEditFlag.value = true;
    }
    isApiLoading.value = localeReportContent.value === baseReportContent.value;
  };
  const isAutoGenerate = ref(false);
  const handleSubmit = () => {
    const manualText = '保存后，报告将被标记为「人工编辑」状态，后续有新事件触发，系统不会自动覆盖您编辑的内容，需要您手动更新报告';
    const autoText = '保存后，报告将被标记为「自动生成」状态，后续有新事件触发，系统将自动更新该报表内容';
    const isAutoReport = props.status === 'auto';
    const hasChange = isChangeVal.value;
    const hasReget = isRegetVal.value;
    let subTitleText = manualText;
    let isShowButton = false;

    if (hasChange) {
      subTitleText = manualText;
      isAutoGenerate.value = false;
    } else if (isAutoReport) {
      subTitleText = autoText;
      isAutoGenerate.value = true;
    } else if (hasReget) {
      subTitleText = autoText;
      isAutoGenerate.value = true;
      isShowButton = true;
    } else {
      subTitleText = manualText;
      isAutoGenerate.value = true;
    }

    // 人工编辑后，则提示用户

    nextTick(() => {
      saveReportDialogRef.value?.show(subTitleText, isShowButton);
    });
  };
  const handleSaveReportSubmit = (isAuto: boolean) => {
    const restoredContent = restoreAiContentBlocks(localeReportContent.value);
    saveOrUpdateRiskReport({
      risk_id: route.params.riskId,
      content: restoredContent,
      auto_generate: isAuto ? isAutoGenerate.value : false,
    });


    saveReportDialogRef.value?.hide();
    closeDialog();
  };
  const closeDialog = () => {
    isChangeVal.value = false;
    // 停止轮询
    stopPolling();
    isShowEditEventReport.value = false;
    quillEditFlag.value = false;
    // 重置url
    replaceSearchParams({
    });
  };
  // 组件卸载时清理轮询
  onBeforeUnmount(() => {
    stopPolling();
  });

  onMounted(() => {
    nextTick(() => {
      setTimeout(() => {
        isChangeVal.value = false;
      }, 1000);
    });
  });
</script>

<style lang="postcss" scoped>
.edit-event-report-content {
  padding: 28px 40px;
  background-color: #f5f7fa;

  .template-generate-tip {
    margin-left: 8px;
    font-size: 12px;
    color: #979ba5;
  }

  .edit-event-report-editor {
    background-color: #fff;

    :deep(.bk-loading-title) {
      margin-left: -50px !important;
    }
  }
}

/* AI智能体块样式 */
:deep(.ql-ai-agent) {
  position: relative;
  display: block;
  width: 100%;
  height: auto;
  padding: 0;
  margin: 0;
  line-height: 1;
}

:deep(.ai-agent-block) {
  display: flex;
  width: 100%;
  min-height: auto;
  padding: 2px 10px;
  margin: 0;
  background: #f5f7fa;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  align-items: flex-start;
}

:deep(.ai-agent-content) {
  display: flex;
  padding: 4px 0;
  margin-left: 35px;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

:deep(.ai-agent-label) {
  font-family: MicrosoftYaHei-Bold, sans-serif;
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
  letter-spacing: 0;
  color: #313238;
}

:deep(.ai-agent-prompt) {
  display: block;
  overflow: visible;
  font-family: MicrosoftYaHei, sans-serif;
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0;
  color: #4d4f56;
  text-align: justify;
  word-break: break-word;
}

:deep(.ai-agent-actions) {
  top: 20px;
  right: 8px;
  display: flex;
  margin-top: 6px;
  align-self: flex-start;
  gap: 8px;
}

:deep(.ai-agent-edit),
:deep(.ai-agent-delete) {
  width: 16px;
  height: 16px;
  padding: 0;
  cursor: pointer;
  transition: all .2s;
  user-select: none;
  -webkit-user-drag: none;
}

:deep(.ai-agent-edit:hover),
:deep(.ai-agent-delete:hover) {
  opacity: 70%;
}

:deep(.ai-agent-ai) {
  position: absolute;
  margin-top: 12px;
}

/* 移除AI智能体块周围的默认间距 */
:deep(.ql-editor .ql-ai-agent) {
  padding: 0;
  margin: 0;
}

:deep(.ql-editor p) {
  margin: 0 0 12px;
  line-height: 1.5;
}

:deep(.ql-editor h1),
:deep(.ql-editor h2),
:deep(.ql-editor h3),
:deep(.ql-editor h4),
:deep(.ql-editor h5),
:deep(.ql-editor h6),
:deep(.ql-editor ul),
:deep(.ql-editor ol) {
  margin: 0 0 12px;
}

:deep(.ql-editor ul),
:deep(.ql-editor ol) {
  padding-left: 20px;
}

:deep(.ql-editor li) {
  margin-bottom: 4px;
}
</style>
