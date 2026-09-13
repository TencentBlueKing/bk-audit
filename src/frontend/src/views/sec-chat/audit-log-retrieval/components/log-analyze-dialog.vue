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
  <teleport
    v-if="isShow"
    to="#sec-chat-overlay-root">
    <div class="log-analyze-overlay">
      <div
        class="log-analyze-dialog-sizer"
        @click.self="handleOverlayClose">
        <div class="log-analyze-modal">
          <div
            class="modal-close"
            @click="handleClose">
            <audit-icon type="close" />
          </div>
          <div class="modal-header">
            <h4 class="modal-title">
              智能分析
            </h4>
          </div>

          <div class="log-analyze-dialog-content">
            <div class="subtitle">
              基于当前 <span class="highlight">{{ formatNumber(totalHit) }}</span> 条日志，为您推荐以下分析报告：
            </div>

            <div
              class="report-card recommend"
              :class="{ 'is-disabled': submitting }"
              @click="handleRecommend">
              <div class="report-info">
                <div class="report-title">
                  智能分析报告
                </div>
                <div class="report-desc">
                  {{ recommendDesc }}
                </div>
              </div>
              <img
                class="report-icon"
                :src="reportIcon">
            </div>

            <div class="divider-wrapper">
              <div class="divider-line" />
              <div class="divider-text">
                以上报告不满足需求？
              </div>
              <div class="divider-line" />
            </div>

            <div class="custom-analysis">
              <div
                class="custom-header"
                @click="isCustomExpanded = !isCustomExpanded">
                <audit-icon
                  class="collapse-icon"
                  :type="isCustomExpanded ? 'angle-fill-down' : 'angle-fill-rignt'" />
                <span class="custom-title">自定义分析</span>
                <span class="custom-desc">（输入任意分析需求，AI为您定制报告）</span>
              </div>
              <div
                v-show="isCustomExpanded"
                class="custom-content">
                <div class="custom-input-wrapper">
                  <bk-input
                    v-model="customRequirement"
                    class="custom-input"
                    placeholder="输入你想分析的内容，例如：分析张三在英雄联盟业务的资产转移报告"
                    :rows="3"
                    type="textarea" />
                  <bk-button
                    class="custom-analysis-btn"
                    :disabled="submitting"
                    :loading="submitting"
                    size="small"
                    theme="primary"
                    @click.stop="handleCustomAnalyze">
                    分析
                  </bk-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script lang="ts" setup>
  import { computed, onDeactivated, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useMessage from '@hooks/use-message';

  import reportIcon from '@images/analyze-recommend-icon.svg';

  import type { RetrievalFilterCondition } from '../../types';

  const props = withDefaults(defineProps<{
    modelValue?: boolean;
    totalHit?: number;
    conditions?: RetrievalFilterCondition[];
    submitting?: boolean;
  }>(), {
    modelValue: false,
    totalHit: 0,
    conditions: () => [],
    submitting: false,
  });

  const emit = defineEmits<{
    'update:modelValue': [value: boolean];
    select: [payload: { type: 'recommend' | 'custom'; title: string; prompt?: string }];
  }>();

  const { messageWarn } = useMessage();
  const { t } = useI18n();

  const isCustomExpanded = ref(false);
  const customRequirement = ref('');
  /** 父级用 v-if 挂载时 modelValue 已是 true，不能再等无 immediate 的 watch */
  const isShow = computed({
    get: () => props.modelValue,
    set: (val: boolean) => emit('update:modelValue', val),
  });

  watch(() => props.modelValue, (val) => {
    if (val && !props.submitting) {
      isCustomExpanded.value = false;
      customRequirement.value = '';
    }
  });

  const operatorName = computed(() => (
    props.conditions.find(item => item.field === '操作人')?.value || '目标对象'
  ));

  const recommendDesc = computed(() => (
    `根据 ${operatorName.value} 的行为链分析、风险关联分析、意图判断、关联人员挖掘、建议下一步调查、风险影响评估`
  ));

  const formatNumber = (num: number) => num.toLocaleString('en-US');

  const handleClose = () => {
    if (props.submitting) return;
    isShow.value = false;
  };

  const handleOverlayClose = () => {
    handleClose();
  };

  // keep-alive 场景下失活时，防止 teleport 留下遮罩/DOM 影响其他页面点击
  onDeactivated(() => {
    isShow.value = false;
    isCustomExpanded.value = false;
    customRequirement.value = '';
  });

  const handleRecommend = () => {
    if (props.submitting) return;
    emit('select', {
      type: 'recommend',
      title: t('智能分析报告'),
    });
    isShow.value = false;
  };

  const handleCustomAnalyze = () => {
    if (props.submitting) return;
    const prompt = customRequirement.value.trim();
    if (!prompt) {
      messageWarn(t('请输入分析要求'));
      return;
    }
    emit('select', {
      type: 'custom',
      title: t('智能分析报告'),
      prompt,
    });
    isShow.value = false;
  };
</script>

<style lang="postcss" scoped>
  .log-analyze-overlay {
    position: absolute;
    inset: 0;
    z-index: 100;
    overflow: auto;
    pointer-events: auto;
    background: rgb(0 0 0 / 40%);
    box-sizing: border-box;
  }

  .log-analyze-dialog-sizer {
    display: flex;
    width: max-content;
    min-width: 100%;
    min-height: 100%;
    padding: 24px;
    box-sizing: border-box;
    align-items: center;
    justify-content: center;
  }

  .log-analyze-modal {
    position: relative;
    width: 680px;
    min-width: 680px;
    flex-shrink: 0;
    margin: auto;
    background: var(--audit-neutral-bg-04);
    border-radius: var(--audit-radius-container);
    box-shadow: var(--audit-shadow-dialog);
    box-sizing: border-box;
  }

  .modal-header {
    display: flex;
    padding: var(--audit-space-16) var(--audit-space-24) 0;
    align-items: center;
    box-sizing: border-box;

    .modal-title {
      margin: 0;
      font-size: var(--audit-font-size-xl);
      font-weight: var(--audit-font-weight-regular);
      line-height: var(--audit-line-height-xl);
      color: var(--audit-neutral-text-01);
    }
  }

  .modal-close {
    position: absolute;
    top: var(--audit-space-8);
    right: var(--audit-space-8);
    display: flex;
    width: 24px;
    height: 24px;
    font-size: var(--audit-font-size-base);
    color: var(--audit-neutral-text-03);
    cursor: pointer;
    border-radius: var(--audit-radius-control);
    align-items: center;
    justify-content: center;

    &:hover {
      color: var(--audit-neutral-text-02);
      background: var(--audit-neutral-border-02);
    }
  }

  .log-analyze-dialog-content {
    padding: 20px var(--audit-space-24) var(--audit-space-24);
    font-size: var(--audit-font-size-sm);
    color: var(--audit-neutral-text-02);

    .subtitle {
      margin-bottom: var(--audit-space-12);
      font-size: var(--audit-font-size-sm);
      line-height: var(--audit-line-height-sm);
      color: var(--audit-neutral-text-02);

      .highlight {
        margin: 0 2px;
        font-weight: var(--audit-font-weight-bold);
        color: var(--audit-brand-02);
      }
    }

    .report-card {
      position: relative;
      display: flex;
      min-height: 70px;
      padding: var(--audit-space-12) var(--audit-space-16);
      margin-bottom: 0;
      overflow: hidden;
      cursor: pointer;
      background: linear-gradient(90deg, #eaf3ff 0%, #fafdff 100%);
      border: 1px solid var(--audit-brand-04);
      border-radius: var(--audit-radius-container);
      transition: all .2s;
      flex-direction: column;
      justify-content: center;
      align-items: stretch;
      gap: var(--audit-space-4);
      box-sizing: border-box;

      &:hover {
        border-color: var(--audit-brand-02);
      }

      &.is-disabled {
        cursor: not-allowed;
        pointer-events: none;
        opacity: 0.6;
      }

      &.recommend {
        border-color: var(--audit-brand-04);
      }

      .report-info {
        position: relative;
        z-index: 1;
        min-width: 0;
      }

      .report-title {
        margin-bottom: 0;
        font-size: var(--audit-font-size-base);
        font-weight: var(--audit-font-weight-bold);
        line-height: var(--audit-line-height-base);
        color: var(--audit-neutral-text-01);
      }

      .report-desc {
        font-size: var(--audit-font-size-sm);
        line-height: var(--audit-line-height-sm);
        color: var(--audit-neutral-text-03);
        overflow-wrap: break-word;
        word-break: break-word;
      }

      .report-icon {
        position: absolute;
        top: 7px;
        right: 25px;
        z-index: 0;
        width: 72px;
        height: 72px;
        pointer-events: none;
        object-fit: none;
      }
    }

    .divider-wrapper {
      display: flex;
      margin: var(--audit-space-24) 0 var(--audit-space-16);
      align-items: center;

      .divider-line {
        height: 1px;
        background-color: #dcdee5;
        flex: 1;
      }

      .divider-text {
        padding: 0 var(--audit-space-16);
        font-size: var(--audit-font-size-sm);
        line-height: var(--audit-line-height-sm);
        color: var(--audit-neutral-text-02);
        white-space: nowrap;
      }
    }

    .custom-analysis {
      .custom-header {
        display: flex;
        min-width: 0;
        cursor: pointer;
        user-select: none;
        align-items: center;
        gap: var(--audit-space-8);

        .collapse-icon {
          display: inline-flex;
          width: 12px;
          height: 12px;
          font-size: 12px;
          line-height: 12px;
          color: var(--audit-neutral-text-03);
          flex-shrink: 0;
          align-items: center;
          justify-content: center;
        }

        .custom-title {
          font-size: var(--audit-font-size-base);
          font-weight: var(--audit-font-weight-bold);
          line-height: var(--audit-line-height-base);
          color: var(--audit-neutral-text-02);
          white-space: nowrap;
          flex-shrink: 0;
        }

        .custom-desc {
          min-width: 0;
          font-size: var(--audit-font-size-sm);
          line-height: var(--audit-line-height-sm);
          color: var(--audit-neutral-text-03);
          white-space: nowrap;
        }
      }

      .custom-content {
        margin-top: var(--audit-space-12);

        .custom-input-wrapper {
          position: relative;
          display: flex;
          width: 100%;
          height: 72px;
          border: 1px solid var(--audit-neutral-border-01);
          border-radius: var(--audit-radius-control);
          transition: all .2s;
          align-items: flex-end;
          box-sizing: border-box;

          &:focus-within {
            background: linear-gradient(white, white) padding-box,
              linear-gradient(90deg, #a469ff 0%, #1cc2fe 100%) border-box;
            border-color: transparent;
          }

          .custom-input {
            background: transparent;
            border: none;
            box-shadow: none;
            flex: 1;

            :deep(.bk-textarea) {
              min-height: 72px;
              height: 72px;
              padding: 4px 8px 32px;
              padding-right: 72px;
              background: transparent;
              border: none;
              resize: none;
              box-sizing: border-box;
            }
          }

          .custom-analysis-btn {
            position: absolute;
            right: 8px;
            bottom: 8px;
            height: 26px;
            min-width: 48px;
            padding: 3px 12px;
          }
        }
      }
    }
  }
</style>
