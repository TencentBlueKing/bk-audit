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
  <bk-loading :loading="isLoading">
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
      :search-placeholder="t('请输入关键字')"
      @change="handleChange">
      <bk-option
        v-for="item in optionsList"
        :key="item.id"
        :label="config.labelName ? config.labelName : item.name"
        :value="config.valName ? config.valName : item.id" />
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
  import {
    computed,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EsQueryService from '@service/es-query';

  import FieldMapModel from '@model/es-query/field-map';

  import useRequest from '@hooks/use-request';

  import Config, { type IFieldConfig } from '../config';
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
  const selectKeys = Object.keys(Config).reduce((result, key) => {
    if (Config[key].type === 'select') {
      result.push(key);
    }
    return result;
  }, [] as Array<string>);

  const  {
    loading: isLoading,
    data,
  } = useRequest(EsQueryService.fetchFieldMap, {
    defaultValue: new FieldMapModel(),
    defaultParams: {
      fields: selectKeys.join(','),
    },
    manual: true,
  });

  const optionsList = computed(() => data.value[props.name]);

  const {
    modelValue,
    selectedAll,
    handleChange,
  } = useMultiCommon(props, t('全部'));

  const handleSubmit = () => {
    emits('submit');
  };

  const handleCancel = () => {
    emits('cancel');
  };

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
