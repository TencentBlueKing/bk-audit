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
  <div class="render-standard-field">
    <div class="field-header-row">
      <div class="field-key">
        {{ t('规范字段') }}
      </div>
      <div
        class="field-value"
        style="padding-left: 16px;">
        {{ t('调试字段') }}
      </div>
    </div>
    <bk-loading :loading="isFieldListLoading">
      <div
        v-for="(fieldItem, fieldIndex) in fieldList"
        :key="fieldIndex"
        class="field-row">
        <div class="field-key">
          <img
            class="field-type-icon"
            :src="getAssetsFile(`field-type/${fieldItem.field_type}.png`)">
          <span style="line-height: 20px;">
            {{ fieldItem.field_name }}（{{ fieldItem.description }}）
          </span>
          <span
            v-if="fieldItem.is_required"
            class="field-required">*</span>
        </div>
        <div class="field-value">
          <select-map-value
            ref="selectMapValueRef"
            :alternative-field-list="renderDataList"
            :data="fieldItem"
            :required="fieldItem.is_required"
            :value="fieldRelatedTargetMap[fieldItem.field_name]"
            @change="value => handleSelectMapValueChange(fieldItem.field_name, value)" />
        </div>
      </div>
    </bk-loading>
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  // import sortable from 'sortablejs';
  import {
    computed,
    nextTick,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import DataIdManageService from '@service/dataid-manage';
  import MetaManageService from '@service/meta-manage';

  import type EtlPreviewModel from '@model/collector/etl-preview';

  import useRequest from '@hooks/use-request';

  import getAssetsFile from '@utils/getAssetsFile';

  import SelectMapValue from '../select-map-value.vue';

  interface Props {
    // eslint-disable-next-line vue/no-unused-properties
    modelValue: Record<string, string>,
    data: Array<EtlPreviewModel>,
  }
  interface Emits {
    (e: 'change', value: Props['modelValue']): void,
    (e: 'update:modelValue', value: Props['modelValue']): void,
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const route = useRoute();
  const isEditMode = route.name === 'logDataIdEdit';

  type TFieldRelatedTargetMap = Record<string, Array<EtlPreviewModel>>

  const fieldRelatedTargetMap = ref<TFieldRelatedTargetMap>({});
  const selectMapValueRef = ref();

  const renderDataList = computed(() => {
    const relatedTargetMap = Object.values(fieldRelatedTargetMap.value).reduce((result, item) => {
      if (item.length > 0) {
        // eslint-disable-next-line no-param-reassign
        result[item[0].key] = true;
      }
      return result;
    }, {} as Record<string, true>);

    return props.data.reduce((result, item) => {
      if (!relatedTargetMap[item.key]) {
        result.push(item);
      }
      return result;
    }, [] as Array<EtlPreviewModel>);
  });


  // 获取默认选中调式字段
  const {
    run: fetchFieldHistory,
  } = useRequest(route.name === 'logDataIdEdit'
    ? DataIdManageService.fetchFieldHistory
    : CollectorManageService.fetchFieldHistory, {
    defaultParams: {
      id: route.params.id,
    },
    defaultValue: {} as Record<string, string>,
    onSuccess: (data) => {
      if (!_.isEmpty(data)) {
        handleDefaultFieldSelect(data);
      }
    },
  });

  const {
    loading: isFieldListLoading,
    data: fieldList,
  } = useRequest(MetaManageService.fetchStandardField, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      fieldRelatedTargetMap.value = data.reduce((result, item) => {
        // eslint-disable-next-line no-param-reassign
        result[item.field_name] = [];
        return result;
      }, {} as TFieldRelatedTargetMap);
    },
  });
  const handleSelectMapValueChange = (fieldName: string, value: Array<EtlPreviewModel>) => {
    if (!window.changeConfirm) {
      window.changeConfirm = true;
    }
    fieldRelatedTargetMap.value[fieldName] = value;
    const result = Object.keys(fieldRelatedTargetMap.value).reduce((result, fieldName) => {
      const relatedTarge = fieldRelatedTargetMap.value[fieldName];
      if (relatedTarge.length > 0) {
        // eslint-disable-next-line no-param-reassign
        result[fieldName] = relatedTarge[0].key;
      }
      return result;
    }, {} as Props['modelValue']);
    console.log('result2222', result);
    emits('change', result);
    emits('update:modelValue', result);
  };
  // const handlerowDrop = () => {
  //   // 此时找到的元素是要拖拽元素的父容器
  //   const tbody = document.querySelector('.render-standard-field') as HTMLElement;
  //   sortble(tbody);
  // };
  // 调试字段拖动排序
  // const sortble = (el: any) => {
  //   console.log(el);
  //   sortable.create(el, {
  //     //  指定父元素下可被拖拽的子元素
  //     draggable: '.render-standard-field .field-row',
  //     animation: 100,
  //     onEnd(evt: any) {
  //       const { oldIndex } = evt;
  //       const { newIndex } = evt;
  //       console.log(oldIndex, newIndex);
  //       // if (oldIndex !== newIndex) {
  //       //   const list = Array.from(evt.to.rows).map((item:any) => item.className.split(' ')[0]);
  //       //   const data = [] as FieldModel[]; // 排序之后的数据
  //       //   formData.value.normal_fields.forEach((item) => {
  //       //     const index = list.indexOf(item.key);
  //       //     data[index] = item;
  //       //   });
  //       // }
  //     },
  //   });
  // };

  // 编辑设置默认选中调试字段
  const handleDefaultFieldSelect = (data: Record<string, string>) => {
    const defaultList = renderDataList.value.reduce((result, item) => {
      if (Object.values(data).includes(item.key)) {
        Object.keys(data).forEach((key) => {
          if (item.key === data[key]) {
            result.push({ value: item, key });
          }
        });
      }
      return result;
    }, [] as Array<{ value: EtlPreviewModel, key: string }>);
    defaultList.forEach((item) => {
      fieldRelatedTargetMap.value[item.key] = [item.value];
    });
    const result = Object.keys(fieldRelatedTargetMap.value).reduce((result, fieldName) => {
      const relatedTarge = fieldRelatedTargetMap.value[fieldName];
      if (relatedTarge.length > 0) {
        // eslint-disable-next-line no-param-reassign
        result[fieldName] = relatedTarge[0].key;
      }
      return result;
    }, {} as Props['modelValue']);
    emits('change', result);
    emits('update:modelValue', result);
  };
  // 快速映射
  const handleAutoMapping = (data: Array<EtlPreviewModel>) => {
    data.forEach((item) => { // 快速映射
      if (fieldRelatedTargetMap.value[item.key]) {
        fieldRelatedTargetMap.value[item.key] = [item];
      }
    });
    const result = Object.keys(fieldRelatedTargetMap.value).reduce((result, fieldName) => {
      const relatedTarge = fieldRelatedTargetMap.value[fieldName];
      if (relatedTarge.length > 0) {
        // eslint-disable-next-line no-param-reassign
        result[fieldName] = relatedTarge[0].key;
      }
      return result;
    }, {} as Props['modelValue']);
    emits('change', result);
    emits('update:modelValue', result);
  };

  watch(() => props.data, (data) => {
    handleAutoMapping(data);
  });
  onMounted(() => {
    nextTick(() => {
    // handlerowDrop();
    });
  });
  defineExpose({
    getValue() {
      return Promise.all(selectMapValueRef.value.map((item: typeof SelectMapValue) => item.getValue()));
    },
    // 点击调试清空调试字段
    clearFiledDebug() {
      Object.keys(fieldRelatedTargetMap.value).forEach((key) => {
        fieldRelatedTargetMap.value[key] = [];
      });
      emits('change', {});
      emits('update:modelValue', {});
    },
    getFieldHistory() {
      if (isEditMode) {
        console.log('getFieldHistory', route.params);
        fetchFieldHistory({
          id: route.params.id,
        });
      }
    },
  });

</script>
<style lang="postcss" scoped>
.render-standard-field {
  display: flex;
  min-width: 640px;
  overflow: hidden;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-header-row {
    display: flex;
    font-size: 12px;
    line-height: 42px;
    color: #313238;
    background: #f0f1f5;

    .field-key {
      background: #f0f1f5;
    }
  }

  .field-row {
    display: flex;
    overflow: hidden;
    font-size: 12px;
    line-height: 42px;
    color: #63656e;
    border-top: 1px solid #dcdee5;
  }

  .field-key {
    position: relative;
    align-items: center;
    flex: 1 0 340px;
    display: flex;
    padding-left: 16px;
    background: #fafbfd;

    .field-type-icon {
      width: 46px;
      margin-right: 6px;
    }

    .field-required {
      margin-right: 10px;
      margin-left: auto;
      color: #ea3636;
    }
  }

  .field-value {
    overflow: hidden;
    border-left: 1px solid #dcdee5;
    flex: 1 1 320px;
  }
}
</style>
