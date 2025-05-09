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
              <div
                class="variable-input-content"
                :class="[variableInputActive ? 'active' : '']"
                @click.stop="(e) => handleClick(e, 'origin')">
                <ul class="list">
                  <template v-if="!variableInputActive">
                    <li
                      v-for="(item, index) in displayRiskTitle"
                      :key="index"
                      @click="handleClickLi(index)">
                      <span
                        :class="[item.isVariable ? 'is-variable' : '']">
                        {{ item.value }}
                      </span>
                    </li>
                  </template>
                  <li
                    v-else
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
              <bk-popover
                ref="variablePopRef"
                :component-event-delay="300"
                :is-show="isShow"
                :offset="8"
                placement="bottom-start"
                theme="light"
                trigger="manual"
                width="490">
                <template #content>
                  <variable-table
                    :select="select"
                    :strategy-id="editData.strategy_id"
                    @is-copy="handleCopy" />
                </template>
              </bk-popover>
            </bk-form-item>
          </template>
        </card-part-vue>
        <card-part-vue :title="t('事件信息')">
          <template #content>
            <event-info-table
              ref="eventRef"
              :data="editData"
              :select="select"
              :strategy-id="editData.strategy_id"
              :strategy-type="strategyType" />
          </template>
        </card-part-vue>
      </audit-form>
    </div>
    <template #action>
      <bk-button
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
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
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
  import _ from 'lodash';
  import { computed, nextTick, onActivated, onDeactivated, onUnmounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import CardPartVue from '../step1/components/card-part.vue';

  import EventInfoTable from './components/event-info-table.vue';
  import VariableTable from './components/variable-table.vue';

  interface IFormData {
    risk_title: string,
    event_evidence_field_configs:  StrategyFieldEvent['event_evidence_field_configs'],
    event_data_field_configs: StrategyFieldEvent['event_data_field_configs'],
    event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'],
  }

  interface Emits {
    (e: 'previousStep', step: number): void;
    (e: 'nextStep', step: number, params: IFormData): void;
    (e: 'showPreview'): void;
  }
  interface Props {
    editData: StrategyModel,
    select: Array<DatabaseTableFieldModel>,
    strategyType: string
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();

  const formRef = ref();
  const eventRef = ref();
  const inputRef = ref();
  const variablePopRef = ref();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const isShow = ref(false);
  const isCopy = ref(false);
  const riskTitleValue = ref('');
  const clickLiIndex = ref(-1);
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

  const handleCancel = () => {
    router.push({
      name: 'strategyList',
    });
  };

  const handleNext = () => {
    Promise.all([formRef.value.validate(), eventRef.value.getValue()]).then(() => {
      const params: IFormData = _.cloneDeep(Object.assign({}, formData.value, eventRef.value.getData()));
      // 处理event_basic_field_configs
      params.event_basic_field_configs = params.event_basic_field_configs.map((item) => {
        if (item.map_config) {
          if (!item.map_config.source_field && !item.map_config.target_value) {
            // eslint-disable-next-line no-param-reassign
            delete item.map_config;
          } else if (item.map_config.source_field && item.map_config.target_value) {
            // eslint-disable-next-line no-param-reassign
            item.map_config.source_field = undefined;
          }
        }
        return item;
      });
      emits('nextStep', 3, params);
    });
  };

  const handleClick = (e: Event, origin?: 'origin') => {
    // 点击输入框，如果是复制了参数，不关闭
    if (origin && !isCopy.value) {
      isShow.value = true;
      variableInputActive.value = true;
      if (displayRiskTitle.value.length) {
        riskTitleValue.value = displayRiskTitle.value.map(item => item.value).join('');
        formData.value.risk_title = '';
      }
      nextTick(() => {
        if (clickLiIndex.value !== -1) {
          // 设置光标位置为指定文字的前面
          inputRef.value?.setSelectionRange(clickLiIndex.value, clickLiIndex.value);
          clickLiIndex.value = -1;
        }
        inputRef.value?.focus();
      });
    }
    // 点击页面其他地方,且是打开状态，关闭pop
    if (!origin && isShow.value) {
      isShow.value = false;
      isCopy.value = false;
      variableInputActive.value = false;

      // 如果有值
      if (riskTitleValue.value) {
        // 赋值
        formData.value.risk_title += riskTitleValue.value;
        // 清空本次输入内容
        riskTitleValue.value = '';
      }
      formRef.value.validate('risk_title');
    }
  };

  const handleClickLi = (index: number) => {
    clickLiIndex.value =  index;
  };

  const getClipboardContent = async () => {
    try {
      const text = await navigator.clipboard.readText();
      // 如果输入有值
      if (riskTitleValue.value) {
        // 赋值
        formData.value.risk_title += riskTitleValue.value;
        // 清空本次输入内容
        riskTitleValue.value = '';
      } else {
        // 没有值，用最后一次复制内容
        formData.value.risk_title += text;
      }
    } catch (err) {
      console.error('Failed to read clipboard contents: ', err);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    // enter生成tag
    if (e.code === 'Enter') {
      // 失去焦点，关闭pop
      isShow.value = false;
      isCopy.value = false;
      variableInputActive.value = false;
      inputRef.value?.blur();
      getClipboardContent();
    }
    // 如果pop还是打开状态，input有值，删除input里面的值
    if (isShow.value && riskTitleValue.value) return;
    if (e.code === 'Backspace' && displayRiskTitle.value?.length) {
      // 顺序删除
      const displayRiskTitleArray = displayRiskTitle.value;
      displayRiskTitleArray.splice(displayRiskTitleArray.length - 1, 1);
      formData.value.risk_title = displayRiskTitleArray.map(item => item.value).join('');
    }
  };

  // 点击复制后，再点击input不关闭pop
  const handleCopy = () => {
    isCopy.value = true;
  };

  // 编辑
  watch(() => props.editData, (data) => {
    formData.value.risk_title = data.risk_title || '';
  }, {
    immediate: isEditMode || isCloneMode,
  });

  const displayRiskTitle = computed(() => {
    const riskTitleArr = formData.value.risk_title.match(/\{\{[^{}]*}}|./g);
    if (!riskTitleArr) return [];
    const resultArray = riskTitleArr.reduce<Array<{
      value: string,
      isVariable: boolean,
    }>>((acc, item) => {
      // 判断是否包含 {{}}
      if (item.startsWith('{{') && item.endsWith('}}')) {
        const variableParts = [
          ...Array.from(item).map(char => ({
            value: char,
            isVariable: true,
          })),
        ];
        return acc.concat(variableParts);
      }
      return acc.concat({ value: item, isVariable: false });
    }, []);
    return resultArray;
  });

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-main');

  onActivated(() => {
    window.addEventListener('click', handleClick);
  });

  onDeactivated(() => {
    isShow.value = false;
    isCopy.value = false;
    variableInputActive.value = false;
    window.removeEventListener('click', handleClick);
  });

  onUnmounted(() => {
    window.removeEventListener('click', handleClick);
  });

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

      /* max-width: 1280px; */
    }
  }

  .variable-input-content {
    min-height: 32px;
    padding-left: 5px;
    color: #63656e;
    cursor: pointer;
    border: 1px solid #c4c6cc;

    .placeholder {
      color: #c4c6cc;
    }

    .list {
      display: flex;
      max-width: 100%;
      flex-wrap: wrap;

      .is-variable {
        padding: 5px 0;
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

  .active {
    cursor: text;
    border-color: #3a84ff;
  }
}
</style>
