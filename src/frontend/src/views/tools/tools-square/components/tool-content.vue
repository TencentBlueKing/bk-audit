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
    id="scroll-dialog-content"
    :style="contentStyle">
    <template
      v-if="toolDetails?.tool_type === 'data_search' || toolDetails?.tool_type === 'api'">
      <!-- 有权限时 -->
      <div v-if="toolDetails?.permission.use_tool">
        <div class="top-search">
          <div class="top-search-title">
            {{ t('查询输入') }}
          </div>
          <bk-form
            ref="formRef"
            class="example"
            form-type="vertical"
            :model="searchFormData"
            :rules="rules">
            <div class="formref-item">
              <bk-form-item
                v-for="(item, index) in localSearchList"
                v-show="item?.is_show !== false"
                :key="index"
                class="formref-item-item"
                :property="item?.raw_name"
                :required="item?.required">
                <template #label>
                  <span
                    v-bk-tooltips="{
                      disabled: !item?.description && !item?.raw_name.replace(/(body|path|query)$/, ''),
                      content: item?.description || item?.raw_name.replace(/(body|path|query)$/, ''),
                    }">
                    {{ item?.display_name || item?.raw_name.replace(/(body|path|query)$/, '') }}
                  </span>
                </template>
                <tool-form-item
                  ref="formItemRef"
                  :data-config="item"
                  @change="(val:any) => handleFormItemChange(val, item)" />
              </bk-form-item>
            </div>
          </bk-form>
          <div v-if="source === ''">
            <bk-button
              class="mr8"
              theme="primary"
              @click.stop="submit">
              查询
            </bk-button>
            <bk-button
              class="mr8"
              @click.stop="handleReset">
              重置
            </bk-button>
          </div>
        </div>
        <div class="top-search">
          <div class="top-search-title">
            {{ t('查询结果') }}
          </div>
          <div class="top-search-result">
            <bk-loading :loading="isLoading">
              <!-- sql工具 -->
              <data-search-result
                v-if="toolDetails?.tool_type === 'data_search'"
                ref="dataSearchResultRef"
                :get-tool-name-and-type="getToolNameAndType"
                :max-height="maxHeight"
                remote-pagination
                :risk-tool-params="riskToolParams"
                :search-list="localSearchList"
                :tool-details="toolDetails"
                :uid="uid"
                @handle-field-down-click="handleFieldDownClick" />

              <!-- api工具 -->
              <api-search-result
                v-show="toolDetails?.tool_type === 'api'"
                ref="apiSearchResultRef"
                :get-tool-name-and-type="getToolNameAndType"
                :max-height="maxHeight"
                :risk-tool-params="riskToolParams"
                :search-list="localSearchList"
                :tool-details="toolDetails"
                :uid="uid"
                @handle-field-down-click="handleFieldDownClick" />
            </bk-loading>
          </div>
        </div>
      </div>
      <!-- 无权限时 -->
      <div
        v-else
        class="default-permission">
        <div class="no-permission">
          <img
            class="no-permission-img"
            src="@images/no-permission.svg">
          <div class="no-permission-desc">
            <p class="no-permission-title">
              {{ t('无使用权限') }}
            </p>
            <p class="no-permission-text">
              {{ t('你没有该工具的使用权限，请前往申请权限') }}
            </p>
            <p
              class="no-permission-btn"
              @click.stop="handleIamApply">
              {{ t('申请权限') }}
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- bkVision工具 -->
    <bk-vision-result
      v-if="toolDetails?.tool_type === 'bk_vision'"
      ref="bkVisionResultRef"
      :drill-down-item-config="drillDownItemConfig"
      :drill-down-item-row-data="drillDownItemRowData"
      :is-drill-down-open="isDrillDownOpen"
      :risk-tool-params="riskToolParams"
      :search-list="localSearchList"
      :tool-details="toolDetails"
      :uid="uid" />
  </div>
</template>

