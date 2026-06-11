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
  <bk-dialog
    v-model:is-show="isShow"
    footer-align="center"
    :quick-close="false"
    :title="t('插入表格')"
    width="420">
    <bk-form
      class="insert-table-form"
      form-type="vertical"
      :label-width="80">
      <bk-form-item :label="t('行数')">
        <bk-input
          v-model="rowInput"
          :max="20"
          :min="2"
          type="number" />
      </bk-form-item>
      <bk-form-item :label="t('列数')">
        <bk-input
          v-model="colInput"
          :max="10"
          :min="1"
          type="number" />
      </bk-form-item>
      <p class="insert-table-tip">
        {{ t('首行将作为表头，行数包含表头') }}
      </p>
    </bk-form>
    <template #footer>
      <bk-button
        theme="primary"
        @click="handleConfirm">
        {{ t('确认') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Emits {
    (e: 'confirm', payload: { rows: number; cols: number }): void;
  }

  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const isShow = ref(false);
  const rowInput = ref('4');
  const colInput = ref('3');

  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

  const show = () => {
    rowInput.value = '4';
    colInput.value = '3';
    isShow.value = true;
  };

  const hide = () => {
    isShow.value = false;
  };

  const handleCancel = () => {
    hide();
  };

  const handleConfirm = () => {
    emit('confirm', {
      rows: clamp(Number(rowInput.value) || 4, 2, 20),
      cols: clamp(Number(colInput.value) || 3, 1, 10),
    });
    hide();
  };

  defineExpose({
    show,
    hide,
  });
</script>
<style lang="postcss" scoped>
.insert-table-form {
  padding-top: 8px;
}

.insert-table-tip {
  margin: 0;
  font-size: 12px;
  color: #979ba5;
}
</style>
