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
  <bk-user-selector
    v-bind="$attrs"
    ref="userSelectorRef"
    v-model="localValue"
    :allow-create="allowCreate"
    :api-base-url="apiBaseUrl"
    :auto-focus="autoFocus"
    :disabled="isDisabled"
    :multiple="multiple"
    :render-tag="renderTag"
    :tenant-id="tenantId"
    :user-group="userGroup"
    :user-group-name="userGroupName"
    @blur="handleBlur"
    @update:model-value="handleValueChange" />
</template>

<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';

  import useRequest from '@hooks/use-request';

  import BkUserSelector from '@blueking/bk-user-selector';

  import '@blueking/bk-user-selector/vue3/vue3.css';
  import MetaManageService from '@/domain/service/meta-manage';

  interface Props {
    modelValue: Array<string> | string;
    allowCreate?: boolean;
    multiple?: boolean;
    isDisabled?: boolean;
    autoFocus?: boolean;
  }

  interface Emits {
    (e: 'update:modelValue', value: Array<string> | string): void;
    (e: 'change', value: Array<string> | string): void;
    (e: 'blur'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: () => [],
    allowCreate: false,
    multiple: true,
    isDisabled: false,
    autoFocus: true,
  });

  const emit = defineEmits<Emits>();
  const userSelectorRef = ref();
  const localValue = ref<Props['modelValue']>([]);
  // 用户组数据，从接口获取变量列表
  const userGroup = ref<{ id: string; name: string; }[]>([]);
  useRequest(MetaManageService.fetchVariableList, {
    manual: true,
    defaultValue: [],
    onSuccess: (value) => {
      userGroup.value = value.map(item => ({
        id: item.value,
        name: `${item.value}(${item.label})`,
      }));
    },
  });


  const userGroupName = ref('可使用变量');


  // 自定义标签渲染
  const renderTag = (createElement:any, userInfo:any) => createElement('span', { class: 'custom-tag' }, [
    createElement('img', { src: userInfo.logo, class: 'avatar' }),
    userInfo.display_name || userInfo.name,
  ]);

  // 从sessionStorage中获取配置
  const getConfig = () => {
    try {
      const configStr = sessionStorage.getItem('BK_AUDIT_CONFIG');
      if (configStr) {
        return JSON.parse(configStr);
      }
    } catch (e) {
      console.error('Failed to parse BK_AUDIT_CONFIG:', e);
    }
    return null;
  };

  // 计算apiBaseUrl
  const apiBaseUrl = computed(() => {
    const config = getConfig();
    if (config?.tenant_config?.BK_USER_WEB_APIGW_URL) {
      return config?.tenant_config?.BK_USER_WEB_APIGW_URL;
    }
    return '';
  });

  // 获取租户ID
  const tenantId = computed(() => {
    const config = getConfig();
    if (config?.tenant_config?.BK_TENANT_ID) {
      return config.tenant_config.BK_TENANT_ID;
    }
    return '';
  });

  const handleValueChange = (v: string | string[]) => {
    emit('update:modelValue', v);
    emit('change', v);
  };

  const handleBlur = () => {
    emit('blur');
  };

  watch(
    () => props.modelValue,
    (modelValue: Props['modelValue']) => {
      console.log(modelValue, 'model');
      localValue.value = modelValue;
    },
    {
      immediate: true,
      deep: true,
    },
  );
</script>

<style lang="postcss">
  .bk-user-selector {
    position: relative;
    z-index: 1;
    width: 100%;

    .angle-up {
      display: none !important;
    }
  }
</style>
