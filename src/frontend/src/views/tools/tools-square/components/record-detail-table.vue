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
    class="record-detail-table"
    :class="{ 'simple-mode': simple }">
    <div
      v-if="title && !simple"
      class="detail-title">
      {{ title }}
    </div>
    <div
      v-if="!simple"
      class="detail-filter">
      <bk-date-picker
        v-if="showDatePicker"
        v-model="localDateRange"
        class="date-picker"
        :placeholder="t('最近半年')"
        type="daterange"
        @change="handleDateChange" />
      <!-- 额外筛选控件插槽 -->
      <slot name="extra-filter" />
      <bk-input
        v-model="localKeyword"
        class="search-input"
        :placeholder="searchPlaceholder"
        right-icon="bk-icon icon-search"
        type="search"
        @enter="handleSearch" />
    </div>
    <bk-table
      :columns="columns"
      :data="data"
      :pagination="simple ? false : pagination"
      :remote-pagination="!simple"
      stripe
      @page-limit-change="handlePageLimitChange"
      @page-value-change="handlePageChange" />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    title?: string;                   // 标题，如"登录明细"、"赠送明细"
    columns: Array<Record<string, any>>;  // 表格列配置
    data: Array<Record<string, any>>;     // 表格数据
    pagination?: {                    // 分页配置（simple 模式下不需要）
      count: number;
      current: number;
      limit: number;
    };
    searchPlaceholder?: string;       // 搜索框 placeholder
    showDatePicker?: boolean;         // 是否显示日期选择器，默认 true
    simple?: boolean;                 // 简洁模式：无标题、无搜索、无分页（概览页面使用）
  }

  withDefaults(defineProps<Props>(), {
    title: '',
    pagination: undefined,
    searchPlaceholder: '',
    showDatePicker: true,
    simple: false,
  });

  const emit = defineEmits<{
    'page-change': [page: number];
    'page-limit-change': [limit: number];
    'search': [keyword: string];
    'date-change': [range: [string, string]];
  }>();

  const { t } = useI18n();

  const localDateRange = ref<[string, string]>(['', '']);
  const localKeyword = ref('');

  const handlePageChange = (page: number) => {
    emit('page-change', page);
  };

  const handlePageLimitChange = (limit: number) => {
    emit('page-limit-change', limit);
  };

  const handleSearch = () => {
    emit('search', localKeyword.value);
  };

  const handleDateChange = (val: [string, string]) => {
    emit('date-change', val);
  };
</script>

<style scoped lang="postcss">
.record-detail-table {
  padding: 16px;
  background: #fff;
  border-radius: 2px;

  .detail-title {
    margin-bottom: 12px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .detail-filter {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;

    .date-picker {
      width: 200px;
    }

    .search-input {
      flex: 1;
    }
  }

  /* simple 模式下去掉内边距，让外部容器控制 */
  &.simple-mode {
    padding: 0;
    background: transparent;
  }
}
</style>
