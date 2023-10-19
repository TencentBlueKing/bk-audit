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
    class="strategy-create-plan-select"
    :class="{'is-errored':isError}">
    <bk-select
      v-model="localValue"
      behavior="simplicity"
      class="bk-select"
      :disabled="disabled"
      filterable
      :placeholder="t('请选择方案')"
      style="font-weight: normal"
      @change="onControlIdChange">
      <bk-option
        v-for="(item) in controlList"
        :key="item.control_id"
        :label="item.control_type_id === 'BKM'
          ?`${item.control_name} - V${item.versions[0].control_version}`
          :`${item.control_name} - V${(isEditMode || isCloneMode) ? curVersion : item.versions[0].control_version}`"
        :value="item.control_id">
        <span v-if="item.control_type_id === 'BKM'">
          {{ `${item.control_name} - V${item.versions[0].control_version}` }}
        </span>
        <span v-else>
          {{ `${item.control_name} - V${item.versions[0].control_version}` }}
        </span>
        <p
          v-if="item.control_type_id === 'BKM'"
          class="inset-tip">
          {{ t('内置') }}
        </p>
      </bk-option>
    </bk-select>
    <span
      v-if="isError"
      v-bk-tooltips="{content: t('必填项'), placement: 'top'}"
      class="err-tip">
      <audit-icon
        type="alert" />
    </span>
    <slot />
  </div>
</template>

<script setup lang='ts'>
  import {
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  interface Emits{
    (e:'change', id: string): void
  }
  interface Expose {
    getValue: () => void,
  }
  interface Props{
    disabled: boolean,
    defaultValue: string,
    controlList: Array<{
      control_type_id: string;
      control_id: string;
      control_name: string;
      versions: Array<{
        control_id: string;
        control_version: number
      }>
    }>
    curVersion?: number, // 当前版本
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const route = useRoute();

  const localValue = ref();
  const isError = ref(false);

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const onControlIdChange = (id: string) => {
    emits('change', id);
  };

  watch(() => props.defaultValue, (data) => {
    localValue.value = data;
  }, {
    immediate: true,
  });

  defineExpose<Expose>({
    getValue() {
      if (!localValue.value) {
        isError.value = true;
        return Promise.reject(new Error('必填'));
      }
      isError.value = false;
      return Promise.resolve();
    },
  });
</script>
<style lang="postcss" scoped>
.strategy-create-plan-select{
  position: relative;

  .err-tip{
    position: absolute;
    top:27%;
    right: 30px;
    font-size: 16px;
    line-height: 1;
    color: #ea3636;
  }
}

.inset-tip{
  position: absolute;
  top: 50%;
  right: 24px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: normal;
  color: #3A84FF;
  background: #EDF4FF;
  border-radius: 2px;
  transform: translateY(-50%);
}
</style>
