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
  <div ref="rootRef">
    <bk-form
      ref="formRef"
      :model="model"
      v-bind="$attrs">
      <slot />
    </bk-form>
  </div>
</template>
<script setup lang="ts">
  import {
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';

  interface Props {
    model?: Record<string, any>,
  }
  interface Exposes {
    validate: (fields?: string | Array<string>) => Promise<Record<string, any>>,
    clearValidate: (fields?: string | Array<string>) => void,
  }
  const props = defineProps<Props>();

  const rootRef = ref();
  const formRef = ref();

  let isUserEdit = false;

  watch(() => props.model, () => {
    if (isUserEdit) {
      window.changeConfirm = true;
    }
  }, {
    deep: true,
    immediate: true,
  });

  const handleUserEdit = () => {
    isUserEdit = true;
  };


  onMounted(() => {
    rootRef.value?.addEventListener('click', handleUserEdit);
  });

  onBeforeUnmount(() => {
    rootRef.value?.removeEventListener('click', handleUserEdit);
  });

  defineExpose<Exposes>({
    validate(fields) {
      return formRef.value.validate(fields)
        .catch((error: Error) => {
          rootRef.value.querySelector('.bk-form-item.is-error').scrollIntoView();
          return Promise.reject(error);
        });
    },
    clearValidate(fields) {
      return formRef.value.clearValidate(fields);
    },
  });
</script>

<style scoped lang="postcss">
/* f统一设置form中label字号 */
:deep(.bk-form-label) {
  font-size: 12px;
}
</style>
