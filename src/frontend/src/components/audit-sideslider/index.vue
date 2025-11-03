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
    v-bind="$attrs"
    :before-close="beforeCloseCallback"
    :is-show="isShow"
    :title="t($attrs.title as string)"
    @update:is-show="handleUpdateShow">
    <template
      v-if="showHeaderSlot"
      #header>
      <slot name="header" />
    </template>
    <template #default>
      <div v-if="isShow">
        <slot />
      </div>
    </template>
    <template
      v-if="showFooter"
      #footer>
      <template v-if="showFooterSlot">
        <slot name="footer" />
      </template>
      <template v-else>
        <div>
          <bk-button
            class="mr8"
            :loading="isLoading"
            style="width: 102px;"
            theme="primary"
            @click="handleConfirm">
            {{ t(confirmText) }}
          </bk-button>
          <bk-button
            style="min-width: 64px;"
            @click="handleCancle">
            {{ t(cancelText) }}
          </bk-button>
        </div>
      </template>
    </template>
  </bk-sideslider>
</template>
<script lang="ts">
  export default {
    inheritAttrs: false,
  };
</script>
<script setup lang="ts">
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useModelProvider from '@hooks/use-model-provider';

  import { changeConfirm } from '@utils/assist';

  interface Props {
    isShow: boolean,
    showFooter?: boolean,
    confirmText?: string,
    cancelText?: string,
    showHeaderSlot?: boolean,
    showFooterSlot?: boolean,
  }
  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    showFooter: true,
    confirmText: '提交',
    cancelText: '取消',
    showFooterSlot: false,
  });
  const emit = defineEmits<Emits>();
  interface Emits{
    (e: 'update:isShow', isShow: boolean):void
  }
  interface Exposes {
    handleConfirm: () => void,
    handleCancle: () => void,
  }
  const { t } = useI18n();
  const isLoading = ref(false);
  let pageChangeConfirm: boolean | 'popover' = false;
  watch(() => props.isShow, (isShow) => {
    if (isShow) {
      pageChangeConfirm = window.changeConfirm;
      window.changeConfirm = 'popover';
    }
  }, {
    immediate: true,
  });

  const getModelProvier = useModelProvider();

  const beforeCloseCallback = () => changeConfirm();
  const close = () => {
    window.changeConfirm = pageChangeConfirm;
    emit('update:isShow', false);
  };

  const handleUpdateShow = () => {
    close();
  };

  // 确定
  const handleConfirm = () => {
    isLoading.value = true;
    const { submit } = getModelProvier();
    submit()
      .then(() => {
        close();
      })
      .finally(() => {
        isLoading.value = false;
      });
  };
  // 取消
  const handleCancle = () => {
    const { cancel } = getModelProvier();
    cancel()
      .then(() => {
        close();
      });
  };
  defineExpose<Exposes>({
    handleConfirm() {
      handleConfirm();
    },
    handleCancle() {
      handleCancle();
    },
  });
</script>
