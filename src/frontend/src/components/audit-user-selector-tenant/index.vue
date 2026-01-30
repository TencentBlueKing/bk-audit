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
    :api-base-url="apiBaseUrl"
    :disabled="disabled"
    :multiple="multiple"
    :tenant-id="tenantId"
    @blur="handleBlur"
    @change="handleChange" />
</template>

<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';

  import BkUserSelector from '@blueking/bk-user-selector';

  import '@blueking/bk-user-selector/vue3/vue3.css';

  interface Props {
    modelValue: Array<string> | string;
    multiple?: boolean;
    disabled?: boolean;
  }

  interface Emits {
    (e: 'update:modelValue', value: Array<string> | string): void;
    (e: 'change', value: Array<string> | string): void;
    (e: 'blur'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: () => [],
    multiple: true,
    disabled: false,
  });

  const emit = defineEmits<Emits>();
  const userSelectorRef = ref();
  const localValue = ref<Props['modelValue']>([]);

  // Mock 数据配置 - 当后端接口未返回 tenant_config 时使用
  // TODO: 后端接口就绪后，移除 mock 数据
  const MOCK_TENANT_CONFIG = {
    BK_TENANT_ID: '',
    BK_USER_WEB_APIGW_URL: '',
  };

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
  // apiBaseUrl 由后端配置中的 BK_API_URL_TMPL 与 BK_USER_WEB_APIGW_URL 以及网关环境拼接而成
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
    // 使用 mock 数据
    return MOCK_TENANT_CONFIG.BK_TENANT_ID;
  });

  const handleChange = (value: Array<string> | string) => {
    emit('update:modelValue', value);
    emit('change', value);
  };

  const handleBlur = () => {
    emit('blur');
  };

  watch(
    () => props.modelValue,
    (modelValue: Props['modelValue']) => {
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
    width: 100%;
  }
</style>
