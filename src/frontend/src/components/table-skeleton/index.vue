<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div
    class="audit-table-skeleton"
    data-testid="table-skeleton">
    <div
      class="audit-table-skeleton__header"
      :style="{ height: `${sizeConfig.headerHeight}px` }">
      <div
        v-for="(column, columnIndex) in normalizedColumns"
        :key="`header-${columnIndex}`"
        class="audit-table-skeleton__header-cell"
        :style="cellStyle(column)">
        <div
          class="audit-table-skeleton__header-bar"
          :style="{ width: barWidth(50 + ((columnIndex * 17 + 5) % 30)) }" />
      </div>
    </div>
    <div class="audit-table-skeleton__body">
      <div
        v-for="(row, rowIndex) in cellWidths"
        :key="`row-${rowIndex}`"
        class="audit-table-skeleton__row"
        :style="{ height: `${sizeConfig.rowHeight}px` }">
        <div
          v-for="(column, columnIndex) in normalizedColumns"
          :key="`cell-${rowIndex}-${columnIndex}`"
          class="audit-table-skeleton__cell"
          :style="cellStyle(column)">
          <div
            class="audit-table-skeleton__cell-bar"
            :style="{ width: barWidth(row[columnIndex]) }" />
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  export type TableSkeletonRowSize = 'large' | 'medium' | 'mini' | 'small';
  export interface TableSkeletonColumn {
    width: number;
    grow?: boolean;
  }
</script>
<script setup lang="ts">
  import {
    computed,
  } from 'vue';

  import '../skeleton/skeleton.css';

  interface Props {
    rowCount?: number;
    /** 像素列宽，或等分时的 flex 比例 */
    columns?: Array<number | TableSkeletonColumn>;
    columnCount?: number;
    rowSize?: TableSkeletonRowSize;
  }

  const props = withDefaults(defineProps<Props>(), {
    rowCount: 3,
    columns: undefined,
    columnCount: 5,
    rowSize: 'medium',
  });

  const ROW_SIZE_MAP: Record<TableSkeletonRowSize, { headerHeight: number; rowHeight: number }> = {
    mini: { headerHeight: 31, rowHeight: 33 },
    small: { headerHeight: 37, rowHeight: 39 },
    medium: { headerHeight: 43, rowHeight: 45 },
    large: { headerHeight: 57, rowHeight: 59 },
  };

  const sizeConfig = computed(() => ROW_SIZE_MAP[props.rowSize] || ROW_SIZE_MAP.medium);
  const normalizedColumns = computed(() => {
    const source = props.columns?.length
      ? props.columns
      : Array.from({ length: Math.max(props.columnCount, 1) }, () => 1);
    return source.map((column) => {
      if (typeof column === 'number') {
        return { width: 0, grow: false, flex: column };
      }
      return { width: column.width, grow: Boolean(column.grow), flex: 0 };
    });
  });
  const cellWidths = computed(() => {
    const rowTotal = Math.max(props.rowCount, 1);
    return Array.from({ length: rowTotal }, (_, rowIndex) => (
      normalizedColumns.value.map((_, columnIndex) => 60 + ((rowIndex * 7 + columnIndex * 13 + 3) % 31))
    ));
  });
  const cellStyle = (column: { width: number; grow: boolean; flex: number }) => {
    const narrow = column.width > 0 && column.width < 64;
    const shared = {
      display: 'flex',
      alignItems: 'center',
      justifyContent: narrow ? 'center' : 'flex-start',
      boxSizing: 'border-box' as const,
      height: '100%',
      padding: narrow ? '0 4px' : '0 16px',
      overflow: 'hidden',
    };
    if (column.width > 0 && column.grow) {
      return {
        ...shared,
        flex: `1 1 ${column.width}px`,
        width: 'auto',
        minWidth: '0',
      };
    }
    if (column.width > 0) {
      return {
        ...shared,
        flex: `0 1 ${column.width}px`,
        width: `${column.width}px`,
        minWidth: narrow ? `${column.width}px` : '48px',
        maxWidth: `${column.width}px`,
      };
    }
    return {
      ...shared,
      flex: `${column.flex || 1} 1 0px`,
      width: '0',
      minWidth: '0',
    };
  };
  // 相对单元格而不是整行。弹性列被拉宽后，色块跟着变长，避免按 minWidth 画成短条留下大空档。
  const barWidth = (percent: number) => `${percent}%`;
</script>
<style lang="postcss">
  .audit-table-skeleton {
    display: flex;
    flex-direction: column;
    width: 100%;
    overflow: hidden;
    border-radius: 4px 4px 0 0;
    animation: audit-skeleton-fade-in 0.3s ease-in-out;
  }

  .audit-table-skeleton__header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    width: 100%;
    background: #f0f4fa;
    border-bottom: 1px solid #e4e9f2;
  }

  .audit-table-skeleton__header-bar {
    flex-shrink: 0;
    max-width: 100%;
    height: 14px;
    background: #e4e9f2;
    border-radius: 4px;
  }

  .audit-table-skeleton__body {
    flex: 1;
    overflow: hidden;
  }

  .audit-table-skeleton__row {
    display: flex;
    align-items: center;
    width: 100%;
    border-bottom: 1px solid #e4e9f2;
  }

  .audit-table-skeleton__cell-bar {
    flex-shrink: 0;
    max-width: 100%;
    height: 14px;
    background: linear-gradient(90deg, #f2f6fc 0%, #e4e9f2 50%, #f2f6fc 100%);
    background-position: -200% 0;
    background-size: 200% 100%;
    border-radius: 4px;
    animation: audit-skeleton-shimmer 1.5s ease-in-out infinite;
  }
</style>
