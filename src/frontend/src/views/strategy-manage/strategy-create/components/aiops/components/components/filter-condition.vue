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
  <div class="filter-conditon">
    <bk-form-item
      class="no-label"
      :description="t('取模型的输出做过滤')"
      label=""
      label-width="0">
      <!-- 条件下拉 -->
      <template v-if="!loading">
        <div
          v-for="(item, index) in formData.filter_config"
          :key="index"
          class="condition-item">
          <div style="display: flex;width: 200px;flex: 1;">
            <span
              v-if="index"
              v-bk-tooltips="t('点击切换')"
              class="condition-equation bold"
              style="width: 43px;margin-left: 0;border: 1px solid #c4c6cc;"
              @click="handleTriggerLogicOp(item)">
              {{ item.connector.toUpperCase() }}
            </span>
            <div style="position: relative; flex: 1;">
              <bk-form-item
                class="mb0"
                :class="{
                  'is-error': isNeedErrorTip && !item.key && (item.method || item.value.length)
                }"
                label=""
                label-width="0">
                <bk-select
                  v-model="item.key"
                  filterable
                  :input-search="false"
                  :placeholder="t('请选择')"
                  :search-placeholder="t('请输入关键字')"
                  @change="(value: string) => handleChangeCondition(value, index)">
                  <bk-option
                    v-for="(condition, conditionIndex) in rtFields"
                    :key="conditionIndex"
                    :label="condition.label"
                    :value="condition.value" />
                </bk-select>
              </bk-form-item>
            </div>
          </div>

          <!-- 等式 -->
          <div>
            <bk-form-item
              class="mb0"
              :class="{
                'is-error': isNeedErrorTip && !item.method && (item.key || item.value.length)
              }"
              label=""
              label-width="0">
              <bk-select
                v-model="item.method"
                class="condition-equation"
                filterable
                :placeholder="t('请选择')"
                @change="handleUpdateFilterConfig">
                <bk-option
                  v-for="(value, valueIndex) in operators.filter_operator"
                  :key="valueIndex"
                  :label="value.label"
                  :value="value.value" />
              </bk-select>
            </bk-form-item>
          </div>

          <!-- 值 -->
          <div
            class="value-box"
            :style="styles[index]">
            <bk-form-item
              class="mb0"
              :class="{
                'is-error': isNeedErrorTip && !item.value.length && (item.key || item.method)
              }"
              label=""
              label-width="0">
              <bk-select
                v-if="dicts[item.key] && dicts[item.key].length"
                v-model="item.value"
                allow-create
                class="consition-value"
                collapse-tags
                filterable
                :loading="fieldLoading"
                multiple
                multiple-mode="tag"
                :no-data-text="t('无数据')"
                :placeholder="t('请输入并Enter结束')"
                trigger="focus"
                @blur="isValueFocus[index]=false"
                @focus="isValueFocus[index]=true">
                <bk-option
                  v-for="(condition, conditionIndex) in dicts[item.key]"
                  :key="conditionIndex"
                  :label="condition.label"
                  :value="condition.value" />
              </bk-select>
              <bk-tag-input
                v-else
                v-model="item.value"
                allow-create
                class="consition-value"
                collapse-tags
                :content-width="350"
                has-delete-icon
                :input-search="false"
                :loading="fieldLoading"
                :placeholder="t('请输入并Enter结束')"
                trigger="focus"
                @blur="isValueFocus[index] = false"
                @change="handleUpdateFilterConfig"
                @focus="isValueFocus[index] = true" />
            </bk-form-item>
          </div>

          <!-- 添加 删除-->
          <div class="condition-icon">
            <div
              v-if="formData.filter_config.length > 1"
              v-bk-tooltips="t('删除')"
              class="ml8"
              @click="handleRemoveCondition(index)">
              <audit-icon type="reduce-fill" />
            </div>
          </div>
        </div>
      </template>
      <div
        style="width: 78px;"
        @click="handleAddCondition()">
        <bk-button
          text
          theme="primary">
          <audit-icon type="add" />
          {{ t('添加条件') }}
        </bk-button>
      </div>
    </bk-form-item>
  </div>
</template>
<script lang="ts">
  const lists = [
    {
      connector: 'and', // AND / OR
      key: '', // 统计字段
      method: '', //  等式
      value: [] as Array<string>, // 对应值
    },
  ];
  export type conditionData = typeof lists;
</script>

