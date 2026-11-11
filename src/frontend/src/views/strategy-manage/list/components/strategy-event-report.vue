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
      <section class="report-section">
        <h4 class="report-section-title">
          {{ t('基本信息') }}
        </h4>
        <div class="report-fields">
          <render-info-item :label="t('事件调查报告')">
            <span class="report-status-tag">{{ t('已启用') }}</span>
          </render-info-item>
          <render-info-item :label="t('自动生成报告')">
            {{ strategyData.report_auto_render ? t('已开启') : t('已关闭') }}
          </render-info-item>
          <render-info-item :label="t('更新人')">
            {{ strategyData.updated_by || '--' }}
          </render-info-item>
          <render-info-item :label="t('更新时间')">
            {{ strategyData.updated_at || '--' }}
          </render-info-item>
        </div>
      </section>
      <div class="report-divider" />
      <section class="report-section">
        <h4 class="report-section-title">
          {{ t('报告内容') }}
        </h4>
        <div class="strategy-event-report-content">
          <ai-editor
            ref="aiEditorRef"
            disabled
            :event-data="eventData"
            :event-info-data="eventInfoData"
            :risk-lisks="riskLisks" />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyModel from '@model/strategy/strategy';

  import AiEditor from '../../strategy-create/components/event-report/ai-editor/index.vue';

  import RenderInfoItem from './render-info-item.vue';

  interface Props {
    data: StrategyModel;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const strategyData = ref<StrategyModel>(props.data);
  const aiEditorRef = ref<InstanceType<typeof AiEditor> | null>(null);

  const riskLisks = ref<Array<{ risk_id: string; title: string; strategy_id: number; created_at: string }>>([]);

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

  const eventInfoData = computed(() => (strategyData.value as any)?.configs?.select || []);

  const syncEditorContent = () => {
    nextTick(() => {
      const frontendTemplate = (strategyData.value as any)?.report_config?.frontend_template || '';
      if (frontendTemplate && aiEditorRef.value) {
        aiEditorRef.value.setQuillContent(frontendTemplate);
      }
    });
  };

  watch(
    () => props.data,
    (data) => {
      if (!data?.strategy_id) return;
      strategyData.value = data;
      syncEditorContent();
    },
    { immediate: true },
  );

</script>

<style scoped lang="postcss">
.strategy-event-report-wrapper {
  display: flex;
  width: 100%;
  min-height: 400px;
  justify-content: center;
}

.strategy-event-report {
  width: 100%;
}

.report-section-title {
  margin: 0 0 var(--bk-theme-space-12);
  font-size: var(--bk-theme-font-size-base);
  font-weight: var(--bk-theme-font-weight-bold);
  line-height: var(--bk-theme-line-height-base);
  color: var(--bk-theme-text-strong);
}

.report-fields {
  padding-left: var(--bk-theme-space-32);
}

.report-fields :deep(.render-info-item) {
  display: flex;
  gap: var(--bk-theme-space-8);
  align-items: flex-start;
  min-height: 32px;
  padding: var(--bk-theme-space-6) 0;
  font-size: var(--bk-theme-font-size-sm);
  font-weight: var(--bk-theme-font-weight-regular);
  line-height: var(--bk-theme-line-height-sm);
}

.report-fields :deep(.info-label) {
  flex: 0 0 84px;
  width: 84px;
  min-width: 84px;
  padding: 0;
  color: var(--bk-theme-text-default);
  text-align: right;
}

.report-fields :deep(.info-value) {
  padding-left: 0;
  overflow: visible;
  color: var(--bk-theme-text-strong);
  text-overflow: unset;
}

.report-status-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 var(--bk-theme-space-8);
  font-size: var(--bk-theme-font-size-sm);
  line-height: var(--bk-theme-line-height-sm);
  color: var(--bk-theme-color-success-1);
  background: var(--bk-theme-color-success-6);
  border-radius: var(--bk-theme-control-radius);
}

.report-divider {
  height: 0;
  margin: var(--bk-theme-space-24) 0;
  border: none;
  border-top: 1px solid var(--bk-theme-border-default);
}

.strategy-event-report-title {
  margin-bottom: var(--bk-theme-space-12);
  font-size: 14px;
  font-weight: 500;
  color: var(--bk-theme-text-strong);
}

.strategy-event-report-content {
  width: 100%;
  min-height: 405px;
  overflow: hidden;
  background: var(--bk-theme-surface-page);
  border: none;
  border-radius: var(--bk-theme-control-radius);
}

.strategy-event-report-body {
  min-height: 200px;
  padding: var(--bk-theme-space-8) 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--bk-theme-text-strong);
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
.strategy-event-report-content :deep(.rich-text-editor-container),
.strategy-event-report-content :deep(.editor-wrapper),
.strategy-event-report-content :deep(.quill-editor),
.strategy-event-report-content :deep(.ql-container.ql-snow),
.strategy-event-report-content :deep(.ql-editor) {
  width: 100%;
  min-height: 405px;
  background: transparent;
  border: none;
  box-shadow: none;
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
