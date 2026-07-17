<template>
  <tdesign-list
    ref="listRef"
    class="report-config-list"
    :columns="tableColumns"
    :data-source="dataSource"
    need-empty-search-tip
    :row-class-name="rowClassName"
    row-key="id"
    @request-success="handleRequestSuccess" />
</template>

<script setup lang="tsx">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';

  import { formatDate } from '@utils/assist/timestamp-conversion';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import type { PanelVisibilityType } from '@model/report-config/panel';

  interface ReportItem {
    id: string;
    binding_type: string;
    name: string;
    description: string;
    vision_id: string;
    bkvisionReportName: string;
    bkvisionSpaceUid?: string;
    status: 'published' | 'unpublished';
    updated_by: string;
    updated_at: string;
    visibility_type?: PanelVisibilityType;
    scene_ids?: Array<number | string>;
    system_ids?: Array<number | string>;
  }

  interface Props {
    highlightReportId?: string | null;
    dataSource: (params: any) => Promise<any>;
    sceneNameMap?: Record<string, string>;
    systemNameMap?: Record<string, string>;
  }

  interface Emits {
    (e: 'edit', row: ReportItem): void;
    (e: 'toggle-status', row: ReportItem): void;
    (e: 'delete', row: ReportItem): void;
    (e: 'request-success', data: any): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    highlightReportId: null,
    sceneNameMap: () => ({}),
    systemNameMap: () => ({}),
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const router = useRouter();
  const listRef = ref();

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
  });

  const {
    run: fetchReportDetail,
  } = useRequest(ToolManageService.fetchReportLists, {
    defaultValue: null,
  });

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

  const getVisibilityLabels = (row: ReportItem) => {
    if (!row.visibility_type) {
      return [];
    }
    const { visibility_type: visibilityType, scene_ids: sceneIds, system_ids: systemIds } = row;

    if (visibilityType === 'all_visible') {
      return [t('全部可见')];
    }

    const labels: string[] = [];
    const isImplicitAllScenes = visibilityType === 'scenes_and_systems'
      && !(sceneIds?.length)
      && !!(systemIds?.length);
    const isImplicitAllSystems = visibilityType === 'scenes_and_systems'
      && !!(sceneIds?.length)
      && !(systemIds?.length);

    if (visibilityType === 'all_scenes' || isImplicitAllScenes) {
      labels.push(t('全部场景'));
    } else if (sceneIds && sceneIds.length > 0) {
      sceneIds.forEach((id: number | string) => {
        const key = String(id);
        labels.push(props.sceneNameMap[key] || `场景${id}`);
      });
    }

    if (visibilityType === 'all_systems' || isImplicitAllSystems) {
      labels.push(t('全部系统'));
    } else if (systemIds && systemIds.length > 0) {
      systemIds.forEach((id: number | string) => {
        const key = String(id);
        labels.push(props.systemNameMap[key] || `平台${id}`);
      });
    }

    return labels;
  };

  const renderVisibilityContent = (row: ReportItem) => {
    const labels = getVisibilityLabels(row);

    return (
      <span class="visibility-cell">
        {labels.length
          ? (
            <EditTag
              data={labels}
              key={row.id}
              showCopy={false} />
          )
          : <span>--</span>}
      </span>
    );
  };

  const handleGoAuditReport = (row: ReportItem) => {
    const routeData = router.resolve({
      name: 'statementManageDetail',
      params: { id: row.id },
      query: {
        scene_id: getSceneSystemParams().scope_id,
        scene_type: 'scene',
      },
    });
    window.open(routeData.href, '_blank');
  };

  const handleGoBkvision = async (row: ReportItem) => {
    if (!row.vision_id) return;
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    if (!baseUrl) return;

    try {
      const res = await fetchReportDetail({ share_uid: row.vision_id });
      if (res?.data?.dashboard_uid) {
        const spaceUid = row.bkvisionSpaceUid || '';
        window.open(`${baseUrl}#/${spaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
      }
    } catch (e) {
      console.error('获取报表详情失败:', e);
    }
  };

  const tableColumns = ref([
    {
      title: t('报表名称'),
      colKey: 'name',
      width: 180,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ReportItem }) => (
        <span class="report-name-cell">
          <span class="report-name-text">
            <Tooltips data={row.name} />
          </span>
          {row.status === 'published' && (
            <span class="hover-show-icon">
              <audit-icon
                v-bk-tooltips={t('点击查看审计报表')}
                class="jump-link"
                type="jump-link"
                onClick={(e: Event) => {
                  e.stopPropagation();
                  handleGoAuditReport(row);
                }} />
            </span>
          )}
        </span>
      ),
    },
    {
      title: t('报表描述'),
      colKey: 'description',
      width: 200,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ReportItem }) => (
        <span>{row.description || '--'}</span>
      ),
    },
    {
      title: t('BKVision 报表'),
      colKey: 'bkvisionReportName',
      width: 200,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ReportItem }) => (
        <span class="bkvision-report-cell">
          {row.bkvisionReportName
            ? (
              <>
                <span class="bkvision-report-text">
                  <Tooltips data={row.bkvisionReportName} />
                </span>
                <span class="hover-show-icon">
                  <audit-icon
                    v-bk-tooltips={t('跳转至BKVision查看')}
                    class="jump-link"
                    type="jump-link"
                    onClick={(e: Event) => {
                      e.stopPropagation();
                      handleGoBkvision(row);
                    }} />
                </span>
              </>
            )
            : <span>--</span>}
        </span>
      ),
    },
    {
      title: t('可见范围'),
      colKey: 'visibility',
      width: 220,
      cell: (_h: any, { row }: { row: ReportItem }) => renderVisibilityContent(row),
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

    :deep(.t-table td) {
      vertical-align: middle;
    }
  }

  :deep(.report-name-cell),
  :deep(.bkvision-report-cell) {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
  }

  :deep(.report-name-text),
  :deep(.bkvision-report-text) {
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;

    .show-tooltips-text {
      display: block;
    }
  }

  :deep(.jump-link) {
    flex-shrink: 0;
    padding-left: 4px;
    font-size: 14px;
    color: #3a84ff;
    cursor: pointer;
  }

  :deep(.visibility-cell) {
    display: block;
    max-width: 100%;
    overflow: hidden;
  }

  :deep(.hover-show-icon) {
    visibility: hidden;
  }

  :deep(tr:hover) {
    .hover-show-icon {
      visibility: visible;
    }
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