<script setup lang="tsx">
  import _ from 'lodash';
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import IamManageService from '@service/iam-manage';

  import IamApplyDataModel from '@model/iam/apply-data';
  import ToolDetailModel from '@model/tool/tool-detail';

  import ApiSearchResult from './api-search-result.vue';
  import BkVisionResult from './bk-vision-result.vue';
  import DataSearchResult from './data-search-result.vue';

  import useRequest from '@/hooks/use-request';
  import ToolFormItem from '@/views/tools/tools-square/components/tool-form-item.vue';

  interface SearchItem {
    value: any;
    raw_name: string;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
    choices: Array<{
      key: string;
      name: string;
    }>;
    disabled: boolean;
    is_show?: boolean;
  }

  interface DrillDownItemConfig {
    source_field: string;
    target_value_type: string;
    target_value: string;
    target_field_type?: string;
  }

  interface Props {
    toolDetails: ToolDetailModel | null;
    uid: string;
    source?: string;
    searchList: SearchItem[];
    riskToolParams?: Record<string, any>;
    isDrillDownOpen?: boolean;
    drillDownItemConfig?: DrillDownItemConfig[];
    drillDownItemRowData?: Record<string, any>;
    maxHeight?: string;
    contentStyle?: Record<string, string>;
    getToolNameAndType: (uid: string) => { name: string; type: string };
  }

  interface Emits {
    (e: 'openFieldDown', drillDownItem: any, drillDownItemRowData: Record<string, any>, activeUid?: string): void;
    (e: 'update:searchList', val: SearchItem[]): void;
  }

  interface Exposes {
    submit: () => void;
    handleReset: () => void;
    setFormItemData: (list: SearchItem[]) => void;
    clearValidate: () => void;
    executeBkVision: () => void;
    resetApiGroupData: () => void;
    isLoading: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    source: '',
    isDrillDownOpen: false,
    drillDownItemConfig: () => [],
    drillDownItemRowData: () => ({}),
    maxHeight: '600px',
    contentStyle: () => ({}),
    riskToolParams: undefined,
  });

  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const formRef = ref();
  const formItemRef = ref();
  const dataSearchResultRef = ref();
  const apiSearchResultRef = ref();
  const bkVisionResultRef = ref();
  const rules = ref({});

  // 本地搜索列表，与父组件同步
  const localSearchList = computed({
    get: () => props.searchList,
    set: val => emit('update:searchList', val),
  });

  const searchFormData = computed(() => {
    const formData: Record<string, any> = {};
    localSearchList.value.forEach((item) => {
      formData[item.raw_name] = item.value;
    });
    return formData;
  });

  const isLoading = computed(() => {
    if (dataSearchResultRef.value) {
      return dataSearchResultRef.value.isLoading;
    }
    if (apiSearchResultRef.value) {
      return apiSearchResultRef.value.isLoading;
    }
    return false;
  });

  const {
    data: applyData,
    run: getApplyData,
  } = useRequest(IamManageService.getApplyData, {
    defaultValue: new IamApplyDataModel(),
  });

  const handleIamApply = () => {
    if (applyData.value?.apply_url) {
      window.open(applyData.value.apply_url, '_blank');
    }
  };

  const handleFormItemChange = (val: any, item: SearchItem) => {
    const target = localSearchList.value.find(i => i.raw_name === item.raw_name);
    if (target) {
      if (_.isEqual(target.value, val)) {
        return;
      }
      target.value = val;
    }
  };

  const submit = () => {
    formRef.value.validate().then(() => {
      formItemRef.value && formItemRef.value.forEach((item: any) => {
        item?.getData();
      });
      // 调用子组件的执行方法
      if (props.toolDetails?.tool_type === 'data_search' && dataSearchResultRef.value) {
        dataSearchResultRef.value.executeTool();
      } else if (props.toolDetails?.tool_type === 'api' && apiSearchResultRef.value) {
        apiSearchResultRef.value.executeTool();
      }
    });
  };

  const handleReset = () => {
    // 检查 searchList 中的所有 value 是否为空
    const allValuesEmpty = localSearchList.value.every(item => item.value === null
      || (Array.isArray(item.value) && item.value.length === 0));
    if (allValuesEmpty) {
      return;
    }

    const newList = localSearchList.value.map(item => ({
      ...item,
      value: (item.field_category === 'person_select' || item.field_category === 'time_range_select') ? [] : null,
    }));
    emit('update:searchList', newList);

    if (formItemRef.value) {
      formItemRef.value.forEach((item: any) => {
        item?.resetValue();
      });
    }

    formRef.value.clearValidate();
  };

  const handleFieldDownClick = (
    drillDownItem: any,
    drillDownItemRowData: Record<string, any>,
    activeUid?: string,
  ) => {
    emit('openFieldDown', drillDownItem, drillDownItemRowData, activeUid);
  };

  // 设置表单项数据
  const setFormItemData = (list: SearchItem[]) => {
    nextTick(() => {
      if (formItemRef.value) {
        formItemRef.value.forEach((item: any, index: number) => {
          item?.setData(list[index].value);
        });
        nextTick(() => {
          formRef.value.clearValidate();
        });
      }
    });
  };

  const clearValidate = () => {
    formRef.value?.clearValidate();
  };

  const executeBkVision = () => {
    nextTick(() => {
      if (bkVisionResultRef.value) {
        bkVisionResultRef.value.executeTool();
      }
    });
  };

  const resetApiGroupData = () => {
    if (apiSearchResultRef.value) {
      apiSearchResultRef.value.resetGroupData();
    }
  };

  // 权限检查
  watch(() => props.toolDetails, (val) => {
    if (val && !val.permission?.use_tool) {
      getApplyData({
        action_ids: 'use_tool',
        resources: val.uid,
      });
    }
  }, { immediate: true });

  defineExpose<Exposes>({
    submit,
    handleReset,
    setFormItemData,
    clearValidate,
    executeBkVision,
    resetApiGroupData,
    get isLoading() {
      return isLoading.value;
    },
  });
