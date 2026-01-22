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
    :quick-close="false">
    <div>
      {{ tips }}
    </div>
    <template #footer>
      <bk-button
        theme="primary"
        @click="handleSubmit(true)">
        {{ t('确认') }}
      </bk-button>
      <bk-button
        v-if="isShowButton"
        class="ml8"
        @click="handleSubmit(false)">
        {{ t('保持人工编辑') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
  <script lang="ts" setup>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface expose {
    show: (tips: string, isRegetVal: boolean) => void;
    hide: () => void;
  }
  interface Props {
    // status: string | undefined ;
  }
  interface Emits {
    (e: 'submit', isAuto: boolean): void;
  }
  defineProps<Props>();
  const emit = defineEmits<Emits>();
  const isShow = ref(false);
  const isShowButton = ref(false);
  const tips = ref('');
  const { t } = useI18n();

  const show = (tip: string, isShowButtonVal: boolean) => {
    isShowButton.value = isShowButtonVal;
    tips.value = tip;
    isShow.value = true;
  };
  const hide = () => {
    tips.value = '';
    isShow.value = false;
    isShowButton.value = false;
  };
  const handleCancel = () => {
    isShow.value = false;
  };
  const handleSubmit = (isAuto: boolean) => {
    // isShow.value = false;
    emit('submit', isAuto);
  };

  defineExpose<expose>({
    show,
    hide,
  });
  </script>
