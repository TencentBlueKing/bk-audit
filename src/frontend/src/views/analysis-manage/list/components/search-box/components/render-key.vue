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
    <div
      class="box-row"
      :style="boxRowStyle">
      <template
        v-for="(fieldItem, fieldName) in defaultFieldList"
        :key="fieldName">
        <render-field-config
          ref="fieldConfigRef"
          class="box-column"
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
            :model="localSearchModel"
            :name="fieldName"
            @change="handleChange" />
        </template>
      </div>
      <!-- 新版查询不支持此参数 -->
      <div
        v-if="!isDoris.enabled"
        class="box-row">
        <render-field-config
          v-for="(fieldItem, fieldName) in queryStringField"
          :key="fieldName"
          ref="fieldConfigRef"
          :model="localSearchModel"
          :name="fieldName"
          @change="handleChange" />
      </div>
    </template>
    <!-- <div>
      <BkCheckbox>查询敏感数据</BkCheckbox>
    </div> -->
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
      <!-- <BkButton>添加跟踪策略</BkButton> -->
    </div>
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import _ from 'lodash';
  import {
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import filedConfig from './render-field-config/config';
  import RenderFieldConfig from './render-field-config/index.vue';

  import useFeature from '@/hooks/use-feature';

  interface Props {
    modelValue: Record<string, any>
  }

  interface Emits {
    (e: 'update:modelValue', value: Record<string, any>): void,
    (e: 'submit'): void,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const { feature: isDoris } = useFeature('enable_doris');

  const localSearchModel = ref<Record<string, any>>({});
  const fieldConfigRef = ref();
  const isShowMore = ref(false);

  const allFieldNameList = Object.keys(filedConfig) as Array<keyof typeof filedConfig>;
  const defaultFieldList = allFieldNameList.slice(0, 7).reduce((result, fieldName) => ({
    ...result,
    [fieldName]: filedConfig[fieldName],
  }), {});
  const moreFieldList = allFieldNameList.slice(7).reduce((result, fieldName) => {
    if (fieldName === 'query_string') {
      return result;
    }
    return {
      ...result,
      [fieldName]: filedConfig[fieldName],
    };
  }, {});
  const queryStringField = {
    query_string: filedConfig.query_string,
  };

  // 同步外部值的改动
  watch(() => props.modelValue, () => {
    localSearchModel.value = props.modelValue;
  }, {
    immediate: true,
  });

  // 显示更多搜索条件
  const handleShowMore = () => {
    isShowMore.value = !isShowMore.value;
  };
  // 搜索项值改变
  const handleChange = (fieldName: string, value: any) => {
    localSearchModel.value = {
      ...localSearchModel.value,
      [fieldName]: value,
    };
  };
  // 提交搜索
  const handleSubmit = () => {
    const getValues = fieldConfigRef.value.map((item: any) => item.getValue());
    Promise.all(getValues).then(() => {
      emits('update:modelValue', localSearchModel.value);
      emits('submit');
    });
  };
  // 重置所有搜索条件
  const handleReset = () => {
    localSearchModel.value = {
      datetime: [
        dayjs(Date.now() - 900000).format('YYYY-MM-DD HH:mm:ss'),
        dayjs().format('YYYY-MM-DD HH:mm:ss'),
      ],
      datetime_origin: [
        'now-15m',
        'now',
      ],
    };
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
</script>
<style lang="postcss">
  .render-form-serach-key {
    position: relative;
    padding: 16px 24px;

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