<script setup lang="ts">
  import _  from 'lodash';
  import {
    computed,
    reactive,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import useRequest from '@hooks/use-request';

  interface Exposes{
    handleValueDicts: (data: conditionData) => void,
    getValue(): void,
  }
  interface Emits {
    (e: 'updateFilterConfig', value: conditionData): void
  }
  interface Props {
    data: Record<string, any>,
    rtFields: Array<{
      label: string;
      value: string
    }>,
    loading: boolean,
  }

  interface Errors {
    condition: boolean,
    value: boolean,
    method: boolean,
    key: boolean,
  }
  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();

  const isNeedErrorTip = ref(false);
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';


  const errors = ref<Array<Errors>>([]);
  const dicts = ref<Record<string, Array<any>>>({});
  const isValueFocus = reactive({} as Record<string, boolean>);
  const formData = ref({
    filter_config: [...lists] as conditionData,
  });
  formData.value.filter_config = lists;
  let isInit = false;

  // eslint-disable-next-line vue/return-in-computed-property
  const styles = computed(() => {
    const styles = {} as Record<string, any>;
    if (!_.isEmpty(isValueFocus)) {
      Object.keys(isValueFocus).forEach((item) => {
        if (isValueFocus[item]) {
          styles[item] = { 'z-index': 999 };
        }
      });
    }
    return styles;
  });


  // 获取条件类型
  const {
    data: operators,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: {},
    manual: true,
  });
  // 筛选条件值
  const {
    run: fetchStrategyFieldValue,
    loading: fieldLoading,
  } = useRequest(StrategyManageService.fetchStrategyFieldValue, {
    defaultValue: [],
  });

  const handleAddCondition = () => {
    const item = {
      connector: 'and',
      key: '',
      method: '',
      value: [],
    };
    formData.value.filter_config.push(item);
    handleUpdateFilterConfig();
  };

  // 切换and
  const handleTriggerLogicOp = (item: Record<string, any>) => {
    // eslint-disable-next-line no-param-reassign
    item.connector = item.connector === 'and' ? 'or' : 'and';
    handleUpdateFilterConfig();
  };

  // 删除筛选条件
  const handleRemoveCondition = (index: number) => {
    formData.value.filter_config.splice(index, 1);
    errors.value.splice(index, 1);
    handleUpdateFilterConfig();
  };
  // 回显下拉值
  const  handleValueDicts = (conditions: conditionData) => {
    conditions.forEach((item) => {
      dicts.value[item.key] = [];
    });
    Object.keys(dicts.value).forEach((item) => {
      if (item) {
        fetchStrategyFieldValue({
          field_name: item,
        }).then((data) => {
          dicts.value[item] = data;
        });
      }
    });
  };

  // 切换筛选条件获取值
  const handleChangeCondition = (value: string, index: number) => {
    formData.value.filter_config[index].value = [];
    if (value) {
      fetchStrategyFieldValue({
        field_name: value,
      }).then((data) => {
        dicts.value[value] = data.filter((item: Record<string, any>) => item.id !== '');
      });
    }
    handleUpdateFilterConfig();
  };

  const handleUpdateFilterConfig = () => {
    isNeedErrorTip.value = false;
    emits('updateFilterConfig', formData.value.filter_config
      .filter(item => item.key && item.method && item.value && item.value.length));
  };

  watch(() => props.data, (data) => {
    if (data && !isInit && (isEditMode || isCloneMode || isUpgradeMode)) {
      if (data.filter_config && data.filter_config.length) {
        formData.value.filter_config = data.filter_config;
        isInit = true;
      }
    }
  }, {
    deep: true,
    immediate: true,
  });

  defineExpose<Exposes>({
    handleValueDicts(data: conditionData) {
      handleValueDicts(data);
    },
    getValue() {
      const res = formData.value.filter_config
        .every(item => (item.key && item.method && item.value.length)
          || (!item.key && !item.method && !item.value.length));
      if (res) {
        return Promise.resolve(1);
      }
      isNeedErrorTip.value = true;
      return Promise.reject(0);
    },
  });
</script>
<style lang="postcss" scoped>
.filter-conditon {
  .condition-item {
    display: flex;
    margin-bottom: 8px;
    justify-content: space-between;


    :deep(.bk-form-error) {
      display: none;
    }

    :deep(.bk-form-label::after) {
      width: 0;
      content: "";
    }

    :deep(.bk-form-label) {
      padding-right: 0;
    }

    .bold {
      font-weight: bold;
    }

    .mb0 {
      margin-bottom: 0;
    }

    .condition-equation {
      display: inline-block;
      width: 120px;
      height: 32px;
      margin: 0 8px;

      /* font-weight: bold; */
      color: #3a84ff;
      text-align: center;
      background: #fff;
      border-radius: 2px;

      :deep(.bk-input--text) {
        color: #3a84ff;
      }
    }

    .value-box {
      position: relative;
      height: 32px;

      .consition-value {
        width: 560px;
        flex: 1;
      }
    }

    .condition-icon {
      display: flex;
      margin-left: 8px;
      font-size: 14px;
      color: #c4c6cc;
      cursor: pointer;
    }


    :deep(.is-errored .bk-input) {
      border: 1px solid red;
    }

    .error-icon {
      position: absolute;
      top: 10px;
      right: 8px;
      color: #ea3636;
    }

    :deep(.bk-form-item.is-error .bk-tag-input-trigger) {
      border-color: #ea3636;
    }
  }
}
</style>
