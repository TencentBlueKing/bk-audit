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
  <div class="strategy-event-report-wrapper">
    <bk-exception
      v-if="!strategyData.report_enabled"
      class="strategy-event-report-empty"
      scene="part"
      type="empty">
      {{ t('当前策略未启用事件调查报告') }}
    </bk-exception>
    <div
      v-else
      class="strategy-event-report">
      <render-info-block class="strategy-event-block">
        <render-info-item :label="t('事件调查报告状态')">
          {{ strategyData.report_enabled ? t('已开启') : t('已关闭') }}
        </render-info-item>
        <render-info-item
          :label="t('自动生成报告')"
          style="padding-top: 10px;">
          {{ strategyData.report_auto_render ? t('已开启') : t('已关闭') }}
        </render-info-item>
        <render-info-item
          :label="t('更新人')"
          style="padding-top: 10px;">
          {{ strategyData.updated_by || '--' }}
        </render-info-item>
        <render-info-item
          :label="t('更新时间')"
          style="padding-top: 10px;">
          {{ strategyData.updated_at || '--' }}
        </render-info-item>
      </render-info-block>


      <div class="strategy-event-report-content">
        <ai-editor
          ref="aiEditorRef"
          disabled
          :event-data="eventData"
          :event-info-data="eventInfoData"
          :risk-lisks="riskLisks" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import AiEditor from '../../strategy-create/components/event-report/ai-editor/index.vue';

  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';

  interface Props {
    data: StrategyModel;
    activeTab?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    activeTab: '',
  });
  const { t } = useI18n();

  // 本地策略数据，优先使用接口返回的最新数据
  const strategyData = ref<StrategyModel>(props.data);
  const aiEditorRef = ref<InstanceType<typeof AiEditor> | null>(null);

  // 是否已加载过数据，防止重复调用（使用 strategy_id 作为 key）
  const loadedStrategyIds = ref<Set<number>>(new Set());
  // 当前正在加载的 strategy_id，防止并发请求
  const loadingStrategyId = ref<number | null>(null);

  // 风险列表（用于 ai-editor）
  const riskLisks = ref<Array<{ risk_id: string; title: string; strategy_id: number; created_at: string }>>([]);

  // 事件数据（用于 ai-editor）
  const eventData = computed(() => {
    if (!strategyData.value) {
      return [];
    }
    return [
      ...(strategyData.value.event_basic_field_configs || []),
      ...(strategyData.value.event_data_field_configs || []),
      ...(strategyData.value.event_evidence_field_configs || []),
    ];
  });

  // 事件信息数据（用于 ai-editor）
  const eventInfoData = computed(() => (strategyData.value as any)?.configs?.select || []);

  // 获取策略详情
  const {
    run: fetchStrategyInfo,
  } = useRequest(StrategyManageService.fetchStrategyInfo, {
    defaultValue: new StrategyModel(),
    onSuccess(data) {
      strategyData.value = data;
      if (loadingStrategyId.value) {
        loadedStrategyIds.value.add(loadingStrategyId.value);
      }
      loadingStrategyId.value = null;
      // 设置编辑器内容
      nextTick(() => {
        const frontendTemplate = (data as any)?.report_config?.frontend_template || '';
        if (frontendTemplate && aiEditorRef.value) {
          aiEditorRef.value.setQuillContent(frontendTemplate);
        }
      });
    },
    onFinally() {
      // 请求完成后清除 loading 状态
      if (loadingStrategyId.value) {
        // 如果请求失败，也需要清除 loading 状态，但不添加到已加载列表
        loadingStrategyId.value = null;
      }
    },
  });

  // 当切换到"事件调查报告"标签页时获取策略详情
  watch(
    () => [props.activeTab, props.data?.strategy_id] as [string, number | undefined],
    ([newTab, strategyId]) => {
      if (newTab === 'eventReport' && strategyId && typeof strategyId === 'number' && strategyId > 0) {
        // 防止重复调用：如果已经加载过或正在加载，则跳过
        if (loadedStrategyIds.value.has(strategyId) || loadingStrategyId.value === strategyId) {
          return;
        }
        loadingStrategyId.value = strategyId;
        fetchStrategyInfo({
          strategy_id: strategyId,
        });
      }
    },
    { immediate: true },
  );

  // 初始化时设置编辑器内容
  watch(
    () => strategyData.value,
    () => {
      nextTick(() => {
        const frontendTemplate = (strategyData.value as any)?.report_config?.frontend_template || '';
        if (frontendTemplate && aiEditorRef.value) {
          aiEditorRef.value.setQuillContent(frontendTemplate);
        }
      });
    },
    { immediate: true },
  );

</script>

<style scoped lang="postcss">
.strategy-event-block {
  :deep(.info-label) {
    min-width: 110px;
  }
}

.strategy-event-report-wrapper {
  display: flex;
  width: 100%;
  min-height: 400px;
  justify-content: center;
}

.strategy-event-report {
  width: 100%;
  padding: 16px 24px;
}

.strategy-event-report-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #313238;
}

.strategy-event-report-content {
  width: 100%;
  min-height: 400px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 2px;
  box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);
}

.strategy-event-report-body {
  min-height: 200px;
  padding: 8px 0;
  font-size: 14px;
  line-height: 1.6;
  color: #313238;
}

.strategy-event-report-empty {
  display: flex;
  width: 100%;
  min-height: 400px;
  align-items: center;
  justify-content: center;
}

:deep(.bk-exception) {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* 编辑器宽度设置 */
.strategy-event-report-content :deep(.rich-text-editor-container) {
  width: 100%;
}

.strategy-event-report-content :deep(.editor-wrapper) {
  width: 100%;
}

.strategy-event-report-content :deep(.quill-editor) {
  width: 100%;
}

/* 移除禁用遮罩层的背景颜色 */
:deep(.editor-wrapper-disabled) {
  background-color: transparent !important;
}

/* 隐藏工具栏 */
:deep(.ql-toolbar) {
  display: none !important;
}

/* 隐藏AI智能体的编辑和删除按钮 */
:deep(.ai-agent-edit),
:deep(.ai-agent-delete) {
  display: none !important;
}

:deep(.ai-agent-actions) {
  display: none !important;
}
</style>

