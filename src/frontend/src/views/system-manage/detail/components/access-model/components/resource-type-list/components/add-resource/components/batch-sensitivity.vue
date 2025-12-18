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
  <div style="display: flex;">
    <h3>{{ t('批量编辑敏感等级') }}</h3>
    <span style="margin-left: 5px; font-size: 12px; line-height: 20px; color: #979ba5;">
      <slot name="subTitle" />
    </span>
  </div>
  <audit-form
    ref="formRef"
    form-type="vertical"
    :model="formData">
    <bk-form-item
      :label="t('敏感等级')"
      label-width="160"
      property="sensitivity"
      required>
      <bk-select
        v-model="formData.sensitivity"
        class="batch-sensitivity"
        filterable
        :input-search="false"
        :placeholder="t('请选择敏感等级')"
        :popover-options="{ boundary: 'parent' }"
        :search-placeholder="t('请输入关键字')">
        <bk-option
          v-for="(item, index) in sensitivityList"
          :key="index"
          :label="item.label"
          :value="item.value" />
      </bk-select>
    </bk-form-item>
  </audit-form>
  <div style="margin-top: 8px; font-size: 14px; line-height: 22px; color: #3a84ff; text-align: right;">
    <bk-button
      class="mr8"
      size="small"
      theme="primary"
      @click="handleSubmitBatch">
      {{ t('确定') }}
    </bk-button>
    <bk-button
      size="small"
      @click="handleCancelBatch">
      {{ t('取消') }}
    </bk-button>
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    sensitivityList: Array<{
      label: string;
      value: number;
    }>
  }

  interface Emits {
    (e: 'updateSensitivity', value: string): void
    (e: 'cancel'): void
  }

  defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const formRef = ref();

  const formData  = ref<{
    sensitivity: string,
  }>({
    sensitivity: '',
  });

  const handleSubmitBatch = () => {
    formRef.value.validate().then(() => {
      emit('updateSensitivity', formData.value.sensitivity);
    });
  };

  const handleCancelBatch = () => {
    formData.value.sensitivity = '';
    emit('cancel');
  };
</script>
