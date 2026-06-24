<template>
  <tdesign-list
    ref="listRef"
    class="report-config-list"
    :columns="tableColumns"
    :data-source="dataSource"
    is-need-scene-params
    need-empty-search-tip
    :row-class-name="rowClassName"
    row-key="id"
    @request-success="handleRequestSuccess" />
</template>

<script setup lang="tsx">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { formatDate } from '@utils/assist/timestamp-conversion';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  interface ReportItem {
    id: string;
    binding_type: string;
    name: string;
    description: string;
    vision_id: string;
    bkvisionReportName: string;
    status: 'published' | 'unpublished';
    updated_by: string;
    updated_at: string;
  }

  interface Props {
    highlightReportId?: string | null;
    dataSource: (params: any) => Promise<any>;
  }

  interface Emits {
    (e: 'edit', row: ReportItem): void;
    (e: 'toggle-status', row: ReportItem): void;
    (e: 'delete', row: ReportItem): void;
    (e: 'request-success', data: any): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    highlightReportId: null,
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const listRef = ref();

  // 新建行高亮 - 响应式 rowClassName
  const rowClassName = computed(() => {
    const highlightId = props.highlightReportId;
    return (row: Record<string, any>) => (row.id === highlightId ? 'is-new-created' : '');
  });

  // 状态 tag 主题映射
  const statusThemeMap: Record<string, string> = {
    published: 'success',
    unpublished: 'default',
  };

  const tableColumns = ref([
    {
      title: t('名称'),
      colKey: 'name',
      width: 150,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ReportItem }) => (
        <span class="report-name-cell">
          <Tooltips data={row.name} />
        </span>
      ),
    },
    {
      title: t('描述'),
      colKey: 'description',
      width: 180,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ReportItem }) => (
        <span>{row.description || '--'}</span>
      ),
    },
    {
      title: t('BKVision 报表'),
      colKey: 'bkvisionReportName',
      width: 160,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ReportItem }) => (
        <span>{row.bkvisionReportName || '--'}</span>
      ),
    },
    {
      title: t('状态'),
      colKey: 'status',
      width: 80,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ReportItem }) => (
        <bk-tag radius="4px" theme={statusThemeMap[row.status] || 'default'}>
          {row.status === 'published' ? t('启用') : t('停用')}
        </bk-tag>
      ),
    },
    {
      title: t('更新人'),
      colKey: 'updated_by',
      width: 120,
      ellipsis: true,
    },
    {
      title: t('更新时间'),
      colKey: 'updated_at',
      width: 180,
      ellipsis: true,
      sortType: 'all',
      sorter: true,
      cell: (_h: any, { row }: { row: ReportItem }) => (
        <span>{row.updated_at ? formatDate(row.updated_at) : '--'}</span>
      ),
    },
    {
      title: t('操作'),
      colKey: 'action',
      width: 160,
      fixed: 'right',
      cell: (_h: any, { row }: { row: ReportItem }) => {
        const isPublished = row.status === 'published';

        return (
          <div class="action-cell">
            <bk-button
              text
              theme="primary"
              class="mr8"
              onClick={() => emit('edit', row)}>
              {t('编辑')}
            </bk-button>
            <bk-button
              text
              theme="primary"
              class="mr8"
              onClick={() => emit('toggle-status', row)}>
              {isPublished ? t('停用') : t('启用')}
            </bk-button>
            <bk-popover
              extCls="report-more-action-popover"
              placement="bottom-start"
              theme="light"
              trigger="click">
              {{
                default: () => (
                  <bk-button text class="more-action-btn">
                    <audit-icon type="more" />
                  </bk-button>
                ),
                content: () => (
                  <div class="more-action-menu">
                    <div
                      v-bk-tooltips={{
                        content: t('请先停用后再删除'),
                        disabled: !isPublished,
                        placement: 'bottom',
                      }}
                      class={['action-item danger', { disableddel: isPublished }]}
                      onClick={() => !isPublished && emit('delete', row)}>
                      {t('删除')}
                    </div>
                  </div>
                ),
              }}
            </bk-popover>
          </div>
        );
      },
    },
  ]);

  const handleRequestSuccess = (data: any) => {
    emit('request-success', data);
  };

  // 暴露刷新方法
  const fetchData = (params: Record<string, any>) => {
    listRef.value?.fetchData(params);
  };

  defineExpose({ fetchData });
</script>

<style lang="postcss" scoped>
  .action-cell {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .more-action-btn {
    padding: 0 4px;
    font-size: 16px;
    color: #979ba5;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }

  .report-config-list {
    :deep(.t-table) {
      border: none;
    }

    :deep(.t-table__row--hover) {
      background-color: #fff !important;
    }
  }

  :deep(.report-name-cell) {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
  }
</style>

<style lang="postcss">
  .report-more-action-popover.bk-popover.bk-pop2-content {
    padding: 0;
  }

  .more-action-menu {
    display: flex;
    flex-direction: column;
    min-width: 60px;

    .action-item {
      display: block;
      width: 100%;
      padding: 8px 15px;
      font-size: 12px;
      color: #63656e;
      cursor: pointer;

      &:hover {
        background-color: #f5f7fa;
      }

      &.danger {
        color: #ea3636;
      }

      &.disableddel {
        color: #c4c6cc;
        cursor: not-allowed;

        &:hover {
          color: #c4c6cc;
          background-color: transparent;
        }
      }
    }
  }

  /* 新建报表高亮 */
  .report-config-list .t-table tbody tr.is-new-created td {
    background-color: #e8fbf0 !important;
  }

  .report-config-list .t-table tbody tr.is-new-created:hover td {
    background-color: #d4f3e1 !important;
  }
</style>
