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
  <span
    ref="spanRef"
    class="multiple-line-clamp-wrap max-line-clamp"
    :class="{'show-copy':isShowCopy}">
    {{ data || '--' }}
  </span>
  <span
    v-if="isShowCopy"
    v-bk-tooltips="t('复制所有')"
    class="copy-btn"
    @click.stop="()=>handleCopy(data)">
    <audit-icon type="copy" />
  </span>
</template>
<script setup lang="ts">
  import {
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { execCopy } from '@utils/assist';

  interface Props {
    data: string,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const spanRef = ref();
  const isShowCopy = ref(false);
  const checkHeight = () => {
    nextTick(() => {
      const el = spanRef.value;
      if (el.offsetHeight < el.scrollHeight) {
        isShowCopy.value = true;
      } else {
        isShowCopy.value = false;
      }
    });
  };
  const handleCopy = (val: any) => {
    execCopy(JSON.stringify(val), t('复制成功'));
  };

  watch(() => props.data, () => {
    checkHeight();
  }, {
    deep: true,
    immediate: true,
  });
</script>
<style lang="postcss">
  .show-copy {
    margin-right: 12px;
  }
</style>
