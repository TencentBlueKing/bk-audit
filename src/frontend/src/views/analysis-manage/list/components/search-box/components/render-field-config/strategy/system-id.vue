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
      show-selected-icon
      @change="handleChange">
      <auth-option
        v-for="item in data"
        :key="item.id"
        action-id="search_regular_event"
        :label="item.name"
        :permission="item.permission.search_regular_event"
        :resource="item.id"
        :value="item.id" />
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
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  import type { IFieldConfig } from '../config';
  import useMultiCommon from '../hooks/use-multi-common';

  interface Props {
    config: IFieldConfig,
    // eslint-disable-next-line vue/no-unused-properties
    name: string,
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
  const {
    loading,
    data,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultParams: {
      action_ids: 'search_regular_event',
    },
    defaultValue: [],
    manual: true,
  });

  const {
    modelValue,
    selectedAll,
    handleChange,
  } = useMultiCommon(props, t('全部（有权限）'));

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
