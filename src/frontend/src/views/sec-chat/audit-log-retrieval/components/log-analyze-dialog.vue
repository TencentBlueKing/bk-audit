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
  <teleport to=".sec-chat-main">
    <div
      v-if="isShow"
      class="log-analyze-overlay"
      @click.self="handleClose">
      <div class="log-analyze-modal">
        <div class="modal-header">
          <h4 class="modal-title">
            智能分析
          </h4>
          <div
            class="modal-close"
            @click="handleClose">
            <audit-icon type="close" />
          </div>
        </div>

        <div class="log-analyze-dialog-content">
          <div class="subtitle">
            基于当前 <span class="highlight">{{ formatNumber(totalHit) }}</span> 条日志，为您推荐以下分析报告：
          </div>

          <div
            class="report-card recommend"
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
  </teleport>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';

  import useMessage from '@hooks/use-message';

  import reportIcon from '@images/Union.svg';

  import type { RetrievalFilterCondition } from '../../types';

  const props = withDefaults(defineProps<{
    modelValue?: boolean;
    totalHit?: number;
    conditions?: RetrievalFilterCondition[];
  }>(), {
    modelValue: false,
    totalHit: 0,
    conditions: () => [],
  });

  const emit = defineEmits<{
    'update:modelValue': [value: boolean];
    select: [payload: { type: 'recommend' | 'custom'; title: string; prompt?: string }];
  }>();

  const { messageSuccess } = useMessage();

  const isShow = ref(false);
  const isCustomExpanded = ref(false);
  const customRequirement = ref('');

  watch(() => props.modelValue, (val) => {
    isShow.value = val;
    if (val) {
      isCustomExpanded.value = false;
      customRequirement.value = '';
    }
  });

  watch(isShow, (val) => {
    if (val !== props.modelValue) {
      emit('update:modelValue', val);
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
    isShow.value = false;
  };

  const handleRecommend = () => {
    emit('select', {
      type: 'recommend',
      title: '智能分析报告',
    });
    messageSuccess('已选择智能分析报告');
    handleClose();
  };

  const handleCustomAnalyze = () => {
    const prompt = customRequirement.value.trim();
    if (!prompt) return;
    emit('select', {
      type: 'custom',
      title: '自定义分析',
      prompt,
    });
    messageSuccess('已提交自定义分析');
    handleClose();
  };
</script>

<style lang="postcss" scoped>
  .log-analyze-overlay {
    position: absolute;
    inset: 0;
    z-index: 100;
    display: flex;
    padding: 24px;
    overflow: auto;
    background: rgb(0 0 0 / 40%);
    box-sizing: border-box;
    align-items: center;
    justify-content: center;
  }

  .log-analyze-modal {
    width: 680px;
    max-width: 100%;
    margin: auto;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 4px 12px rgb(0 0 0 / 15%);
  }

  .modal-header {
    display: flex;
    height: 52px;
    padding: 0 24px;
    align-items: center;
    justify-content: space-between;
    box-sizing: border-box;

    .modal-title {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      line-height: 28px;
      color: #313238;
    }

    .modal-close {
      display: flex;
      width: 32px;
      height: 32px;
      margin-right: -8px;
      font-size: 18px;
      color: #979ba5;
      cursor: pointer;
      border-radius: 2px;
      align-items: center;
      justify-content: center;

      &:hover {
        color: #63656e;
        background: #eaebf0;
      }
    }
  }

  .log-analyze-dialog-content {
    padding: 0 24px 24px;
    font-size: 12px;
    color: #63656e;

    .subtitle {
      margin-bottom: 16px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;

      .highlight {
        margin: 0 2px;
        font-weight: 700;
        color: #3a84ff;
      }
    }

    .report-card {
      position: relative;
      padding: 16px 20px;
      margin-bottom: 12px;
      overflow: hidden;
      cursor: pointer;
      background: #fff;
      border: 1px solid #dcdee5;
      border-radius: 2px;
      transition: all .2s;

      &:hover {
        background: linear-gradient(90deg, #eaf3ff 0%, #fafdff 100%);
        border-color: #3a84ff;
        box-shadow: 0 2px 4px 0 rgb(0 0 0 / 10%);
      }

      &.recommend {
        border-color: #c4d9ff;
      }

      .report-title {
        margin-bottom: 8px;
        font-size: 14px;
        font-weight: 700;
        color: #313238;
      }

      .report-desc {
        padding-right: 60px;
        line-height: 18px;
        color: #979ba5;
      }

      .report-icon {
        position: absolute;
        top: 50%;
        right: 20px;
        width: 60px;
        height: 60px;
        pointer-events: none;
        transform: translateY(-50%);
      }
    }

    .divider-wrapper {
      display: flex;
      margin: 24px 0 16px;
      align-items: center;

      .divider-line {
        height: 1px;
        background-color: #dcdee5;
        flex: 1;
      }

      .divider-text {
        padding: 0 16px;
        color: #979ba5;
      }
    }

    .custom-analysis {
      .custom-header {
        display: flex;
        cursor: pointer;
        user-select: none;
        align-items: center;

        .collapse-icon {
          margin-right: 6px;
          font-size: 16px;
          color: #979ba5;
        }

        .custom-title {
          font-size: 14px;
          font-weight: 700;
          color: #313238;
        }

        .custom-desc {
          color: #979ba5;
        }
      }

      .custom-content {
        margin-top: 16px;

        .custom-input-wrapper {
          position: relative;
          display: flex;
          width: 100%;
          border: 1px solid #dcdee5;
          border-radius: 2px;
          transition: all .2s;
          align-items: flex-end;

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
              min-height: 80px;
              padding-right: 80px;
              padding-bottom: 40px;
              background: transparent;
              border: none;
              resize: none;
            }
          }

          .custom-analysis-btn {
            position: absolute;
            right: 8px;
            bottom: 8px;
            height: 32px;
            min-width: 64px;
          }
        }
      }
    }
  }
</style>
