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
  <div class="bk-vision-component">
    <div class="component">
      <div class="lable">
        {{ props.config?.label }}
      </div>
      <div class="content">
        <audit-user-selector
          v-if="props.config?.type === 'userSelect'"
          v-model="newOperators"
          :placeholder="t('请输入人员')" />
        <bk-input
          v-if="props.config?.type === 'input'"
          v-model="inputVal" />
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    config: any;
  }
  const props = defineProps<Props>();
  const { t } = useI18n();
  console.log(props.config);

  const newOperators = ref([]);
  const inputVal = ref();

</script>

<style scoped lang="postcss">
.bk-vision-component {
  width: 100%;
  height: 100%;

  .component {
    .lable {
      padding-bottom: 5px;
      font-size: 12px;
      line-height: 20px;
      letter-spacing: 0;
      color: #4d4f56;
    }
  }
}
</style>
