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
      <bk-popover
        v-if="!reportEnabled"
        placement="top"
        theme="dark">
        <bk-button
          class="mb16"
          disabled
          outline
          theme="primary"
          @click="handleGenerateReport">
          {{ reportContent ? t('重新生成报告') : t('自动生成报告') }}
        </bk-button>
        <template #content>
          <component :is="reportEnabledTeps" />
        </template>
      </bk-popover>
      <bk-button
        v-else
        class="mb16"
        outline
        theme="primary"
        @click="handleGenerateReport">
        {{ reportContent ? t('重新生成报告') : t('自动生成报告') }}
      </bk-button>

      <bk-loading
        class="edit-event-report-editor"
        :loading="riskReportGenerateLoading || isPollingLoading">
        <quill-editor
          ref="quillEditorRef"
          v-model:content="localeReportContent"
          content-type="html"
          :options="editorOptions"
          style="height: 1000px;"
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
  import {
    h,
    nextTick,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import RiskReportService from '@service/risk-report';
  import StrategyManageService from '@service/strategy-manage';

  import useRequest from '@hooks/use-request';

  import { QuillEditor } from '@vueup/vue-quill';

  import saveReportDialog from './save-report-dialog.vue';

  import useMessage from '@/hooks/use-message';

  interface Props {
    reportContent?: string;
    status: string | undefined;
    reportEnabled: boolean;
    strategyId: number | string;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<{
    update: [];
  }>();
  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const { messageSuccess } = useMessage();
  const isApiLoading = ref(false);
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
  const quillEditorRef = ref<InstanceType<typeof QuillEditor>>();
  const localeReportContent = ref(props.reportContent || '');

  // 监听 props 变化，更新本地内容
  watch(() => props.reportContent, (newContent) => {
    if (newContent !== undefined) {
      localeReportContent.value = newContent;
    }
  }, { immediate: true });

  const isShowEditEventReport = defineModel<boolean>('isShowEditEventReport', {
    required: true,
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
          localeReportContent.value = result;
          // 如果编辑器已初始化，同步更新编辑器内容
          if (quillEditorRef.value) {
            quillEditorRef.value.setHTML(result);
          }
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
    isApiLoading.value = false;
    isPollingLoading.value = false; // 停止轮询时取消 loading
    currentTaskId = null;
    console.log('status', props.status);
    setTimeout(() => {
      quillEditFlag.value = false;
    }, 0);
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  };

  const handleGenerateReport = () => {
    const typeText = props.reportContent ? '重新生成' : '自动生成';
    const titleText = `确认${typeText}报告`;
    const subTitleText =  props.reportContent ? t('系统将根据最新的审计策略配置和风险信息重新生成报告，在重新生成之前，当前报告内容将被清空，请谨慎操作')
      : t('系统将根据最新的审计策略配置和风险信息自动生成报告，在自动生成之前，当前报告内容将被清空，请谨慎操作');

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
      confirmText: t(typeText),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        // 清空当前报告内容
        localeReportContent.value = '';
        if (quillEditorRef.value) {
          quillEditorRef.value.setHTML('');
        }
        isApiLoading.value = true;
        quillEditFlag.value = false;
        // 获取task_id
        riskReportGenerate({
          risk_id: route.params.riskId,
        });
      },
    });
  };

  const handleTextChange = () => {
    quillEditFlag.value = true;
  };

  const handleSubmit = () => {
    // 人工编辑后，则提示用户
    const subTitleText = quillEditFlag.value
      ? t('保存后，报告将被标记为「人工编辑」状态，后续有新事件触发，系统不会自动覆盖您编辑的内容，需要您手动更新报告')
      : t('保存后，报告将被标记为「自动生成」状态，后续有新事件触发，系统将自动更新该报表内容');
    nextTick(() => {
      console.log('saveReportDialogRef', saveReportDialogRef.value);
      saveReportDialogRef.value?.show(subTitleText, quillEditFlag.value);
    });
  };
  const handleSaveReportSubmit = (isAuto: boolean) => {
    console.log('handleSaveReportSubmit', isAuto,  quillEditFlag.value, props.status);
    if (props.status === 'auto') { // 自动生成的单子
      if (quillEditFlag.value) { // 没有点击自动生成
        saveOrUpdateRiskReport({
          risk_id: route.params.riskId,
          content: localeReportContent.value,
          auto_generate: false,
        });
      } else { // 点击自动生成
        saveOrUpdateRiskReport({
          risk_id: route.params.riskId,
          content: localeReportContent.value,
          auto_generate: true,
        });
      }
    } else { // 人工编辑的单子
      if (quillEditFlag.value) { // 人工编辑
        saveOrUpdateRiskReport({
          risk_id: route.params.riskId,
          content: localeReportContent.value,
          auto_generate: false,
        });
      } else { // 自动生成
        saveOrUpdateRiskReport({
          risk_id: route.params.riskId,
          content: localeReportContent.value,
          auto_generate: isAuto,
        });
      }
    }


    saveReportDialogRef.value?.hide();
    closeDialog();
  };
  const closeDialog = () => {
    // 停止轮询
    stopPolling();
    isShowEditEventReport.value = false;
    quillEditFlag.value = false;
  };
  const reportEnabledTeps = () => <div>
        <span>{t('该审计风险所属策略未启用事件调查报告自动生成功能，请编辑 ')}</span>
        <span onClick={handleTostrategyId}  style="color: #4d93fa;cursor: pointer;">{`${strategyList.value.find(item => item.value === props.strategyId)?.label}(${props.strategyId})`}</span>
        <span>{t(' 启用此功能')}</span>
        </div>;
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
  });
  const handleTostrategyId = () => {
    router.push({
      name: 'strategyList',
      query: {
        strategy_id: props.strategyId,
      },
    });
  };
  // 组件卸载时清理轮询
  onBeforeUnmount(() => {
    stopPolling();
  });

</script>

<style lang="postcss" scoped>
.edit-event-report-content {
  padding: 28px 40px;
  background-color: #f5f7fa;

  .edit-event-report-editor {
    background-color: #fff;
  }
}
</style>
