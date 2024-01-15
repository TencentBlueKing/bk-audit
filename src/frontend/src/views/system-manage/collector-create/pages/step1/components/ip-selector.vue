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
  <div>
    <auth-component
      v-if="bizId && spaceTypeId === 'bkcc'"
      action-id="create_collection_v2_bk_log"
      :resource="bizId">
      <ip-selector
        :biz-id="bizId"
        :model-value="modelValue"
        :type="type"
        @change="handleIPChange" />
    </auth-component>
    <div v-else-if="bizId && spaceTypeId !== 'bkcc'">
      <span
        v-bk-tooltips="{
          content: t('非业务类型暂不支持采集主机数据')
        }">
        <bk-button
          disabled>
          <audit-icon
            class="mr8"
            type="add" />
          {{ t('添加目标') }}
        </bk-button>
      </span>
    </div>
    <ip-selector v-else />
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import IpSelector from '@components/ip-selector/index.vue';

  interface Props {
    modelValue: Array<any>,
    type?: string,
    bizId?: number,
    spaceTypeId: string,
  }
  interface IResult {
    type: string,
    value: Array<any>
  }
  withDefaults(defineProps<Props>(), {
    type: '',
    modelValue: () => [],
    bizId: undefined,
    spaceTypeId: undefined,
  });
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  interface Emits {
    (e: 'change', result: IResult): void
  }
  const handleIPChange = (result: IResult) => {
    emits('change', result);
  };
</script>
