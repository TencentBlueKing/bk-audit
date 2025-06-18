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
  <bk-select
    ref="userSelectorRef"
    :allow-create="allowCreate"
    auto-focus
    class="audit-user-selector"
    :collapse-tags="collapseTags"
    :disabled="isDisabled"
    filterable
    :model-value="localValue"
    :multiple="multiple"
    multiple-mode="tag"
    :no-data-text="noDataText"
    :remote-method="remoteMethod"
    @blur="handleBlur"
    @change="handleChange"
    @focus="handleFocus">
    <bk-option
      v-for="(item) in filterData"
      :key="item.id"
      :label="`${item.username}(${item.display_name})`"
      :value="item.username" />
  </bk-select>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  interface Props {
    modelValue: Array<string> | string,
    allowCreate?: boolean,
    multiple?: boolean,
    collapseTags?: boolean,
    needRecord?:boolean,
    isDisabled?:boolean,
  }
  interface Option{
    display_name: string,
    username: string,
    id:number
  }
  interface Emits {
    (e: 'update:modelValue', value:Array<string>): void
    (e: 'change', value:Array<string>): void
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: () => [],
    allowCreate: false,
    multiple: true,
    collapseTags: true,
    isDisabled: false,
  });
  const emit = defineEmits<Emits>();
  const rememberList = ref<Array<Option>>([]);
  const { t } = useI18n();
  const userSelectorRef = ref();
  const noDataText = ref(t('请输入用户名'));
  const localValue = ref<Props['modelValue']>([]);
  const pageSize = 30;
  const filterData = computed(() => data.value.results
    .filter(item => item && item.username && item.id));

  const {
    data,
    run,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: {
      page: 1,
      page_size: pageSize,
      fuzzy_lookups: '',
    },
    defaultValue: {
      count: 0,
      results: [],
    },
    onSuccess: (data) => {
      if (data.results.length <= 0) {
        noDataText.value = t('找不到对应用户');
      }
    },
  });


  const recordList = (val: string) => {
    if (!val) return;
    const userValue = data.value.results.find(item => item.username === val) as Option;
    if (!userValue) return;
    const alreayExistUserValue = rememberList.value.find(item => item.username === val);
    if (!alreayExistUserValue) {
      if (rememberList.value.length >= 6) {
        rememberList.value.splice(rememberList.value.length - 1, 1);
      }
      rememberList.value.unshift(userValue);
    }
  };
  const rememberResult = () => {
    const string = sessionStorage.getItem('audit-userlist');
    if (string) {
      const ar = JSON.parse(string).filter((item: any) => item && typeof item === 'object' && !Array.isArray(item));
      data.value.results = ar;
      rememberList.value = ar;
    }
  };
  const remoteMethod = (value:string) => {
    if (!_.trim(value)) {
      // data.value.results = [];
      if (!props.multiple) {
        data.value.results = [];
      }
      return;
    }
    run({
      page: 1,
      page_size: pageSize,
      fuzzy_lookups: value,
    });
  };

  const handleChange = (value: []) => {
    emit('update:modelValue', value);
    emit('change', value);
    if (props.needRecord) {
      recordList(value[value.length - 1]);
    }
    if (props.multiple) {
      nextTick(() => {
        userSelectorRef.value.searchKey = '';
        userSelectorRef.value.customOptionName = '';
        userSelectorRef.value.curSearchValue = '';
      });
    }
  };
  // 获取焦点优先清掉数据
  const handleFocus = () => {
    noDataText.value = t('请输入用户名');
    data.value.results = [];
    if (props.needRecord) {
      rememberResult();
    }
  };
  const handleBlur = () => {
    sessionStorage.setItem('audit-userlist', JSON.stringify(rememberList.value));
  };

  watch(() => props.modelValue, (modelValue: Props['modelValue']) => {
    localValue.value = modelValue;
  }, {
    immediate: true,
    deep: true,
  });
</script>
<style lang="postcss">
  .audit-user-selector {
    position: relative;
    z-index: 1;
    width: 100%;

    .angle-up {
      display: none !important;
    }
  }
</style>
