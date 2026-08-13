<template>
  <span
    v-show="false"
    aria-hidden="true">{{ activeJumpPopoverId }}{{ scopeOptionsLoading }}</span>
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

  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import type { PanelVisibilityType } from '@model/report-config/panel';

  import ReportJumpScopeMenu, {
    type JumpScopeItem,
  } from './report-jump-scope-menu.vue';

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
    default_value_overrides?: {
      default?: Record<string, any>;
      scenes?: Record<string, Record<string, any>>;
      systems?: Record<string, Record<string, any>>;
      use_bkvision_default?: Record<string, boolean>;
    };
  }

  interface SceneOption {
    id: number;
    name: string;
  }

  interface SystemOption {
    id: number;
    system_id?: string;
    name: string;
  }

  interface VisibilityScopeItem {
    type: 'scene' | 'system';
    id: number | string;
    name: string;
  }

  interface Props {
    highlightReportId?: string | null;
    dataSource: (params: any) => Promise<any>;
    sceneNameMap?: Record<string, string>;
    systemNameMap?: Record<string, string>;
    sceneOptions?: SceneOption[];
    systemOptions?: SystemOption[];
    /** 场景/系统选项加载中（跳转弹层首次打开展示 loading） */
    scopeOptionsLoading?: boolean;
  }

  interface Emits {
    (e: 'edit', row: ReportItem): void;
    (e: 'edit-visibility', row: ReportItem): void;
    (e: 'toggle-status', row: ReportItem): void;
    (e: 'delete', row: ReportItem): void;
    (e: 'request-success', data: any): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    highlightReportId: null,
    sceneNameMap: () => ({}),
    systemNameMap: () => ({}),
    sceneOptions: () => [],
    systemOptions: () => [],
    scopeOptionsLoading: false,
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const router = useRouter();
  const listRef = ref();
  const activeJumpPopoverId = ref<string | null>(null);
  const scopeOptionsLoading = computed(() => props.scopeOptionsLoading);

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  const {
    run: fetchReportDetail,
  } = useRequest(ToolManageService.fetchReportLists, {
    defaultValue: null,
  });

  // 新建行绿底高亮（与其它菜单一致使用 new-row；刷新后消失）
  // TDesign rowClassName 入参为 { row, rowIndex }，需兼容直接传 row 的情况
  const rowClassName = computed(() => {
    const highlightId = props.highlightReportId;
    return (params: Record<string, any>) => {
      if (!highlightId) return '';
      const rowData = params?.row || params;
      return String(rowData?.id) === String(highlightId) ? 'new-row' : '';
    };
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
    const editIcon = (
      <audit-icon
        class="visibility-edit-icon"
        type="edit-fill"
        onClick={(e: Event) => {
          e.stopPropagation();
          emit('edit-visibility', row);
        }} />
    );

    return (
      <span class="visibility-cell">
        {labels.length
          ? (
            <EditTag
              data={labels}
              key={row.id}
              showCopy={false}
              v-slots={{
                suffix: () => editIcon,
              }} />
          )
          : (
            <span class="visibility-empty">
              <span>--</span>
              {editIcon}
            </span>
          )}
      </span>
    );
  };

  const buildAllSceneScopes = (): VisibilityScopeItem[] => (
    props.sceneOptions.map(scene => ({
      type: 'scene' as const,
      id: scene.id,
      name: scene.name,
    }))
  );

  const buildAllSystemScopes = (): VisibilityScopeItem[] => (
    props.systemOptions.map(system => ({
      type: 'system' as const,
      id: system.system_id || String(system.id),
      name: system.name,
    }))
  );

  const buildSpecificSceneScopes = (sceneIds: Array<number | string>): VisibilityScopeItem[] => (
    sceneIds.map((id) => {
      const key = String(id);
      return {
        type: 'scene' as const,
        id,
        name: props.sceneNameMap[key] || `场景${id}`,
      };
    })
  );

  const buildSpecificSystemScopes = (systemIds: Array<number | string>): VisibilityScopeItem[] => (
    systemIds.map((id) => {
      const key = String(id);
      return {
        type: 'system' as const,
        id,
        name: props.systemNameMap[key] || `平台${id}`,
      };
    })
  );

  const isAllScenesVisibility = (row: ReportItem): boolean => {
    const {
      visibility_type: type,
      scene_ids: sceneIds,
      system_ids: systemIds,
    } = row;
    if (!type || type === 'all_systems' || type === 'specific_systems') return false;
    if (type === 'all_visible' || type === 'all_scenes') return true;
    if (type === 'scenes_and_systems') {
      const hasScenes = (sceneIds?.length ?? 0) > 0;
      const hasSystems = (systemIds?.length ?? 0) > 0;
      // 全部场景 + 指定系统：scene_ids 为空、system_ids 非空
      if (!hasScenes && hasSystems) return true;
    }
    if (props.sceneOptions.length > 0 && sceneIds?.length === props.sceneOptions.length) {
      return true;
    }
    return false;
  };

  const isAllSystemsVisibility = (row: ReportItem): boolean => {
    const {
      visibility_type: type,
      scene_ids: sceneIds,
      system_ids: systemIds,
    } = row;
    if (!type || type === 'all_scenes' || type === 'specific_scenes') return false;
    if (type === 'all_visible' || type === 'all_systems') return true;
    if (type === 'scenes_and_systems') {
      const hasScenes = (sceneIds?.length ?? 0) > 0;
      const hasSystems = (systemIds?.length ?? 0) > 0;
      // 指定场景 + 全部系统：scene_ids 非空、system_ids 为空
      if (hasScenes && !hasSystems) return true;
    }
    if (props.systemOptions.length > 0 && systemIds?.length === props.systemOptions.length) {
      return true;
    }
    return false;
  };

  // 解析可见范围为场景/系统列表，用于跳转交互（对齐工具管理）
  const getVisibilityScopeGroups = (row: ReportItem) => {
    const scenes: VisibilityScopeItem[] = [];
    const systems: VisibilityScopeItem[] = [];

    if (!row.visibility_type) {
      return { scenes, systems, totalCount: 0 };
    }

    const { scene_ids: sceneIds, system_ids: systemIds } = row;

    if (isAllScenesVisibility(row)) {
      scenes.push(...buildAllSceneScopes());
    } else if (sceneIds?.length) {
      scenes.push(...buildSpecificSceneScopes(sceneIds));
    }

    if (isAllSystemsVisibility(row)) {
      systems.push(...buildAllSystemScopes());
    } else if (systemIds?.length) {
      systems.push(...buildSpecificSystemScopes(systemIds));
    }

    return { scenes, systems, totalCount: scenes.length + systems.length };
  };

  const buildReportOpenQuery = (scope?: VisibilityScopeItem) => {
    if (!scope) return {};
    if (scope.type === 'scene') {
      const id = String(scope.id);
      return {
        scene_id: id,
        scope_id: id,
        scope_type: 'scene',
      };
    }
    const id = String(scope.id);
    return {
      scope_id: id,
      scope_type: 'system',
    };
  };

  const handleGoAuditReport = (row: ReportItem, scope?: VisibilityScopeItem) => {
    const routeData = router.resolve({
      name: 'statementManageDetail',
      params: { id: row.id },
      query: buildReportOpenQuery(scope),
    });
    window.open(routeData.href, '_blank');
  };

  const renderJumpScopeMenu = (
    row: ReportItem,
    scenes: VisibilityScopeItem[],
    systems: VisibilityScopeItem[],
  ) => (
    <ReportJumpScopeMenu
      loading={props.scopeOptionsLoading}
      scenes={scenes as JumpScopeItem[]}
      systems={systems as JumpScopeItem[]}
      onSelect={(scope: JumpScopeItem) => handleGoAuditReport(row, scope)} />
  );

  const renderJumpLink = (row: ReportItem) => {
    if (row.status !== 'published') return null;

    const { scenes, systems, totalCount } = getVisibilityScopeGroups(row);
    // 全部场景/系统在选项未就绪时 totalCount 可能为 0，仍需弹层展示 loading
    const waitingAllScopes = props.scopeOptionsLoading && (
      isAllScenesVisibility(row) || isAllSystemsVisibility(row)
    );
    const showScopePopover = totalCount > 1 || waitingAllScopes;
    const singleScope = totalCount === 1 ? (scenes[0] || systems[0]) : undefined;
    const isPopoverActive = activeJumpPopoverId.value === row.id;
    const jumpIcon = (
      <audit-icon
        v-bk-tooltips={t('点击查看审计报表')}
        class="jump-link"
        type="jump-link"
        onClick={!showScopePopover ? (e: Event) => {
          e.stopPropagation();
          handleGoAuditReport(row, singleScope);
        } : undefined} />
    );

    if (!showScopePopover) {
      return (
        <span class="hover-show-icon">
          {jumpIcon}
        </span>
      );
    }

    return (
      <bk-popover
        extCls="report-jump-scope-popover"
        placement="bottom-start"
        theme="light"
        trigger="click"
        width="240"
        onAfterShow={() => {
          activeJumpPopoverId.value = row.id;
        }}
        onAfterHidden={() => {
          if (activeJumpPopoverId.value === row.id) {
            activeJumpPopoverId.value = null;
          }
        }}>
        {{
          default: () => (
            <span
              class={[
                'report-jump-trigger',
                'hover-show-icon',
                { 'is-popover-active': isPopoverActive },
              ]}>
              {jumpIcon}
            </span>
          ),
          // 每次渲染重新解析 scopes，避免 loading 结束后列表不刷新
          content: () => {
            const latest = getVisibilityScopeGroups(row);
            return renderJumpScopeMenu(row, latest.scenes, latest.systems);
          },
        }}
      </bk-popover>
    );
  };

  // 跳转到 BKVision（对齐场景配置报表管理）
  const handleGoBkvision = async (row: ReportItem) => {
    if (!row.vision_id) return;
    const res = await fetchReportDetail({ share_uid: row.vision_id });
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    window.open(`${baseUrl}#/${row.bkvisionSpaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
  };

  const tableColumns = computed(() => {
    // 依赖选项加载状态，确保 loading / 列表变化时跳转列重新渲染
    void props.scopeOptionsLoading;
    void props.sceneOptions;
    void props.systemOptions;
    void props.sceneNameMap;
    void props.systemNameMap;

    return [
      {
        title: t('报表名称'),
        colKey: 'name',
        minWidth: 180,
        ellipsis: true,
        cell: (_h: any, { row }: { row: ReportItem }) => (
          <span class="report-name-cell">
            <span class="report-name-text">
              <Tooltips data={row.name} />
            </span>
            {renderJumpLink(row)}
          </span>
        ),
      },
      {
        title: t('报表描述'),
        colKey: 'description',
        minWidth: 160,
        ellipsis: true,
        cell: (_h: any, { row }: { row: ReportItem }) => (
          <span>{row.description || '--'}</span>
        ),
      },
      {
        title: t('BKVision 报表'),
        colKey: 'bkvisionReportName',
        width: 240,
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
        minWidth: 280,
        cell: (_h: any, { row }: { row: ReportItem }) => renderVisibilityContent(row),
      },
      {
        title: t('状态'),
        colKey: 'status',
        width: 100,
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
        width: 140,
        ellipsis: true,
      },
      {
        title: t('更新时间'),
        colKey: 'updated_at',
        width: 200,
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
        width: 120,
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
    ];
  });

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

    .visibility-edit-icon {
      flex-shrink: 0;
      font-size: 14px;
      color: #979ba5;
      cursor: pointer;
      visibility: hidden;

      &:hover {
        color: #3a84ff;
      }
    }

    .visibility-empty {
      display: inline-flex;
      gap: 4px;
      align-items: center;
    }

    &:hover {
      .visibility-edit-icon {
        visibility: visible;
      }
    }
  }

  :deep(.hover-show-icon) {
    visibility: hidden;
  }

  :deep(.hover-show-icon.is-popover-active),
  :deep(.report-jump-trigger[aria-expanded='true']) {
    visibility: visible;
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

  .report-jump-scope-popover.bk-popover.bk-pop2-content {
    width: 240px !important;
    max-width: 240px !important;
    min-width: 240px !important;
    padding: 0;
    overflow: hidden;
  }

  .report-jump-scope-popover.bk-popover.bk-pop2-content .bk-popover-content {
    max-height: none !important;
    overflow: hidden !important;
  }

</style>
