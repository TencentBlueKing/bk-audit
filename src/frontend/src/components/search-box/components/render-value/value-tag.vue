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
    v-if="isRender"
    class="search-value-tag">
    <div
      ref="rootRef"
      class="tag-pop-ref">
      <div class="mr8">
        {{ t(safeConfig.label) }}:
      </div>
      <div class="value-text">
        <template v-if="isFieldMapLoading || isRemoteOriginLoading">
          ...
        </template>
        <template v-else>
          {{ renderValueText }}
        </template>
      </div>
    </div>
    <audit-icon
      v-if="!safeConfig.required"
      class="remove-btn"
      type="close"
      @click="handleRemove" />
    <div style="display: none;">
      <div
        ref="popRef"
        style="width: 368px; padding: 9px 15px;">
        <render-field-config
          ref="fieldConfigRef"
          :field-config="fieldConfig"
          :model="model"
          :name="name"
          simple
          @cancel="handleCancel"
          @change="handleChange"
          @submit="handleSubmit" />
        <div style="margin-top: 8px; font-size: 14px; line-height: 22px; color: #3a84ff; text-align: right;">
          <span
            style="margin-right: 16px; cursor: pointer;"
            @click="handleSubmit">
            {{ t('确定') }}
          </span>
          <span
            style="cursor: pointer;"
            @click="handleCancel">
            {{ t('取消') }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">

  let singleIns: Instance;
  export default {

  };
</script>
<script setup lang="ts">
  import _ from 'lodash';
  import tippy, {
    type Instance,
    type SingleTarget,
  } from 'tippy.js';
  import {
    computed,
    onBeforeUnmount,
    ref,
    shallowRef,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EsQueryService from '@service/es-query';

  import FieldMapModel from '@model/es-query/field-map';

  import useRequest from '@hooks/use-request';

  import type { IFieldConfig } from '../render-field-config/config';
  // import fieldConfig from '../render-field-config/config';
  import RenderFieldConfig from '../render-field-config/index.vue';

  import { makeMap } from '@/utils/assist';

  interface Props {
    name: string,
    value: any,
    model: Record<string, any>
    fieldConfig: Record<string, IFieldConfig>;
  }
  interface Emits {
    (e: 'remove', name: string): void
    (e: 'change', name: string, value: any): void
  }
  interface Exposes {
    getValue: (fieldValue: string)=> Promise<Record<string, any>|string>,
    handleCancel: ()=> void
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const config = computed(() => props.fieldConfig[props.name]);
  const safeConfig = computed(() => config.value || {
    label: props.name,
    type: 'string',
    required: false,
  });

  const rootRef = ref();
  const popRef = ref();
  const fieldConfigRef = ref();
  const isRemoteOriginLoading = ref(false);
  const remoteOriginalList = shallowRef<Array<any>>([]);

  const allSelectTypeKeyList = Object.keys(props.fieldConfig).reduce((result, key) => {
    if (props.fieldConfig[key].type === 'select') {
      result.push(key);
    }
    return result;
  }, [] as Array<string>);

  const {
    loading: isFieldMapLoading,
    data: fieldMap,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(EsQueryService.fetchFieldMap, {
    defaultValue: new FieldMapModel(),
    defaultParams: {
      fields: allSelectTypeKeyList.join(','),
    },
    // eslint-disable-next-line vue/no-setup-props-destructure
    manual: allSelectTypeKeyList.includes(props.name),
  });

  if (config.value?.service) {
    isRemoteOriginLoading.value = true;
    config.value.service()
      .then((data) => {
        remoteOriginalList.value = data;
      })
      .finally(() => {
        isRemoteOriginLoading.value = false;
      });
  }

  const isRender = computed(() => !_.isEmpty(props.value) && !!config.value);

  const renderValueText = computed(() => {
    if (_.isEmpty(props.value)) {
      return '--';
    }
    if (safeConfig.value.type === 'datetimerange') {
      return `${props.value[0]} ${t('至')} ${props.value[1]}`;
    }
    if (safeConfig.value.type === 'select') {
      const valueMap = (props.value as Array<string>).reduce((result, item: string) => ({
        ...result,
        [item]: true,
      }), {} as Record<string, boolean>);

      return fieldMap.value[props.name as keyof FieldMapModel].reduce((result, item) => {
        if (valueMap[item.id]) {
          result.push(item.name);
        }
        return result;
      }, [] as Array<string>).join(' | ');
    }
    if (config.value?.service && remoteOriginalList.value.length > 0) {
      const valueList = Array.isArray(props.value) ? props.value : [props.value];
      const valueMap = makeMap(valueList);
      const valueKeyList = remoteOriginalList.value.reduce((result, item) => {
        if (valueMap[item.id]) {
          result.push(item.name);
        }
        return result;
      }, [] as Array<string>);
      return valueKeyList.join(' | ');
    }
    return Array.isArray(props.value) ? props.value.join(' | ') : props.value;
  });

  let valueMemo: any;

  let tippyIns: Instance | null = null;

  // 删除
  const handleRemove = () => {
    emits('remove', props.name);
  };
  // 编辑值
  const handleChange = (fieldName: string, fieldValue: any) => {
    valueMemo = fieldValue;
  };
  // 提交编辑状态
  const handleSubmit = () => {
    if (valueMemo !== undefined) {
      emits('change', props.name, valueMemo);
    } else {
      tippyIns?.hide();
    }
  };
  // 取消
  const handleCancel = () => {
    tippyIns?.hide();
  };

  const initTippy = () => {
    if (tippyIns || !rootRef.value || !popRef.value) {
      return;
    }
    tippyIns = tippy(rootRef.value as SingleTarget, {
      content: popRef.value,
      placement: 'bottom-start',
      appendTo: () => document.body,
      theme: 'search-value-edit-theme light',
      maxWidth: 'none',
      trigger: 'click',
      interactive: true,
      arrow: true,
      offset: [0, 8],
      zIndex: 999,
      hideOnClick: false,
      onShow() {
        if (singleIns) {
          singleIns.hide();
        }
        singleIns = tippyIns as Instance;
      },
    });
  };

  watch([rootRef, popRef, isRender], () => {
    if (isRender.value) {
      initTippy();
    }
  }, { immediate: true });

  onBeforeUnmount(() => {
    tippyIns?.hide();
    tippyIns?.unmount();
    tippyIns?.destroy();
    tippyIns = null;
  });

  defineExpose<Exposes>({
    getValue(fieldValue:string) {
      if (fieldConfigRef.value) {
        return fieldConfigRef.value.getValue(fieldValue);
      }
    },
    handleCancel() {
      tippyIns?.hide();
    },
  });
</script>
<style lang="postcss">
  .search-value-tag {
    display: flex;
    height: 22px;
    padding: 0 6px;
    margin-right: 6px;
    margin-bottom: 8px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #f0f1f5;
    border-radius: 2px;
    transition: all .15s;
    align-items: center;

    .tag-pop-ref {
      display: flex;
    }

    &:hover {
      color: #63656e;
      background: #dcdee5;
    }

    .value-text {
      max-width: 400px;
      overflow: hidden;
      text-overflow: ellipsis;
      word-break: keep-all;
      white-space: nowrap;
    }

    .remove-btn {
      margin-left: 8px;
    }
  }
</style>
