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
  <bk-loading
    :loading="isGlobalsLoading"
    style="width: 600px;">
    <div class="log-filter-box">
      <bk-select
        :clearable="false"
        :model-value="data.type"
        style="width: 160px;"
        @change="(value: string) => handleChange('type', value)">
        <bk-option
          v-for="item in globalsData.param_conditions_type"
          :key="item.id"
          :label="item.name"
          :value="item.id" />
      </bk-select>
      <bk-select
        class="ml8"
        filterable
        :model-value="data.separator"
        style="width: 312px;"
        @change="(value: string) => handleChange('separator', value)">
        <bk-option
          v-for="item in globalsData.data_delimiter"
          :key="item.id"
          :label="item.name"
          :value="item.id" />
      </bk-select>
    </div>
    <div>
      <div class="separator-filter-tips">
        {{ t('复杂的过滤条件（超过5个）会影响机器性能') }}
      </div>
      <div class="separator-filter-list">
        <div
          v-for="(filterItem, index) in data.separator_filters"
          :key="index"
          class="separator-filter-row">
          <div
            v-if="index > 0"
            v-bk-tooltips="t('点击切换')"
            class="logic-operation-value"
            @click="handleLogicOperationChange">
            {{ filterItem.logic_op }}
          </div>
          <bk-input
            class="column-input"
            :model-value="filterItem.fieldindex"
            placeholder=" "
            :prefix="t('第')"
            :suffix="t('列')"
            @input="(value: any) => handleFieldIndexChange(value as string, index)" />
          <span class="column-expression">=</span>
          <bk-input
            class="column-value-input"
            :model-value="filterItem.word"
            :placeholder="t('输入匹配内容')"
            @input="(value: any) => handleWordChange(value as string, index)" />
          <div
            v-bk-tooltips="t('添加一个')"
            class="column-btn"
            style="margin-left: 5px;">
            <audit-icon
              type="add-fill"
              @click="handleAddSeparatorFilter(index)" />
          </div>
          <div
            v-if="data.separator_filters.length > 1"
            v-bk-tooltips="t('删除')"
            class="column-btn">
            <audit-icon
              type="reduce-fill"
              @click="handleRemoveSeparator(index)" />
          </div>
        </div>
      </div>
    </div>
    <div ref="separatorBottomRef" />
  </bk-loading>
</template>
<script setup lang="ts">
  import {
    computed,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import GlobalsModel from '@model/meta/globals';

  import useRequest from '@hooks/use-request';

  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  interface Props {
    data: {
      type: string,
      separator: string,
      separator_filters: Array<Record<'logic_op'|'fieldindex'|'word', string>>
    }
  }
  interface Emits {
    (e: 'change', value: Props['data']): void
  }

  const separatorBottomRef = ref();

  const currentLogicOp = computed(() => props.data.separator_filters[0]?.logic_op || 'AND');

  const {
    loading: isGlobalsLoading,
    data: globalsData,
  } = useRequest(MetaManageService.fetchGlobals, {
    defaultValue: new GlobalsModel(),
    manual: true,
    onSuccess(data) {
      handleChange('separator', data.data_delimiter[0].id);
    },
  });


  const handleLogicOperationChange = () => {
    const separatorFilters = props.data.separator_filters.map(item => ({
      ...item,
      logic_op: currentLogicOp.value === 'AND' ? 'OR' : 'AND',
    }));
    handleChange('separator_filters', separatorFilters);
  };
  const handleFieldIndexChange = (value: string, index: number) => {
    const separatorFilters = [...props.data.separator_filters];
    separatorFilters.splice(index, 1, {
      ...separatorFilters[index],
      fieldindex: value,
    });
    handleChange('separator_filters', separatorFilters);
  };
  const handleWordChange = (value: string, index: number) => {
    const separatorFilters = [...props.data.separator_filters];
    separatorFilters.splice(index, 1, {
      ...separatorFilters[index],
      word: value,
    });
    handleChange('separator_filters', separatorFilters);
  };
  // 新增条件
  const handleAddSeparatorFilter = (index: number) => {
    const separatorFilters = [...props.data.separator_filters];
    separatorFilters.splice(index + 1, 0, {
      logic_op: currentLogicOp.value,
      fieldindex: '',
      word: '',
    });
    handleChange('separator_filters', separatorFilters);
    setTimeout(() => {
      separatorBottomRef.value.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }, 100);
  };
  // 删除条件
  const handleRemoveSeparator = (index: number) => {
    const separatorFilters = [...props.data.separator_filters];
    separatorFilters.splice(index, 1);
    handleChange('separator_filters', separatorFilters);
  };

  const handleChange = (field: string, value: any) => {
    emits('change', {
      ...props.data,
      [field]: value,
    });
  };

  watch(() => props.data, (newData) => {
    if (newData.separator_filters && newData.separator_filters.length < 1) {
      handleAddSeparatorFilter(-1);
    }
  }, {
    immediate: true,
  });

  onMounted(() => {
    setTimeout(() => {
      separatorBottomRef.value.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }, 100);
  });
</script>
<style lang="postcss" scoped>
  .log-filter-box {
    display: flex;
  }

  .separator-filter-tips {
    margin-top: 24px;
    font-size: 12px;
    line-height: 16px;
    color: #979ba5;
  }

  .separator-filter-row {
    position: relative;
    display: flex;
    padding-left: 48px;
    margin-top: 12px;

    .logic-operation-value {
      position: absolute;
      top: 0;
      left: 0;
      width: 40px;
      height: 32px;
      font-size: 12px;
      color: #3a84ff;
      text-align: center;
      cursor: pointer;
      background: #fff;
      border: 1px solid #c4c6cc;
      border-radius: 2px;

      &:hover {
        background: #f0f1f5;
        border-color: #f0f1f5;
      }
    }

    .column-input {
      width: 112px;
    }

    .column-expression {
      display: flex;
      width: 26px;
      font-size: 14px;
      color: #3a84ff;
      align-items: center;
      justify-content: center;
    }

    .column-value-input {
      width: 294px;
    }

    .column-btn {
      display: flex;
      height: 32px;
      padding: 0 5px;
      font-size: 14px;
      color: #c4c6cc;
      cursor: pointer;
      align-items: center;
      justify-content: center;

      &:hover {
        color: #979ba5;
      }
    }
  }
</style>
