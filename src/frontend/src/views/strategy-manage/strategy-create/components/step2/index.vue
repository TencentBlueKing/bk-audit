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
    <div class="create-strategy-main">
      <audit-form
        ref="formRef"
        class="strategt-form"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <card-part-vue :title="t('风险单信息')">
          <template #content>
            <bk-form-item
              class="is-required"
              :label="t('风险单标题')"
              label-width="160"
              property="risk_title">
              <bk-popover
                class="variable-popover"
                :component-event-delay="300"
                disable-outside-click
                :is-show="isShow"
                :offset="8"
                placement="bottom-start"
                theme="light"
                trigger="manual"
                width="490">
                <div
                  class="variable-input"
                  :class="[variableInputActive ? 'active' : '']">
                  <div
                    class="variable-input-content"
                    @click.stop="() => handleClick('origin')">
                    <ul class="list">
                      <li
                        v-for="(item, index) in displayRiskTitle"
                        :key="index">
                        <span
                          :class="[item.startsWith('{{') && item.endsWith('}}') ? 'is-variable' : '']">
                          {{ item }}
                        </span>
                      </li>
                      <li
                        v-if="variableInputActive"
                        class="list-item-input">
                        <input
                          ref="inputRef"
                          v-model.trim="riskTitleValue"
                          class="input"
                          type="text"
                          @keydown="handleKeyDown">
                      </li>
                    </ul>
                    <p
                      v-if="!variableInputActive && !formData.risk_title"
                      class="placeholder">
                      {{ t('请输入风险单名称') }}
                    </p>
                  </div>
                </div>
                <template #content>
                  <variable-table :strategy-id="data.strategy_id" />
                </template>
              </bk-popover>
            </bk-form-item>
          </template>
        </card-part-vue>
        <card-part-vue :title="t('事件信息')">
          <template #content>
            <event-info-table
              ref="eventRef"
              :data="data"
              :strategy-id="data.strategy_id" />
          </template>
        </card-part-vue>
      </audit-form>
    </div>
    <template #action>
      <bk-button
        class="w88"
        @click="handlePrevious">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        theme="primary"
        @click="handleNext">
        {{ t('下一步') }}
      </bk-button>
      <bk-button
        style="margin-left: 48px;"
        @click="handlePreview">
        {{ t('预览') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  import { computed, nextTick, onActivated, onDeactivated, onUnmounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyModel from '@model/strategy/strategy';
  import type { EventItem } from '@model/strategy/strategy-field-event';

  import CardPartVue from '../step1/components/card-part.vue';

  import EventInfoTable from './components/event-info-table.vue';
  import VariableTable from './components/variable-table.vue';

  interface IFormData {
    risk_title: string,
    event_evidence_field_configs: Array<EventItem>,
    event_data_field_configs: Array<EventItem>,
    event_basic_field_configs: Array<EventItem>,
  }

  interface Emits {
    (e: 'previousStep', step: number): void;
    (e: 'nextStep', step: number, params: IFormData): void;
    (e: 'showPreview'): void;
  }
  interface Props {
    data: StrategyModel
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const route = useRoute();
  const { t } = useI18n();

  const formRef = ref();
  const eventRef = ref();
  const inputRef = ref();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const isShow = ref(false);
  const riskTitleValue = ref('');
  const variableInputActive = ref(false);
  const formData = ref<IFormData>({
    risk_title: '',
    event_evidence_field_configs: [],
    event_data_field_configs: [],
    event_basic_field_configs: [],
  });

  const rules = {
    risk_title: [
      {
        validator: (value: string) => !!value,
        message: t('风险单标题不能为空'),
        trigger: 'change',
      },
    ],
  };

  const handlePreview = () => {
    // 预览前更新一次formData，用于查看重点信息
    const params: IFormData = Object.assign({}, formData.value, eventRef.value.getData());
    emits('nextStep', 2, params);
    emits('showPreview');
  };

  const handlePrevious = () => {
    emits('previousStep', 1);
  };

  const handleNext = () => {
    formRef.value.validate().then(() => {
      const params: IFormData = Object.assign({}, formData.value, eventRef.value.getData());
      emits('nextStep', 3, params);
    });
  };

  const handleClick = (type: string | Event) => {
    // 点击输入框，切换展示pop
    if (typeof type === 'string') {
      isShow.value = !isShow.value;
    }
    // 点击页面其他地方,且是打开状态，关闭pop
    if (typeof type !== 'string' && isShow.value) {
      isShow.value = false;
    }
    // active
    variableInputActive.value = !variableInputActive.value;
    // focus
    nextTick(() => {
      inputRef.value?.focus();
    });
    // 赋值
    if (riskTitleValue.value) {
      formData.value.risk_title += riskTitleValue.value;
    }
    // 清空本次输入内容
    riskTitleValue.value = '';
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.code === 'Backspace' && displayRiskTitle.value?.length) {
      // 顺序删除
      const displayRiskTitleArray = displayRiskTitle.value;
      displayRiskTitleArray.splice(displayRiskTitleArray.length - 1, 1);
      formData.value.risk_title = displayRiskTitleArray.join('');
    }
  };

  // 编辑
  watch(() => props.data, (data) => {
    formData.value.risk_title = data.risk_title;
  }, {
    immediate: isEditMode || isCloneMode,
  });

  onActivated(() => {
    window.addEventListener('click', handleClick);
  });

  onDeactivated(() => {
    window.removeEventListener('click', handleClick);
  });

  onUnmounted(() => {
    window.removeEventListener('click', handleClick);
  });

  const displayRiskTitle = computed(() => formData.value.risk_title.match(/\{\{[^}]+\}\}|./g));

  const getSmartActionOffsetTarget = () => document.querySelector('.bk-form-content');
</script>
<style lang="postcss" scoped>
.create-strategy-page {
  .create-strategy-main {
    display: flex;
    padding-top: 4px;
    padding-bottom: 1px;
    margin-bottom: 24px;

    .strategt-form {
      flex: 1;
      max-width: 1280px;
    }
  }

  .variable-input {
    color: #63656e;
    border: 1px solid #c4c6cc;

    .variable-input-content {
      min-height: 32px;
      padding-left: 5px;
      cursor: pointer;

      .placeholder {
        color: #c4c6cc;
      }

      .list {
        display: flex;

        .is-variable {
          padding: 5px;
          margin: 0 5px;
          background-color: #f2f3f6;
        }

        .list-item-input {
          flex: 1;

          .input {
            width: 100%;
            border: none;
            outline: none;
          }
        }
      }
    }
  }

  .active {
    cursor: text;
    border-color: #3a84ff;
  }
}
</style>
