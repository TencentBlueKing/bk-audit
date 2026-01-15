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
  </audit-sideslider>
</template>
<script setup lang="ts">
  import {
    Checkbox as BkCheckbox,
    InfoBox,
  } from 'bkui-vue';
  import {
    computed,
    h,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import RiskReportService from '@service/risk-report';

  import useRequest from '@hooks/use-request';

  import { QuillEditor } from '@vueup/vue-quill';

  interface Props {
    reportContent?: string;
    status: string | undefined;
    reportEnabled: boolean;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const route = useRoute();

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
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const autoGenerateChecked = ref(false); // checkbox 状态，默认 false 表示 auto_generate 为 false

  // 判断是否显示 checkbox：当 !quillEditFlag.value && (status === 'auto' || status === undefined) 时显示
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const showAutoGenerateCheckbox = computed(() => !quillEditFlag.value && (props.status === 'auto' || props.status === undefined));

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
    isPollingLoading.value = false; // 停止轮询时取消 loading
    currentTaskId = null;
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  };

  const handleGenerateReport = () => {
    const typeText = props.reportContent ? '重新生成' : '自动生成';
    const titleText = `确认${typeText}报告`;
    const subTitleText = `系统将根据最新的审计策略配置和风险信息${typeText}报告，
在自动生成之前，当前报告内容将被清空，请谨慎操作`;

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
    // 重置 checkbox 状态
    autoGenerateChecked.value = false;

    // 人工编辑后，则提示用户
    const subTitleText = quillEditFlag.value
      ? t('保存后，报告将被标记为「人工编辑」状态，后续有新事件触发，系统将自动更新该报表内容')
      : t('保存后，报告将被标记为「自动生成」状态，后续有新事件触发，系统将自动更新该报表内容');

    InfoBox({
      type: 'warning',
      title: t('确认保存更改?'),
      subTitle: () => {
        const children: any[] = [t(subTitleText)];

        // 如果满足条件，添加 checkbox
        if (showAutoGenerateCheckbox.value) {
          const checkboxDiv = h('div', {
            style: {
              marginTop: '12px',
              display: 'flex',
              alignItems: 'center',
            },
          }, [
            h(BkCheckbox, {
              modelValue: autoGenerateChecked.value,
              'onUpdate:modelValue': (val: boolean) => {
                autoGenerateChecked.value = val;
              },
            }),
            h('span', {
              style: {
                marginLeft: '8px',
                fontSize: '14px',
                color: '#4D4F56',
              },
            }, t('保持人工编辑')),
          ]);
          children.push(checkboxDiv);
        }

        return h('div', {
          style: {
            color: '#4D4F56',
            backgroundColor: '#f5f6fa',
            padding: '12px 16px',
            borderRadius: '2px',
            fontSize: '14px',
            textAlign: 'left',
          },
        }, children);
      },
      confirmText: t('确认'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        // 如果显示 checkbox 且未选中，则 auto_generate 为 true；否则根据 quillEditFlag 判断
        const autoGenerate = showAutoGenerateCheckbox.value
          ? !autoGenerateChecked.value
          : !quillEditFlag.value;

        saveOrUpdateRiskReport({
          risk_id: route.params.riskId,
          content: localeReportContent.value,
          auto_generate: autoGenerate,
        });
      },
      onClose() {
        closeDialog();
      },
    });
  };

  const closeDialog = () => {
    // 停止轮询
    stopPolling();
    isShowEditEventReport.value = false;
    quillEditFlag.value = false;
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
