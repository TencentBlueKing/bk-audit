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
  <div class="render-form-serach-key">
    <div class="render-form-serach-top">
      <div
        class="box-row"
        :style="boxRowStyle">
        <template
          v-for="(fieldItem, fieldName) in defaultFieldList"
          :key="fieldName">
          <render-field-config
            ref="fieldConfigRef"
            class="box-column"
            :field-config="fieldConfig"
            :model="localSearchModel"
            :name="fieldName"
            @change="handleChange" />
        </template>
        <div class="show-more-condition-btn">
          <bk-button
            text
            theme="primary"
            @click="handleShowMore">
            {{ t('更多选项') }}
            <audit-icon
              :class="{ active: isShowMore }"
              style=" margin-left: 4px;"
              type="angle-double-down" />
          </bk-button>
        </div>
      </div>

      <template v-if="isShowMore">
        <div
          class="box-row"
          :style="boxRowStyle">
          <template
            v-for="(fieldItem, fieldName) in moreFieldList"
            :key="fieldName">
            <render-field-config
              ref="fieldConfigRef"
              class="box-column"
              :field-config="fieldConfig"
              :model="localSearchModel"
              :name="fieldName"
              @change="handleChange" />
          </template>
        </div>
      </template>
      <slot name="more-list" />
      <slot name="more-button" />
    </div>

    <div class="mt16">
      <bk-button
        class="mr8"
        theme="primary"
        @click="handleSubmit">
        {{ t('查询') }}
      </bk-button>
      <bk-button
        class="mr8"
        @click="handleReset">
        {{ t('重置') }}
      </bk-button>
      <slot name="button" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useUrlSearch from '@hooks/use-url-search';

  import type { IFieldConfig } from './render-field-config/config';
  // import filedConfig from './render-field-config/config';
  import RenderFieldConfig from './render-field-config/index.vue';

  interface Props {
    modelValue: Record<string, any>
    fieldConfig: Record<string, IFieldConfig>;
  }

  interface Emits {
    (e: 'update:modelValue', value: Record<string, any>): void,
    (e: 'submit'): void,
    (e: 'clear'): void,
    (e: 'modelValueWatch', value: Record<string, any>): void,
  }
  interface Exposes {
    showMore: (val: boolean) =>void,
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const allText = t('全部');
  // const isExportLoading = ref(false);
  const {
    replaceSearchParams,
    getSearchParams,
  } = useUrlSearch();

  const localSearchModel = ref<Record<string, any>>({
    datetime: ['', ''],
  });
  const fieldConfigRef = ref();
  const isShowMore = ref(false);

  const allFieldNameList = Object.keys(props.fieldConfig);
  const defaultFieldList = allFieldNameList.slice(0, 7).reduce((result, fieldName) => ({
    ...result,
    [fieldName]: props.fieldConfig[fieldName],
  }), {});
  const moreFieldList = allFieldNameList.slice(7).reduce((result, fieldName) => ({
    ...result,
    [fieldName]: props.fieldConfig[fieldName],
  }), {});

  // 同步外部值的改动
  watch(() => props.modelValue, () => {
    localSearchModel.value = props.modelValue;
    emits('modelValueWatch', localSearchModel.value);
  }, {
    immediate: true,
    deep: true,
  });

  // 显示更多搜索条件
  const handleShowMore = () => {
    isShowMore.value = !isShowMore.value;
  };
  const handleExShowMore = (val: boolean) => {
    isShowMore.value = val;
  };
  // 搜索项值改变
  const handleChange = (fieldName: string, value: any) => {
    // 精准更新特定键值
    localSearchModel.value[fieldName] = value;
    const replaceUrl = getSearchParams();
    if (Array.isArray(value)) {
      const normalized = value
        .map(item => (item == null ? '' : item.toString()))
        .filter(item => item !== '' && item !== allText);
      if (normalized.length === 0) {
        delete replaceUrl[fieldName];
      } else {
        replaceUrl[fieldName] = normalized.join(',');
      }
    } else if (value === '' || value === null || value === undefined) {
      delete replaceUrl[fieldName];
    } else {
      replaceUrl[fieldName] = value;
    }
    replaceSearchParams(replaceUrl);
  };
  // 提交搜索
  const updateSearchParams = () => {
    const replaceUrl = getSearchParams();
    const fieldNames = new Set(Object.keys(props.fieldConfig));
    if (Object.prototype.hasOwnProperty.call(localSearchModel.value, 'datetime_origin')) {
      fieldNames.add('datetime_origin');
    }
    fieldNames.forEach((fieldName) => {
      const value = localSearchModel.value[fieldName];
      if (Array.isArray(value)) {
        const normalized = value
          .map(item => (item == null ? '' : item.toString()))
          .filter(item => item !== '' && item !== allText);
        if (normalized.length === 0) {
          delete replaceUrl[fieldName];
        } else {
          replaceUrl[fieldName] = normalized.join(',');
        }
        return;
      }
      if (value === '' || value === null || value === undefined || value === allText) {
        delete replaceUrl[fieldName];
        return;
      }
      replaceUrl[fieldName] = value;
    });
    replaceSearchParams(replaceUrl);
  };
  const handleSubmit = () => {
    const getValues = fieldConfigRef.value.map((item: any) => item.getValue());
    Promise.all(getValues).then(() => {
      updateSearchParams();
      emits('update:modelValue', localSearchModel.value);
      emits('submit');
    });
  };
  // 重置所有搜索条件
  const handleReset = () => {
    localSearchModel.value = {
      datetime: ['', ''],
      datetime_origin: ['', ''],
    };
    emits('update:modelValue', localSearchModel.value);
    emits('clear');
  };

  const boxRowStyle = ref({
    'grid-template-columns': 'repeat(4, 1fr)',
  });

  const init = () => {
    const windowInnerWidth = window.innerWidth;
    boxRowStyle.value = windowInnerWidth < 1720 ? {
      'grid-template-columns': 'repeat(3, 1fr)',
    } : {
      'grid-template-columns': 'repeat(4, 1fr)',
    };
  };
  const resizeHandler = _.throttle(init, 100);

  onMounted(() => {
    init();
    window.addEventListener('resize', resizeHandler);
  });
  onBeforeUnmount(() => {
    window.removeEventListener('resize', resizeHandler);
  });
  defineExpose<Exposes>({
    showMore(val: boolean) {
      handleExShowMore(val);
    },
  });
</script>
<style lang="postcss">
  .render-form-serach-key {
    position: relative;
    padding: 16px 24px;

    .render-form-serach-top {
      max-height: 40vh;
      overflow-y: auto
    }

    .box-row {
      display: grid;
      margin-bottom: 12px;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px 16px;

      .box-column {
        display: inline-block;
      }
    }

    .show-more-condition-btn {
      display: inline-block;
      margin-top: 35px;

      .active {
        transform: rotateZ(-180deg);
        transition: all .15s;
      }
    }
  }
</style>
