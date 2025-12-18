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
  <div class="ip-selector">
    <div
      v-if="localValue.value.length > 0"
      class="ip-selector-result"
      @click="handleShowDialog">
      <audit-icon
        style="margin-right: 6px;"
        type="ip-result" />
      <span class="number">{{ localValue.value.length }}</span>
      <span>{{ resultText }}</span>
      <audit-icon
        style="margin-left: 6px; color: #3a84ff;"
        type="edit-fill" />
    </div>
    <span
      v-else
      v-bk-tooltips="{
        disabled: bizId,
        content: t('请选择业务')
      }">
      <bk-button
        :disabled="!bizId"
        @click="handleShowDialog">
        <audit-icon
          class="mr8"
          type="add" />
        {{ t('添加目标') }}
      </bk-button>
    </span>
    <template v-if="bizId">
      <selector-box
        v-model:is-show="isShow"
        :biz-id="bizId"
        :model-value="modelValue"
        :type="type"
        v-bind="$attrs"
        @change="handleChange" />
    </template>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    inject,
    type Ref,
    ref,
    shallowReactive,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import SelectorBox from './selector-box/index.vue';

  interface Props {
    modelValue?: Array<any>,
    type?: string,
    bizId?: number,
  }
  interface Emits {
    (e: 'change', result: IResult): void
  }

  const props = withDefaults(defineProps<Props>(), {
    type: '',
    modelValue: () => [],
    bizId: undefined,
  });
  const emits = defineEmits<Emits>();
  interface IResult {
    type: string,
    value: Array<any>
  }
  const { t } = useI18n();

  const typeTextMap = {
    TOPO: '个动态节点',
    INSTANCE: '台主机',
    SERVICE_TEMPLATE: '个服务模板',
    SET_TEMPLATE: '个集群模板',
  };

  const isShow = inject<Ref<boolean>>('isShow', ref(false));
  const localValue = shallowReactive<IResult>({
    type: '',
    value: [],
  });
  const resultText = computed(() => typeTextMap[localValue.type as keyof typeof typeTextMap]);

  watch(() => [props.type, props.modelValue], () => {
    if (props.type && props.modelValue) {
      localValue.type = props.type;
      localValue.value = props.modelValue;
    } else {
      localValue.type = '';
      localValue.value = [];
    }
  }, {
    immediate: true,
  });

  const handleShowDialog = () => {
    isShow.value = true;
  };

  const handleChange = (result: IResult) => {
    localValue.type = result.type;
    localValue.value = result.value;
    emits('change', result);
  };
</script>
<style lang="postcss">
  .ip-selector {
    display: inline-block;

    .ip-selector-result {
      display: flex;
      height: 32px;
      padding: 0 10px 0 5px;
      font-size: 12px;
      color: #7a7c85;
      cursor: pointer;
      border-radius: 2px;
      align-items: center;
      justify-content: center;

      &:hover {
        background: #f5f7fa;
      }
    }
  }
</style>
