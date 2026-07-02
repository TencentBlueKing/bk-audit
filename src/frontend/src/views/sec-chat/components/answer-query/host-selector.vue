<template>
  <div class="host-selector">
    <!-- 标题 -->
    <div class="query-header">
      <audit-icon
        class="query-icon"
        type="audit" />
      <span>为了进行分析，请选择时间范围和目标主机</span>
    </div>

    <!-- 时间范围 -->
    <div class="query-section">
      <label class="section-label">时间范围</label>
      <div class="picker-box">
        <date-picker
          v-model="localDateTimeValue"
          v-model:timezone="localTimezone"
          format="YYYY-MM-DD HH:mm:ss"
          type="datetimerange"
          @update:model-value="handleDateTimeChange"
          @update:timezone="handleTimezoneChange" />
      </div>
    </div>

    <!-- 目标主机 -->
    <div class="query-section">
      <label class="section-label">目标主机</label>
      <bk-input
        v-model="searchKeyword"
        clearable
        placeholder="搜索 IP 地址、云区域、所属业务、所属拓扑、操作系统" />
    </div>

    <!-- 数据表格 -->
    <div class="query-table-wrapper">
      <div class="table-header-info">
        已选 {{ selectedRowKeys.length }} 台，共 {{ tableData.length }} 台
      </div>
      <primary-table
        cell-empty-content="--"
        :columns="columns"
        :data="filteredTableData"
        hover
        max-height="400"
        :pagination="pagination"
        resizable
        row-key="id"
        :selected-row-keys="selectedRowKeys"
        table-layout="fixed"
        @page-change="handlePageChange"
        @select-change="handleSelectChange" />
    </div>

    <!-- 确认分析按钮 -->
    <div class="query-footer">
      <button
        class="confirm-btn"
        :class="{ 'is-active': selectedRowKeys.length > 0 }"
        :disabled="selectedRowKeys.length === 0"
        @click="handleConfirm">
        确认分析
      </button>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref, reactive, computed, watch } from 'vue';
  import { PrimaryTable } from '@blueking/tdesign-ui';

  const props = defineProps<{
    dateTimeValue: [string, string];
    timezone: string;
  }>();

  const emit = defineEmits<{
    'update:dateTimeValue': [value: [string, string]];
    'update:timezone': [value: string];
    confirm: [hosts: any[]];
  }>();

  // 本地状态
  const localDateTimeValue = ref<[string, string]>(props.dateTimeValue);
  const localTimezone = ref(props.timezone);

  watch(() => props.dateTimeValue, (val) => {
    localDateTimeValue.value = val;
  });

  watch(() => props.timezone, (val) => {
    localTimezone.value = val;
  });

  const handleDateTimeChange = (value: any) => {
    if (value && Array.isArray(value) && value.length === 2) {
      localDateTimeValue.value = [value[0], value[1]];
      emit('update:dateTimeValue', localDateTimeValue.value);
    }
  };

  const handleTimezoneChange = (tz: string) => {
    localTimezone.value = tz;
    emit('update:timezone', tz);
  };

  // 搜索
  const searchKeyword = ref('');

  // 表格数据
  const generateTableData = () => {
    const list = [];
    for (let i = 0; i < 12; i++) {
      list.push({
        id: `host_${i}`,
        ip: `10.0.1.${23 + i}`,
        cloudArea: '默认区域',
        bizName: '王者荣耀',
        topo: '王者荣耀/微信iOS大区/对战模块',
        os: 'CentOS 7.9',
        agentStatus: i % 3 === 0 ? '离线' : '在线',
      });
    }
    return list;
  };

  const tableData = ref(generateTableData());

  // 过滤
  const filteredTableData = computed(() => {
    if (!searchKeyword.value) return tableData.value;
    const keyword = searchKeyword.value.toLowerCase();
    return tableData.value.filter(row => row.ip.toLowerCase().includes(keyword)
      || row.cloudArea.toLowerCase().includes(keyword)
      || row.bizName.toLowerCase().includes(keyword)
      || row.topo.toLowerCase().includes(keyword)
      || row.os.toLowerCase().includes(keyword));
  });

  // 表格列定义
  const columns = [
    { colKey: 'row-select', type: 'multiple', width: 50 },
    { colKey: 'ip', title: 'IP 地址', width: 140 },
    { colKey: 'cloudArea', title: '云区域', width: 100 },
    { colKey: 'bizName', title: '所选业务', width: 100 },
    { colKey: 'topo', title: '所选拓扑' },
    { colKey: 'os', title: '操作系统', width: 120 },
    {
      colKey: 'agentStatus',
      title: 'Agent 状态',
      width: 100,
      cell: (h: any, { row }: { row: any }) => {
        const isOnline = row.agentStatus === '在线';
        return h('span', {}, [
          h('span', {
            class: ['status-dot', isOnline ? 'is-online' : ''],
            style: {
              display: 'inline-block',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: isOnline ? '#22a472' : '#c4c6cc',
              marginRight: '4px',
              verticalAlign: 'middle',
            },
          }),
          h('span', {}, row.agentStatus),
        ]);
      },
    },
  ];

  // 分页
  const pagination = reactive({
    current: 1,
    pageSize: 10,
    total: 12,
  });

  const handlePageChange = (pageInfo: { current: number; pageSize: number }) => {
    pagination.current = pageInfo.current;
    pagination.pageSize = pageInfo.pageSize;
  };

  // 选择 - 使用 PrimaryTable 的 select-change 事件
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
.host-selector {
  .query-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;

    .query-icon {
      font-size: 18px;
    }

    span {
      font-size: 15px;
      font-weight: 600;
      color: #313238;
    }
  }

  .query-section {
    margin-bottom: 16px;

    .section-label {
      display: block;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 600;
      color: #313238;
    }

    .picker-box {
      width: 100%;
    }
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