</script>

<style scoped lang="postcss">
.top-search {
  padding: 16px;
  margin-top: 12px;
  background: #fff;

  .top-search-title {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    letter-spacing: 0;
    color: #313238;
  }

  .top-search-result {
    position: relative;
    height: auto;
    padding-right: 16px;
    margin-top: 12px;

    .top-search-table-title {
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 20px;
      letter-spacing: 0;
      color: #313238;
    }
  }

  .example {
    margin-top: 10px;

    .formref-item {
      display: flex;
      flex-wrap: wrap;

      .formref-item-item {
        width: 400px;
        margin-right: 15px;
      }
    }
  }

  .list-data {
    margin-top: 10px;
  }
}

.default-permission {
  position: relative;
  height: 70vh;

  .no-permission {
    position: absolute;
    top: 30%;
    left: 50%;
    text-align: center;
    transform: translate(-50%, -30%);

    .no-permission-img {
      width: 200px;
      height: 200px;
      margin: 0 auto;
    }

    .no-permission-desc {
      margin-top: 16px;

      .no-permission-title {
        margin-bottom: 8px;
        font-size: 16px;
        font-weight: bold;
        color: #4d4f56;
      }

      .no-permission-text {
        margin-bottom: 12px;
        font-size: 14px;
        color: #63656e;
      }

      .no-permission-btn {
        font-size: 14px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }
}

/* api-search-result 样式覆盖 - 仅在工具广场生效 */
:deep(.card-content) {
  border: .5px solid #dcdee5;
  border-bottom-right-radius: 2px;
  border-bottom-left-radius: 2px;
}

:deep(.bk-table.bordered-outer) {
  border-top: none;
  border-right: none;
  border-left: none;

  .bk-table-footer {
    background-color: #fff;
    border-bottom: none;
  }
}

:deep(.bk-table) {
  .bk-table-head table thead th,
  .bk-table-body table thead th,
  table thead th {
    background-color: #f0f1f5 !important;
  }
}
</style>
