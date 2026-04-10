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
    class="scene-table-wrapper"
    :class="[{ 'scene-table-section': !!title }]">
    <!-- 可选的标题区域（合并自 related-table-section） -->
    <div
      v-if="title"
      class="section-title">
      {{ title }}
      <bk-popover
        v-if="tooltip"
        :max-width="400"
        placement="top"
        theme="dark">
        <span style="display: inline-flex; align-items: center; width: 14px; height: 14px;">
          <audit-icon
            class="info-icon"
            type="info-fill" />
        </span>
        <template #content>
          <div>{{ tooltip }}</div>
        </template>
      </bk-popover>
    </div>
    <!-- PrimaryTable 表格 -->
    <primary-table
      :columns="columns"
      :data="pageData"
      :max-height="maxHeight"
      :resizable="resizable"
      row-key="id"
      :stripe="stripe"
      :style="{ '--row-height': rowHeight + 'px' }" />
    <!-- 分页器 -->
    <div
      v-if="showPagination && data.length > 0"
      class="scene-table-pagination">
      <div class="pagination-left">
        <span class="pagination-total">{{ t('共计') }} {{ data.length }} {{ t('条') }}</span>
        <span class="pagination-limit">
          {{ t('每页') }}
          <bk-select
            v-model="currentLimit"
            class="pagination-limit-select"
            :clearable="false"
            @change="handleLimitChange">
            <bk-option
              v-for="item in limitList"
              :key="item"
              :label="item"
              :value="item" />
          </bk-select>
          {{ t('条') }}
        </span>
      </div>
      <div class="pagination-right">
        <bk-pagination
          v-model="currentPage"
          :count="data.length"
          :limit="currentLimit"
          :show-limit="false"
          :show-total-count="false"
          small
          @change="handlePageChange" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { PrimaryTable } from '@blueking/tdesign-ui';

  import '@blueking/tdesign-ui/vue3/index.css';

  interface Props {
    columns: Array<Record<string, any>>;
    data: Array<Record<string, any>>;
    maxHeight?: number | string;
    showPagination?: boolean;
    limit?: number;
    limitList?: number[];
    title?: string;
    tooltip?: string;
    resizable?: boolean;
    stripe?: boolean;
    rowHeight?: number;
  }

  const props = withDefaults(defineProps<Props>(), {
    maxHeight: undefined,
    showPagination: false,
    limit: 10,
    limitList: () => [10, 20, 50],
    title: '',
    tooltip: '',
    resizable: false,
    stripe: true,
    rowHeight: 36,
  });

  const { t } = useI18n();

  const currentPage = ref(1);
  const currentLimit = ref(props.limit);

  // 监听 limit prop 变化
  watch(() => props.limit, (val) => {
    currentLimit.value = val;
  });

  // 当数据变化时重置页码
  watch(() => props.data, () => {
    currentPage.value = 1;
  });

  // 计算当前页数据
  const pageData = computed(() => {
    if (!props.showPagination) {
      return props.data;
    }
    const start = (currentPage.value - 1) * currentLimit.value;
    return props.data.slice(start, start + currentLimit.value);
  });

  const handlePageChange = (page: number) => {
    currentPage.value = page;
  };

  const handleLimitChange = (limit: number) => {
    currentLimit.value = limit;
    currentPage.value = 1;
  };
</script>

<style lang="postcss" scoped>
  .scene-table-wrapper {
    width: 100%;
  }

  /* 作为独立区块时的样式（带标题） */
  .scene-table-section {
    padding: 16px 24px 24px;
    margin-bottom: 24px;
    background-color: #fff;
    border-radius: 2px;
  }

  .section-title {
    display: flex;
    flex-wrap: nowrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .info-icon {
    flex-shrink: 0;
    font-size: 14px;
    color: #c4c6cc;
    cursor: pointer;
  }

  /* 时间标签 */
  :deep(.time-label) {
    display: inline-block;
    padding: 0 6px;
    font-size: 12px;
    line-height: 20px;
    border-radius: 2px;
  }

  :deep(.time-label-danger) {
    color: #ea3636;
    background-color: #feebea;
  }

  :deep(.time-label-warning) {
    color: #ff9c01;
    background-color: #fff3e1;
  }

  :deep(.time-label-success) {
    color: #2dcb56;
    background-color: #e5f6ea;
  }

  :deep(.domain-cell) {
    display: inline-flex;
    align-items: center;

    .domain-text {
      color: #313238;
    }

    .domain-jump-icon {
      display: none;
      align-items: center;
      margin-left: 4px;
      font-size: 15px;
      color: #3a84ff;
      cursor: pointer;
    }

    &:hover .domain-jump-icon {
      display: inline-flex;
    }
  }

  :deep(.ml8) {
    margin-left: 8px;
  }

  /* 可用字段下划线链接 */
  :deep(.field-count-link) {
    color: #313238;
    cursor: pointer;
    border-bottom: 1px dashed #c4c6cc;

    &:hover {
      color: #3a84ff;
      border-bottom-color: #3a84ff;
    }
  }

  /* 可用字段气泡窗内容 */
  :deep(.field-popover-content) {
    max-height: 500px;
  }

  /* PrimaryTable 表格样式 */
  :deep(.t-table) {
    th,
    td {
      height: var(--row-height, 36px) !important;
      border-right: none !important;
      border-left: none !important;
    }

    /* 表头行 */
    thead tr {
      background-color: #f5f7fa !important;
      border-bottom: 1px solid #dcdee5 !important;
    }

    /* 内容行 */
    tbody tr:nth-child(even) {
      background-color: #fafbfd !important;
    }

    tbody tr:nth-child(odd) {
      background-color: #fff !important;
    }
  }

  /* 分页器样式 */
  .scene-table-pagination {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 15px;
  }

  .pagination-left {
    display: flex;
    gap: 12px;
    align-items: center;
    font-size: 12px;
    color: #63656e;
  }

  .pagination-total {
    white-space: nowrap;
  }

  .pagination-limit {
    display: flex;
    gap: 4px;
    align-items: center;
    white-space: nowrap;
  }

  .pagination-limit-select {
    width: 56px;

    :deep(.bk-input) {
      height: 24px;
    }
  }

  .pagination-right {
    :deep(.bk-pagination) {
      justify-content: flex-end;
    }
  }
</style>
