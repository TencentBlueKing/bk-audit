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
  <bk-sideslider
    v-model:isShow="isShow"
    background-color="#f5f7fa"
    :before-close="handleCancel"
    :esc-close="false"
    :quick-close="false"
    render-directive="if"
    :title="t('新建关联事件')"
    :width="800">
    <edit
      ref="editRef"
      :event-data="eventData"
      @add-success="handleAddSuccess" />
    <template #footer>
      <div class="foot-button">
        <bk-button
          theme="primary"
          @click="handleSubmit">
          {{ t('提交') }}
        </bk-button>
        <bk-button @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import Event from '@model/risk/risk';
  import StrategyInfo from '@model/risk/strategy-info';

  import edit from './edit.vue';

  interface Exposes{
    show(): void,
  }
  interface Props {
    eventData: Event & StrategyInfo
  }
  interface Emits{
    (e: 'addSuccess',): void;
  }
  defineProps<Props>();

  const emits = defineEmits<Emits>();
  const isShow = ref(false);
  const { t } = useI18n();
  const editRef = ref();
  // 取消
  const handleCancel = async (): Promise<boolean> => new Promise((resolve) => {
    InfoBox({
      title: t('确认取消当前操作?'),
      content: t('已填写的内容将会丢失，请谨慎操作！'),
      cancelText: t('取消'),
      confirmText: t('确认'),
      onConfirm() {
        isShow.value = false;
        resolve(true);
      },
      onCancel() {
        resolve(false);
      },
    });
  });
  // 提交
  const handleSubmit = () => {
    editRef.value?.submit();
  };
  const handleAddSuccess = () => {
    isShow.value = false;
    emits('addSuccess');
  };

  defineExpose<Exposes>({
    show() {
      isShow.value = true;
    },
  });
</script>

<style lang="postcss" scoped>
.foot-button {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}
</style>
