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
  <div class="">
    <bk-loading
      class="form-item-common environment-type"
      :loading="isGlobalsLoading">
      <div>
        <span class="type-lable">
          {{ t('物理环境') }}
        </span>
        <div
          class="pr8"
          style="height: 32px;padding-right: 8px;border-right: 1px solid rgb(0 0 0 / 16%);">
          <span
            v-for="item in physics"
            :key="item.id"
            class="type-item ml8"
            :class="{
              disabled: readonly,
              active: item.id===active,
            }"
            @click="hanldeType(item.id, 'physics')">
            <img
              class="type-image"
              :src="getAssetsFile(`${item.image}.svg`)">
            <span class="ml8">{{ item.name }}</span>
          </span>
        </div>
      </div>
      <div
        class="ml8">
        <span class="type-lable">
          {{ t('容器环境') }}
        </span>
        <div
          style="height: 32px;">
          <span
            v-for="item in globalsData.bcs_log_type"
            :key="item.id"
            class="type-item ml8"
            :class="{
              active: item.id===active,
              disabled: readonly,
            }"
            @click="hanldeType(item.id, 'container')">
            <img
              class="type-image"
              :src="getAssetsFile(`${item.id}.svg`)">
            <span class="ml8">{{ t(item.name) }}</span>
          </span>
        </div>
      </div>
    </bk-loading>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import GlobalsModel from '@model/meta/globals';

  import useRequest from '@hooks/use-request';

  import getAssetsFile from '@utils/getAssetsFile';

  interface Props {
    collectorEnvironment: string,
    readonly: boolean
  }
  interface Emits {
    (e: 'update:collectorEnvironment', value: string): void,
    (e: 'change', type: string): void;
  }
  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const physics = [
    {
      id: 'linux',
      name: 'linux',
      image: 'linux',
    },
  ];
  // eslint-disable-next-line vue/no-setup-props-destructure
  const active = ref(props.collectorEnvironment);
  // 全局数据
  const {
    loading: isGlobalsLoading,
    data: globalsData,
  } = useRequest(MetaManageService.fetchGlobals, {
    defaultValue: new GlobalsModel(),
    manual: true,
  });
  const hanldeType = (value: string, type: string) => {
    if (props.readonly) {
      return;
    }
    active.value = value;
    emits('update:collectorEnvironment', value);
    emits('change', type);
  };
  watch(() => props.collectorEnvironment, (collectorEnvironment) => {
    active.value = collectorEnvironment;
  }, {
    deep: true,
  });
</script>
<style lang="postcss">
.environment-type {
  display: flex;

  .type-lable {
    color: #63656e;
  }

  .type-item:first-child {
    margin-left: 0;
  }

  .type-item {
    display: inline-block;
    display: inline-flex;
    width: 100px;
    height: 32px;
    padding: 5px;
    color: #313238;
    cursor: pointer;
    background: #fff;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    align-items: center;

    .type-image {
      width: 20px;
      height: 20px;
    }
  }

  .active {
    color: #3a84ff;
    background: #e1ecff;
    border: 1px solid #3a84ff;
  }

  .active:hover {
    color: #3a84ff;
    border: 1px solid #3a84ff;
  }

  .disabled:not(.active) {
    color: #c4c6cc;
    cursor: not-allowed;
    border-color: #dcdee5;
  }

  .type-item:not(.disabled):hover {
    color: #3a84ff;
    border: 1px solid #3a84ff;
  }
}
</style>
