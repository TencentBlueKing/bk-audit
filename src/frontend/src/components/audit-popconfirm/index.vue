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
  <div
    ref="rootRef"
    v-bind="$attrs"
    class="audit-popconfirm">
    <slot />
  </div>
  <div
    ref="popRef"
    style="width: 280px; padding: 15px 10px;">
    <div style="font-size: 16px; line-height: 20px; color: #313238;">
      {{ title }}
    </div>
    <div style="margin-top: 10px; font-size: 12px; color: #63656e;">
      <slot name="contentHeader">
        {{ content }}
      </slot>
    </div>
    <div style="margin-top: 16px;">
      <slot name="content" />
    </div>
    <div style="margin-top: 16px; text-align: right;">
      <bk-button
        class="mr8"
        :loading="isConfirmLoading"
        size="small"
        theme="primary"
        @click="handleConfirm">
        {{ t(confirmText) }}
      </bk-button>
      <bk-button
        :loading="isCancelLoading? isConfirmLoading: false"
        size="small"
        @click="handleCancel">
        {{ t(cancelText) }}
      </bk-button>
    </div>
  </div>
</template>
<script setup lang="ts">
  import tippy, {
    type Instance,
    type Placement,
    type SingleTarget,
  } from 'tippy.js';
  import {
    onBeforeUnmount,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Exposes{
    hide(): void,
  }
  interface Emits{
    (e:'hide'): void,
  }
  interface Props {
    title: string,
    content: string,
    placement?: Placement,
    confirmHandler: () => Promise<any>,
    cancelHandler?: () => Promise<any>,
    zIndex?: number,
    hideOnClick?: boolean,
    confirmText?: string,
    cancelText?: string,
    confirmAutoHide?: boolean,
    isCancelLoading?:boolean
  }
  const props = withDefaults(defineProps<Props>(), {
    placement: 'top',
    cancelHandler: () => Promise.resolve(),
    zIndex: 999999,
    hideOnClick: true,
    confirmText: '确认',
    cancelText: '取消(No)',
    confirmAutoHide: true,
  });

  const emits = defineEmits<Emits>();


  let tippyIns: Instance;

  const { t } = useI18n();

  const rootRef = ref();
  const popRef = ref();
  const isConfirmLoading = ref(false);

  const handleConfirm = () => {
    isConfirmLoading.value = true;
    Promise.resolve()
      .then(() => props.confirmHandler())
      .then(() => {
        if (props.confirmAutoHide) {
          tippyIns.hide();
          emits('hide');
        }
      })
      .finally(() => {
        isConfirmLoading.value = false;
      });
  };

  const handleCancel = () => {
    Promise.resolve()
      .then(() => props.cancelHandler())
      .then(() => {
        tippyIns.hide();
        emits('hide');
      });
  };

  onMounted(() => {
    const tippyTarget = rootRef.value.children[0];
    if (tippyTarget) {
      tippyIns = tippy(tippyTarget as SingleTarget, {
        content: popRef.value,
        placement: props.placement,
        appendTo: () => document.body,
        theme: 'light',
        maxWidth: 'none',
        trigger: 'click',
        interactive: true,
        arrow: true,
        offset: [0, 8],
        zIndex: props.zIndex,
        hideOnClick: props.hideOnClick,
        onTrigger(instance, event) {
          event.stopPropagation();
        },
      });
    }
  });

  onBeforeUnmount(() => {
    tippyIns.hide();
    tippyIns.unmount();
    tippyIns.destroy();
  });

  defineExpose<Exposes>({
    hide() {
      tippyIns.hide();
    },
  });
</script>
<style lang="postcss">
  .audit-popconfirm {
    display: inline-block;
    line-height: 1;
  }
</style>
