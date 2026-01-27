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
  <smart-action
    class="create-strategy-page"
    :offset-target="getSmartActionOffsetTarget">
    <div
      v-if="isShowTips"
      class="event-tips">
      <audit-icon
        class="info-fill-icon"
        type="info-fill" />
      <span class="info-fill-text">{{ t('当前策略尚未产生风险单，暂时无法预览报告的实际内容，您可以选择等待策略产生风险单后再启用该功能，或立即启用无需使用预览功能') }}</span>
    </div>
    <div class="event-box">
      <div class="event-title">
        <span class="event-title-text">{{ t('事件调查报告') }}</span>
        <bk-switcher
          v-model="isEnvent"
          class="event-switcher"
          theme="primary"
          @change="handleSwitcher" />
        <div class="event-title-desc">
          <audit-icon
            class="title-fill-icon"
            type="info-fill" />
          <span class="info-fill-dec">{{ t('启用后，审计策略产生的风险工单将新增事件调查报告内容，便于非技术人员理解风险详情') }}</span>
        </div>
      </div>
      <div class="is-auto-reports">
        <div class="auto-reports-content">
          <bk-checkbox
            v-model="isAutoGetReports"
            :disabled="!isEnvent"
            size="small">
            {{ t('自动生成报告') }}
          </bk-checkbox>
          <div class="auto-reports-desc">
            <audit-icon
              class="title-fill-icon"
              type="info-fill" />
            <span
              class="info-fill-text"
              style="color: #979ba5;">{{ t('勾选后，风险单产生时将自动生成事件调查报告，建议策略正式上线后再开启，避免调试阶段消耗过多 AI Token，调试期间可在风险单中手动创建报告')
              }}</span>
          </div>
        </div>
      </div>
      <div class="event-editor">
        <div class="event-editor-title">
          {{ t('事件调查报告模版') }}
        </div>
        <div class="editor-box">
          <ai-editor
            ref="aiEditorRef"
            :disabled="!isEnvent"
            :event-info-data="eventInfoData"
            :risk-lisks="riskLisks"
            @is-has-content="handleHasContent" />
        </div>
      </div>
      <div
        v-if="isEnvent && riskLisks.length > 0"
        class="risks-select">
        <div class="risks-select-content">
          <bk-select
            v-model="selectedValue"
            class="risks-bk-select"
            :prefix="t('审计风险工单')">
            <bk-option
              v-for="(item, index) in riskLisks"
              :id="item?.risk_id"
              :key="index"
              :name="`${item?.title}(${item?.risk_id})`" />
          </bk-select>
          <bk-button
            v-bk-tooltips="{
              disabled: !(!hasEditorContent || selectedValue === ''),
              content: previewTooltips,
            }"
            class="ml8"
            :disabled="!hasEditorContent || selectedValue === ''"
            outline
            theme="primary"
            @click="handlePreview">
            {{ t('报告预览') }}
          </bk-button>
          <div class="risks-select-desc">
            <audit-icon
              class="info-fill"
              type="info-fill" />
            <span class="select-tip-text">{{ t('关联审计风险工单，用于预览报告渲染效果') }}</span>
          </div>
        </div>
      </div>
    </div>
    <template #action>
      <div class="action-button">
        <bk-button @click="handlePrevious">
          {{ t('上一步') }}
        </bk-button>
        <bk-button
          class="ml8"
          theme="primary"
          @click="handleNext">
          {{ t(isEnvent ? '下一步' : '跳过') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </div>
    </template>
  </smart-action>
  <preview-report
    ref="previewReportRef"
    v-model:visible="showPreview"
    :risk-id="selectedValue" />
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import AiEditor from './ai-editor/index.vue';
  import PreviewReport from './preview-report.vue';

  import { formatDate } from '@/utils/assist/timestamp-conversion';

  interface IFormData {
    processor_groups: Array<number>,
    notice_groups: Array<number>,
    report_enabled: boolean,
    report_config: Record<string, any>,
    report_auto_render: boolean,
  }

  interface riskItem {
    risk_id: string,
    title: string,
    strategy_id: number,
    created_at: string,
  }
  interface aiVariables {
    name: string,
    prompt_template: string,
  }

  interface Props {
    editData: StrategyModel;
    select?: any[]; // 从父组件传递的 formData.configs.select
  }
  interface Emits {
    (e: 'previousStep', step: number): void;
    (e: 'nextStep', step: number, params: IFormData): void;
    (e: 'submitData'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    select: () => [],
  });
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const isEnvent = ref(false);
  const isAutoGetReports = ref(false);
  const showPreview = ref(false);
  const aiEditorRef = ref();
  const previewReportRef = ref();
  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');
  const selectedValue = ref('');
  const riskLisks = ref<Array<riskItem>>([]);
  const editorContent = ref('');
  const reportInfo = ref({ // 报告信息
    enabled: false,
    config: {},
  });
  // 从 editData 或 select prop 中获取 expectedResultList (step1 中的 configs.select)
  // 优先使用 select prop（创建模式），否则使用 editData.configs.select（编辑模式）
  const eventInfoData = computed(() => {
    const data = props.select && props.select.length > 0
      ? props.select
      : (props.editData?.configs?.select || []);
    return data;
  });
  const handleSwitcher = (value: boolean) => {
    isEnvent.value = value;
    console.log('handleSwitcher', value);
    if (!value) {
      isAutoGetReports.value = false;
      aiEditorRef.value?.clearContent();
    }
  };
  // 是否显示提示
  const isShowTips = ref(false);
  // 定期检查编辑器内容变化
  let contentCheckInterval: ReturnType<typeof setInterval> | null = null;

  const startContentCheck = () => {
    if (contentCheckInterval) return;
    contentCheckInterval = setInterval(() => {
      if (aiEditorRef.value) {
        try {
          const content = aiEditorRef.value.getContent();
          editorContent.value = content || '';
        } catch {
          editorContent.value = '';
        }
      }
    }, 300);
  };
  // 检查编辑器是否有内容
  const hasEditorContent = ref(false);
  const handleHasContent = (hasContent: boolean) => {
    hasEditorContent.value = hasContent;
  };

  // 构建报告配置
  const buildReportConfig = () => {
    const frontendContent = aiEditorRef.value.getQuillContent();
    const template = aiEditorRef?.value.getContentVal();

    // 处理 template：将 AI Agent 块替换为模板变量
    let templateContent = template;

    // 使用 DOMParser 解析 HTML
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${templateContent}</div>`, 'text/html');
    const container = doc.body.firstElementChild as HTMLElement;

    if (container) {
      // 先收集所有需要替换的节点信息（避免在遍历时修改 DOM 导致的问题）
      const aiAgentNodes: Array<{ node: HTMLElement; name: string }> = [];
      const nodes = container.querySelectorAll('.ql-ai-agent');

      nodes.forEach((node) => {
        const htmlNode = node as HTMLElement;
        const name = htmlNode.getAttribute('data-name') || '';
        if (name) {
          aiAgentNodes.push({ node: htmlNode, name });
        }
      });

      // 从后往前替换，避免索引问题
      for (let i = aiAgentNodes.length - 1; i >= 0; i--) {
        const { node, name } = aiAgentNodes[i];
        // 创建模板变量文本节点
        const templateVar = doc.createTextNode(`{{ ai.${name} }}`);
        // 替换整个节点（包括所有子元素）
        if (node.parentNode) {
          node.parentNode.replaceChild(templateVar, node);
        }
      }

      // 清理可能残留的 AI Agent 相关元素（以防万一）
      const selectors = ['.ai-agent-block', '.ai-agent-content', '.ai-agent-actions', '.ai-agent-label', '.ai-agent-prompt'];
      selectors.forEach((selector) => {
        const elements = container.querySelectorAll(selector);
        elements.forEach((element) => {
          if (element.parentNode) {
            element.parentNode.removeChild(element);
          }
        });
      });

      // 获取处理后的 HTML 内容（移除包装的 div）
      templateContent = container.innerHTML;
    }

    const aiVariables = aiEditorRef.value.getAiLists().map((item: aiVariables) => ({
      name: item.name,
      prompt_template: item.prompt_template,
    }));
    return {
      frontend_template: frontendContent,
      template: templateContent,
      ai_variables: aiVariables,
    };
  };
  const previewTooltips = computed(() => {
    // 当编辑器有内容且选中了风险工单时，不显示提示
    if (hasEditorContent.value && selectedValue.value !== '') {
      return '';
    }

    // 当编辑器有内容但是没有选中风险工单时，提示 请选择审计风险工单
    if (hasEditorContent.value && selectedValue.value === '') {
      return t('请选择审计风险工单');
    }

    // 当编辑器没有内容但是选中了风险工单时，提示 请填写报告内容
    if (!hasEditorContent.value && selectedValue.value !== '') {
      return t('请填写报告内容');
    }

    // 当编辑器没有内容且没有选中风险工单时，提示 请填写报告内容并选择审计风险工单
    return t('请填写报告内容并选择审计风险工单');
  });


  const stopContentCheck = () => {
    if (contentCheckInterval) {
      clearInterval(contentCheckInterval);
      contentCheckInterval = null;
    }
  };

  // 当编辑器引用可用时开始检查
  nextTick(() => {
    if (aiEditorRef.value) {
      startContentCheck();
    }
  });


  const route = useRoute();
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const handlePrevious = () => {
    emits('previousStep', 2);
  };
  const handleNext = () => {
    reportInfo.value.enabled = isEnvent.value;
    if (isEnvent.value) {
      reportInfo.value.config = buildReportConfig();
    }
    emits('nextStep', 4, {
      processor_groups: [],
      notice_groups: [],
      report_enabled: reportInfo.value.enabled,
      report_config: reportInfo.value.config,
      report_auto_render: isAutoGetReports.value,
    });
  };
  const handleCancel = () => {
    console.log('handleCancel');
  };

  const handlePreview = () => {
    showPreview.value = true;
    nextTick(() => {
      previewReportRef.value?.setContent({
        risk_id: selectedValue.value,
        report_config: buildReportConfig(),
      });
    });
  };
  // 获取风险简要列表
  const {
    run: fetchRisksBriefList,
  } = useRequest(StrategyManageService.fetchRisksBrief, {
    defaultValue: [],
    onSuccess(data) {
      // 如果返回的数据包含 results 字段，则使用 results，否则直接使用 data
      riskLisks.value = data?.results || data || [];
      isShowTips.value = !(riskLisks.value.length > 0);
    },
  });


  onMounted(() => {
    if (isEditMode || isCloneMode) {
      isEnvent.value = props.editData.report_enabled;
      isAutoGetReports.value = props.editData.report_auto_render;
      const strategyId = route.params.id;
      // 默认当前时间往前6个月（6个月前到现在）
      const now = dayjs();
      const sixMonthsAgo = dayjs().subtract(6, 'month');
      const params = {
        strategy_id: String(strategyId),
        start_time: formatDate(sixMonthsAgo.valueOf()),
        end_time: formatDate(now.valueOf()),
      };
      fetchRisksBriefList(params);
      if (props.editData.report_enabled && props.editData.report_config?.frontend_template) {
        // 使用 nextTick 确保编辑器已经准备好
        nextTick(() => {
          if (aiEditorRef.value) {
            aiEditorRef.value.setQuillContent(props.editData.report_config.frontend_template);
          }
        });
      }
    }
  });

  onBeforeUnmount(() => {
    stopContentCheck();
  });

</script>

<style lang="postcss" scoped>
.create-strategy-page {
  .event-tips {
    display: flex;
    align-items: center;
    height: 32px;
    background: #f0f5ff;
    border: 1px solid #a3c5fd;
    border-radius: 2px;

    .info-fill-icon {
      margin-left: 9px;
      font-size: 14px;
      color: #3a84ff;
    }

  }

  .event-box {
    height: auto;
    margin-top: 16px;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 4px 0 #1919290d;

    .event-title {
      display: flex;
      height: 50px;
      padding: 0 16px;
      font-size: 14px;
      font-weight: 700;
      line-height: 22px;
      letter-spacing: 0;
      color: #4d4f56;
      border-bottom: 1px solid #e8e8e8;
      align-items: center;

      .event-title-text {
        margin-right: 13px;
      }

      .event-switcher {
        margin-right: 13px;
      }

      .event-title-desc {
        display: flex;
        align-items: center;
        flex: 1;

        .info-fill-dec {
          margin-left: 5px;
          font-size: 12px;
          font-weight: 500;
          line-height: 20px;
          letter-spacing: 0;
          color: #4d4f56;
        }
      }
    }

    .is-auto-reports {
      padding: 20px 16px 0;

      .auto-reports-content {
        display: flex;
        align-items: flex-start;
        font-size: 12px;
        line-height: 20px;
        letter-spacing: 0;
        color: #4d4f56;

        .auto-reports-desc {
          display: flex;
          align-items: center;
          margin-left: 8px;
          flex: 1;
        }
      }
    }

    .event-editor {
      padding: 16px;

      .event-editor-title {
        font-size: 12px;
        line-height: 20px;
        letter-spacing: 0;
        color: #4d4f56;
      }
    }

    .editor-box {
      margin-top: 5px;
    }

    .risks-select {
      padding: 0 16px 20px;

      .risks-select-content {
        display: flex;
        align-items: center;

        .risks-bk-select {
          width: 520px;
        }

        .risks-select-desc {
          display: flex;
          align-items: center;
          margin-left: 8px;
          flex: 1;
        }
      }
    }
  }

  .info-fill {
    font-size: 14px;
    color: #c4c6cc;
  }

  .select-tip-text {
    font-size: 12px;
    letter-spacing: 0;
    color: #4d4f56;
  }

  .action-button {
    margin-top: 20px;
  }
}

.title-fill-icon {
  margin-left: 0;
  font-size: 14px;
  color: #979ba5;
}

.info-fill-text {
  margin-left: 5px;
  font-size: 12px;
  letter-spacing: 0;
  color: #4d4f56;
}
</style>
