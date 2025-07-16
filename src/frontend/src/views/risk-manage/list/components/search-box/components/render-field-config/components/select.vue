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
  <bk-loading :loading="loading">
    <bk-select
      :class="{
        'is-selected-all': selectedAll
      }"
      collapse-tags
      filterable
      :input-search="false"
      :model-value="modelValue"
      multiple
      multiple-mode="tag"
      :placeholder="`请选择${config.label}`"
      :remote-method="handleSearch"
      :search-placeholder="t('请输入关键字')"
      @change="handleChange">
      <bk-option
        v-for="item in filterList"
        :key="config.valName ? item[config.valName] : item.id"
        :label="item[config.labelName ? config.labelName : 'name']"
        :value="item[config.valName ? config.valName : 'id']" />
      <template
        v-if="simple"
        #extension>
        <div class="analysis-mult-select-action">
          <div
            class="action-item"
            @click="handleSubmit">
            确认
          </div>
          <div
            class="action-item"
            @click="handleCancel">
            取消
          </div>
        </div>
      </template>
    </bk-select>
  </bk-loading>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    ref,
    // watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  // import EsQueryService from '@service/es-query';
  import type FieldMapModel from '@model/es-query/field-map';

  import useRequest from '@hooks/use-request';

  import  type {  IFieldConfig } from '../config';
  import useMultiCommon from '../hooks/use-multi-common';

  interface Props {
    config: IFieldConfig,
    name: keyof FieldMapModel,
    // eslint-disable-next-line vue/no-unused-properties
    model: Record<string, any>,
    simple?: boolean,
  }
  interface Exposes {
    getValue: ()=> Promise<Record<string, any>|string>
  }
  interface Emits {
    (e: 'change', name: string, value: Array<string>): void,
    (e: 'submit'): void,
    (e: 'cancel'): void,
  }

  const props = withDefaults(defineProps<Props>(), {
    simple: false,
  });

  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const list = ref([] as Array<Record<string, string>>);
  const loading = ref(false);

  let originList = [] as Array<Record<string, string>>;

  const filterList = computed(() => {
    if (props.config.filterList) {
      return list.value.filter((item) => {
        const valName = props.config.valName ? props.config.valName : 'id';
        if (props.config.filterList?.includes(item[valName])) return false;
        return true;
      });
    }
    if (originList.length === 0) {
      originList = _.cloneDeep(list.value);
    }
    return list.value;
  });

  const {
    modelValue,
    selectedAll,
    handleChange,
  } = useMultiCommon(props, t('全部'));

  if (props.config.service)   {
    loading.value = true;
    useRequest(props.config.service, {
      manual: true,
      defaultParams: props.config.defaultParams || {},
      defaultValue: [],
      onSuccess(data) {
        list.value = data;
        loading.value = false;
      },
    });
  }

  const handleSearch = (keyword: string) => {
    // 既可以通过labelName来搜索，也可以通过valName来搜索
    const filtered = originList.filter((item) => {
      const labelName = props.config.labelName ? props.config.labelName : 'name';
      const valName = props.config.valName ? props.config.valName : 'id';
      if (item[labelName].includes(keyword) || String(item[valName]).includes(keyword)) {
        return true;
      }
      return false;
    });
    list.value = [...filtered]; // 创建新数组引用
  };

  const handleSubmit = () => {
    emits('submit');
  };

  const handleCancel = () => {
    emits('cancel');
  };

  // if (props.name === 'tags' as keyof FieldMapModel) {
  //   watch(() => props.model.datetime, (val) => {
  //     console.log(val);
  //   }, {
  //     immediate: true,
  //     deep: true,
  //   });
  // }

  defineExpose<Exposes>({
    getValue() {
      if (props.config.validator && !props.config.validator(modelValue)) {
        return Promise.reject(`${props.name} error`);
      }
      return Promise.resolve({
        [props.name]: modelValue,
      });
    },
  });
</script>
