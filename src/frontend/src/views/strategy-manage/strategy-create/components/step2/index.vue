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
                :offset="8"
                placement="bottom-start"
                theme="light"
                trigger="click"
                width="490">
                <bk-input
                  v-model.trim="formData.risk_title"
                  :placeholder="t('请输入风险单名称')"
                  style="width: 100%;" />
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
        theme="primary"
        @click="handlePrevious">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleNext">
        {{ t('下一步') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyModel from '@model/strategy/strategy';

  import CardPartVue from '../step1/components/card-part.vue';

  import EventInfoTable from './components/event-info-table.vue';
  import VariableTable from './components/variable-table.vue';

  interface Variable {
    field_name: string,
    description: string
    display_name: string;
    is_priority: boolean;
  }

  interface IFormData {
    risk_title: string,
    event_evidence_field_configs: Array<Variable>,
    event_data_field_configs: Array<Variable>,
    event_basic_field_configs: Array<Variable>,
  }

  interface Emits {
    (e: 'previousStep', step: number): void;
    (e: 'nextStep', step: number, params: IFormData): void;
  }
  interface Props {
    data: StrategyModel
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const formRef = ref();
  const eventRef = ref();

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

  const handlePrevious = () => {
    emits('previousStep', 1);
  };

  const handleNext = () => {
    formRef.value.validate().then(() => {
      const params: IFormData = Object.assign({}, formData.value, eventRef.value.getData());
      emits('nextStep', 3, params);
    });
  };

  // 编辑
  watch(() => props.data, (data) => {
    formData.value.risk_title = data.risk_title;
  }, {
    immediate: true,
  });

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
}
</style>
