<template>
  <div class="risk-selector">
    <!-- 标题 -->
    <div class="query-header">
      <audit-icon
        class="query-icon"
        type="audit" />
      <span>请勾选需要解读的风险告警</span>
    </div>

    <!-- 搜索 -->
    <div class="query-section">
      <bk-input
        v-model="searchKeyword"
        clearable
        left-icon="bk-icon icon-search"
        placeholder="搜索风险 ID、风险名称、影响资产" />
    </div>

    <!-- 数据表格 -->
    <div class="query-table-wrapper">
      <div class="table-header-info">
        已选 {{ selectedRowKeys.length }} 条，共 {{ filteredTableData.length }} 条
      </div>
      <primary-table
        cell-empty-content="--"
        :columns="columns"
        :data="filteredTableData"
        hover
        :pagination="pagination"
        resizable
        row-key="id"
        :selected-row-keys="selectedRowKeys"
        table-layout="fixed"
        @page-change="handlePageChange"
        @select-change="handleSelectChange" />
    </div>

    <!-- 确认解读按钮 -->
    <div class="query-footer">
      <button
        class="confirm-btn"
        :class="{ 'is-active': selectedRowKeys.length > 0 }"
        :disabled="selectedRowKeys.length === 0"
        @click="handleConfirm">
        确认解读
      </button>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref, reactive, computed } from 'vue';
  import { PrimaryTable } from '@blueking/tdesign-ui';

  const emit = defineEmits<{
    confirm: [risks: any[]];
  }>();

  // 搜索
  const searchKeyword = ref('');

  // 表格数据
  const generateTableData = () => {
    const levels = ['严重', '高危', '中危', '低危'];
    const types = ['主机威胁', 'Web漏洞', '配置风险', '弱口令', '病毒事件'];
    const list = [];
    for (let i = 0; i < 20; i++) {
      const level = levels[i % 4];
      list.push({
        id: `risk_${i + 1}`,
        level,
        levelText: level,
        name: `${types[i % 5]}-${i + 1}`,
        type: types[i % 5],
        affectedAssets: `10.0.1.${23 + (i % 10)}`,
        foundTime: `2026-04-${(i % 10) + 1} 14:${(i % 60).toString().padStart(2, '0')}:12`,
        operator: ['Tom', 'Jerry', 'Alice', 'Bob'][i % 4],
      });
    }
    return list;
  };

  const tableData = ref(generateTableData());

  // 过滤
  const filteredTableData = computed(() => {
    if (!searchKeyword.value) return tableData.value;
    const keyword = searchKeyword.value.toLowerCase();
    return tableData.value.filter(row => row.id.toLowerCase().includes(keyword)
      || row.name.toLowerCase().includes(keyword)
      || row.affectedAssets.toLowerCase().includes(keyword)
      || row.type.toLowerCase().includes(keyword));
  });

  // 表格列定义
  const columns = [
    { colKey: 'row-select', type: 'multiple', width: 50 },
    {
      colKey: 'id',
      title: '风险 ID',
      width: 120,
    },
    {
      colKey: 'type',
      title: '风险类型',
      width: 100,
    },
    {
      colKey: 'foundTime',
      title: '风险发现时间',
      width: 160,
    },
    {
      colKey: 'level',
      title: '风险等级',
      width: 90,
      cell: (h: any, { row }: { row: any }) => {
        const levelClass = getRiskLevelClass(row.level);
        return h('span', {
          class: ['risk-level-tag', levelClass],
        }, row.level);
      },
    },
    {
      colKey: 'affectedAssets',
      title: '影响资产',
      width: 120,
    },
    {
      colKey: 'operator',
      title: '操作人',
      width: 80,
    },
  ];

  // 风险等级样式
  const getRiskLevelClass = (level: string) => {
    const map: Record<string, string> = {
      严重: 'risk-level-serious',
      高危: 'risk-level-high',
      中危: 'risk-level-medium',
      低危: 'risk-level-low',
    };
    return map[level] || '';
  };

  // 分页
  const pagination = reactive({
    current: 1,
    pageSize: 10,
    total: 20,
  });

  const handlePageChange = (pageInfo: { current: number; pageSize: number }) => {
    pagination.current = pageInfo.current;
    pagination.pageSize = pageInfo.pageSize;
  };

  // 选择
  const selectedRowKeys = ref<(string | number)[]>([]);
  const selectedRowData = ref<Record<string, any>[]>([]);

  const handleSelectChange = (
    selectedRowKey: Array<string | number>,
    options: { selectedRowData: Record<string, any>[] },
  ) => {
    selectedRowKeys.value = selectedRowKey;
    selectedRowData.value = options.selectedRowData;
  };

  // 确认
  const handleConfirm = () => {
    if (selectedRowData.value.length > 0) {
      emit('confirm', selectedRowData.value);
    }
  };
</script>

<style lang="postcss" scoped>
.risk-selector {
  .query-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;

    .query-icon {
      flex-shrink: 0;
    }

    span {
      font-size: 15px;
      font-weight: 600;
      color: #313238;
    }
  }

  .query-section {
    margin-bottom: 16px;
  }

  .query-table-wrapper {
    margin-top: 4px;

    .table-header-info {
      padding: 8px 12px;
      font-size: 13px;
      color: #63656e;
      background: #f5f7fa;
      border: 1px solid #dcdee5;
      border-bottom: none;
      border-radius: 4px 4px 0 0;
    }

    :deep(.t-table) {
      border: 1px solid #dcdee5;
      border-top: none;
      border-radius: 0 0 4px 4px;

      th {
        font-size: 13px;
        font-weight: 600;
        color: #313238;
        background: #fafbfd !important;
      }

      td {
        font-size: 13px;
        color: #63656e;
      }

      .risk-level-tag {
        display: inline-block;
        padding: 0 6px;
        font-size: 10px;
        font-weight: 500;
        border-radius: 2px;
      }

      .risk-level-serious {
        color: #ea3636;
        background: #fff0f0;
      }

      .risk-level-high {
        color: #ff9b29;
        background: #fff2e5;
      }

      .risk-level-medium {
        color: #feb02c;
        background: #fffbe6;
      }

      .risk-level-low {
        color: #3b84ff;
        background: #e6f7ff;
      }
    }
  }

  .query-footer {
    margin-top: 20px;
    text-align: left;

    .confirm-btn {
      padding: 8px 32px;
      font-size: 14px;
      color: #fff;
      cursor: pointer;
      background: #dce3ea;
      border: none;
      border-radius: 4px;
      transition: all .2s;

      &.is-active {
        background: #3a84ff;
      }

      &:hover.is-active {
        background: #5c97f7;
      }

      &:disabled {
        cursor: not-allowed;
      }
    }
  }
}
</style>
