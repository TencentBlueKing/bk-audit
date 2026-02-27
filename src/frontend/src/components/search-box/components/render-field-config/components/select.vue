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
      :model-value="displayModelValue"
      :multiple="isMultiple"
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
    onUnmounted,
    ref,
    watch,
    watchEffect,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  // import EsQueryService from '@service/es-query';
  import type FieldMapModel from '@model/es-query/field-map';

  import useRequest from '@hooks/use-request';

  import { DateRange } from '@blueking/date-picker';

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

  // multiple 默认为 true
  const isMultiple = computed(() => props.config.multiple ?? true);

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
    handleChange: handleMultiChange,
  } = useMultiCommon(props, t('全部'));

  // 处理单选和多选的变化
  const handleChange = (value: Array<string | number> | string | number) => {
    if (isMultiple.value) {
      // 多选模式：直接使用数组
      handleMultiChange(value as Array<string | number>);
      return;
    }
    // 单选模式：将单个值转换为数组
    const singleValue = value === undefined || value === '' ? [] : [value as string | number];
    handleMultiChange(singleValue);
  };

  // 根据单选/多选模式调整 modelValue
  const displayModelValue = computed(() => {
    if (isMultiple.value) {
      return modelValue.value;
    }
    // 单选模式：返回数组的第一个值，如果没有则返回空字符串
    return modelValue.value.length > 0 ? modelValue.value[0] : '';
  });

  // eslint-disable-next-line max-len
  const fetchListRef = ref<(params: Record<string, any>) => Promise<Array<Record<string, string>>>>(() => Promise.resolve([]));

  // 判断是否为特殊字段
  const isSpecialField = (fieldName: keyof FieldMapModel): boolean => fieldName === 'tags' as keyof FieldMapModel
    || fieldName === 'strategy_id' as keyof FieldMapModel;

  watchEffect(() => {
    if (props.config.service) {
      loading.value = true;
      const { run } = useRequest(props.config.service, {
        defaultParams: props.config.defaultParams || {},
        manual: !isSpecialField(props.name),  // 特定字段 watch中 immediate为true，会初始化
        defaultValue: [],
        onSuccess(data) {
          // modelValue.value清除不在data中的, '全部'这个值不用清除
          const filterArr = modelValue.value.filter((modelValueItem) => {
            const valName = props.config.valName ? props.config.valName : 'id';
            if (modelValueItem === '全部') return true;
            if (data.some(listItem => listItem[valName] === modelValueItem)) {
              return true;
            }
            return false;
          });
          // 更新
          handleChange(filterArr);
          list.value = data;
          loading.value = false;
        },
      });

      fetchListRef.value = run;

      // 1.只有特定字段才需要设置监听时间，
      // 2.获取时间后，根据时间重新获取list，
      if (isSpecialField(props.name)) {
        const stopWatch = watch(
          () => props.model.datetime_origin,
          (val) => {
            if (!val) return;
            // 获取最新的、正确的时间格式
            const date = new DateRange(val, 'YYYY-MM-DD HH:mm:ss', window.timezone);

            if (date.startDisplayText && date.endDisplayText) {
              // 使用最新的 defaultParams
              fetchListRef.value({
                ...(props.config.defaultParams || {}),
                start_time: date.startDisplayText,
                end_time: date.endDisplayText,
              });
            }
          },
          {
            deep: true,
            immediate: true,
          },
        );

        // 组件卸载时清除监听
        onUnmounted(stopWatch);
      }
    }
  });

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
