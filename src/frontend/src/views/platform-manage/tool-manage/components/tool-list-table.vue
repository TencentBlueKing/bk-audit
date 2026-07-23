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
  <span
    v-show="false"
    aria-hidden="true">{{ activeJumpPopoverUid }}</span>
  <tdesign-list
    ref="listRef"
    class="report-config-list"
    :columns="tableColumns"
    :data-source="dataSource"
    need-empty-search-tip
    row-key="uid"
    :search-params="searchParams"
    @clear-search="handleClearSearch"
    @request-success="handleRequestSuccess" />
</template>

<script setup lang="tsx">
  import {
    computed,
    defineComponent,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
    type PropType,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import { formatDate } from '@utils/assist/timestamp-conversion';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import sceneIconUrl from '@images/scene.svg';
  import systemIconUrl from '@images/system.svg';

  // 工具类型枚举
  type ToolTypeKey = 'api' | 'data_search' | 'bk_vision';

  // 可见范围接口定义
  interface VisibilityInfo {
    binding_type: string;
    visibility_type: string;
    scene_ids: Array<number | string>;
    system_ids: Array<number | string>;
  }

  // 工具模型接口定义
  interface ToolModel {
    id: string;
    uid: string;
    name: string;
    tool_type: ToolTypeKey;
    version: number;
    description: string;
    favorite: boolean;
    is_bkvision: boolean;
    namespace: string;
    status: 'published' | 'unpublished' | '';
    tags: string[];
    visibility: VisibilityInfo;
    strategies: number[];
    created_at: string;
    created_by: string;
    updated_at: string;
    updated_by: string;
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

  interface Props {
    searchParams: Record<string, any>;
    sceneNameMap?: Record<string, string>;
    systemNameMap?: Record<string, string>;
    sceneOptions?: SceneOption[];
    systemOptions?: SystemOption[];
  }

  interface Emits {
    (e: 'edit', row: ToolModel): void;
    (e: 'delete', row: ToolModel): void;
    (e: 'toggle-status', row: ToolModel): void;
    (e: 'edit-visibility', row: ToolModel): void;
    (e: 'clear-search'): void;
    (e: 'request-success', data: any): void;
    (e: 'status-counts', counts: { all: number; published: number; unpublished: number }): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    sceneNameMap: () => ({}),
    systemNameMap: () => ({}),
    sceneOptions: () => [],
    systemOptions: () => [],
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const router = useRouter();

  const listRef = ref();
  const activeJumpPopoverUid = ref<string | null>(null);
  // 适配器：将 fetchToolsList 返回的数组包装为 tdesign-list 期望的分页结构
  const dataSource = (params: any) => ToolManageService.fetchToolsList(params).then((list) => {
    const page = params?.page || 1;
    const pageSize = params?.page_size || 10;
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    // 复用完整列表数据计算状态统计，通知父组件
    emit('status-counts', {
      all: list.length,
      published: list.filter((item: any) => item.status === 'published').length,
      unpublished: list.filter((item: any) => item.status === 'unpublished').length,
    });
    return {
      results: list.slice(start, end),
      page,
      num_pages: Math.ceil(list.length / pageSize),
      total: list.length,
    };
  });

  const toolType: Record<ToolTypeKey, string> = {
    api: t('API接口'),
    data_search: t('数据查询'),
    bk_vision: t('BKVision图表'),
  };

  const formatCellText = (value: unknown) => {
    if (value === null || value === undefined || value === '') {
      return '--';
    }
    return String(value);
  };

  // 根据可见范围信息组装标签文案（场景 + 平台/系统）
  // 后端 visibility_type 枚举值：
  //   all_visible=全部可见, all_scenes=全部场景, all_systems=全部系统,
  //   specific_scenes=指定场景, specific_systems=指定系统, scenes_and_systems=场景和系统
  const getVisibilityLabels = (visibility: VisibilityInfo) => {
    if (!visibility || !visibility.visibility_type) {
      return [];
    }
    const { visibility_type: visibilityType, scene_ids: sceneIds, system_ids: systemIds } = visibility;

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

  const renderVisibilityContent = (row: ToolModel) => {
    const labels = getVisibilityLabels(row.visibility);
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
              key={row.uid}
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

  interface VisibilityScopeItem {
    type: 'scene' | 'system';
    id: number | string;
    name: string;
  }

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

  const isAllScenesVisibility = (visibility: VisibilityInfo): boolean => {
    const { visibility_type: type, scene_ids: sceneIds, system_ids: systemIds } = visibility;
    if (type === 'all_systems') return false;
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

  const isAllSystemsVisibility = (visibility: VisibilityInfo): boolean => {
    const { visibility_type: type, scene_ids: sceneIds, system_ids: systemIds } = visibility;
    if (type === 'all_scenes') return false;
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

  // 解析可见范围为场景/系统列表，用于跳转交互
  // 全部场景/全部系统/全部可见会展开为完整列表，与工具广场跨场景/跨系统分组逻辑一致
  const getVisibilityScopeGroups = (visibility: VisibilityInfo) => {
    const scenes: VisibilityScopeItem[] = [];
    const systems: VisibilityScopeItem[] = [];

    if (!visibility?.visibility_type) {
      return { scenes, systems, totalCount: 0 };
    }

    const { scene_ids: sceneIds, system_ids: systemIds } = visibility;

    if (isAllScenesVisibility(visibility)) {
      scenes.push(...buildAllSceneScopes());
    } else if (sceneIds?.length) {
      scenes.push(...buildSpecificSceneScopes(sceneIds));
    }

    if (isAllSystemsVisibility(visibility)) {
      systems.push(...buildAllSystemScopes());
    } else if (systemIds?.length) {
      systems.push(...buildSpecificSystemScopes(systemIds));
    }

    return { scenes, systems, totalCount: scenes.length + systems.length };
  };

  const buildToolOpenQuery = (scope?: VisibilityScopeItem) => {
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

  // 跳转至工具广场并打开该工具
  const handleOpenToolInSquare = (uid: string, scope?: VisibilityScopeItem) => {
    const url = router.resolve({
      name: 'toolDetail',
      params: { uid },
      query: buildToolOpenQuery(scope),
    }).href;
    window.open(url, '_blank');
  };

  const JumpScopeMenu = defineComponent({
    name: 'JumpScopeMenu',
    props: {
      row: {
        type: Object as PropType<ToolModel>,
        required: true,
      },
      scenes: {
        type: Array as PropType<VisibilityScopeItem[]>,
        default: () => [],
      },
      systems: {
        type: Array as PropType<VisibilityScopeItem[]>,
        default: () => [],
      },
    },
    setup(props) {
      const { t } = useI18n();
      const searchKeyword = ref('');
      const menuRef = ref<HTMLElement | null>(null);
      const showScrollbar = ref(false);
      const thumbHeight = ref(0);
      const thumbTop = ref(0);
      let menuResizeObserver: ResizeObserver | null = null;

      const normalizedKeyword = computed(() => searchKeyword.value.trim().toLowerCase());

      const filterItems = (items: VisibilityScopeItem[]) => {
        const keyword = normalizedKeyword.value;
        if (!keyword) return items;
        return items.filter(item => item.name.toLowerCase().includes(keyword));
      };

      const filteredScenes = computed(() => filterItems(props.scenes));
      const filteredSystems = computed(() => filterItems(props.systems));
      const isEmpty = computed(() => !filteredScenes.value.length && !filteredSystems.value.length);

      const updateScrollbar = () => {
        const el = menuRef.value;
        if (!el) {
          showScrollbar.value = false;
          return;
        }
        const { scrollHeight, clientHeight, scrollTop } = el;
        if (scrollHeight <= clientHeight + 1) {
          showScrollbar.value = false;
          return;
        }
        showScrollbar.value = true;
        const minThumbHeight = 24;
        thumbHeight.value = Math.max(clientHeight * (clientHeight / scrollHeight), minThumbHeight);
        const maxThumbTop = clientHeight - thumbHeight.value;
        const scrollRatio = scrollTop / (scrollHeight - clientHeight);
        thumbTop.value = maxThumbTop * scrollRatio;
      };

      watch([filteredScenes, filteredSystems, normalizedKeyword], () => {
        nextTick(updateScrollbar);
      });

      onMounted(() => {
        nextTick(() => {
          updateScrollbar();
          if (menuRef.value) {
            menuResizeObserver = new ResizeObserver(() => updateScrollbar());
            menuResizeObserver.observe(menuRef.value);
          }
        });
      });

      onBeforeUnmount(() => {
        menuResizeObserver?.disconnect();
      });

      const renderScopeItem = (scope: VisibilityScopeItem) => (
        <div
          class="jump-scope-item"
          key={`${scope.type}-${scope.id}`}
          onClick={(e: Event) => {
            e.stopPropagation();
            handleOpenToolInSquare(props.row.uid, scope);
          }}>
          <img
            alt=""
            class={[
              'jump-scope-item-icon',
              scope.type === 'scene' ? 'scene-icon' : 'system-icon',
            ]}
            src={scope.type === 'scene' ? sceneIconUrl : systemIconUrl} />
          <span class="jump-scope-item-content">
            <span class="jump-scope-item-name">
              <Tooltips data={scope.name} />
            </span>
            <audit-icon
              class="jump-scope-link-icon"
              type="jump-link" />
          </span>
        </div>
      );

      return () => (
        <div class="tool-jump-scope-menu-outer">
          <div
            class="jump-scope-search"
            onMousedown={(e: Event) => e.stopPropagation()}>
            <span class="search-prefix-wrap">
              <audit-icon
                class="search-prefix"
                type="search1" />
            </span>
            <bk-input
              behavior="simplicity"
              clearable
              modelValue={searchKeyword.value}
              placeholder={t('搜索')}
              onUpdate:modelValue={(val: string) => {
                searchKeyword.value = val;
              }} />
          </div>
          <div class="tool-jump-scope-menu-wrap">
            <div
              ref={menuRef}
              class="tool-jump-scope-menu"
              onScroll={updateScrollbar}>
              {filteredScenes.value.length > 0 && (
                <div class="jump-scope-section">
                  <div class="jump-scope-section-title">{t('所属场景')}</div>
                  {filteredScenes.value.map(scene => renderScopeItem(scene))}
                </div>
              )}
              {filteredSystems.value.length > 0 && (
                <div class="jump-scope-section">
                  <div class="jump-scope-section-title">{t('所属系统')}</div>
                  {filteredSystems.value.map(system => renderScopeItem(system))}
                </div>
              )}
              {isEmpty.value && (
                <div class="jump-scope-empty">{t('无匹配数据')}</div>
              )}
            </div>
            {showScrollbar.value && (
              <div
                aria-hidden="true"
                class="jump-scope-scrollbar-track">
                <div
                  class="jump-scope-scrollbar-thumb"
                  style={{
                    height: `${thumbHeight.value}px`,
                    transform: `translateY(${thumbTop.value}px)`,
                  }} />
              </div>
            )}
          </div>
        </div>
      );
    },
  });

  const renderJumpLink = (row: ToolModel) => {
    if (row.status !== 'published') return null;

    const { scenes, systems, totalCount } = getVisibilityScopeGroups(row.visibility);
    const singleScope = totalCount === 1 ? (scenes[0] || systems[0]) : undefined;
    const isPopoverActive = activeJumpPopoverUid.value === row.uid;
    const jumpIcon = (
      <audit-icon
        v-bk-tooltips={t('点击查看工具')}
        class="jump-link"
        type="jump-link"
        onClick={totalCount <= 1 ? (e: Event) => {
          e.stopPropagation();
          handleOpenToolInSquare(row.uid, singleScope);
        } : undefined} />
    );

    if (totalCount <= 1) {
      return (
        <span class="hover-show-icon">
          {jumpIcon}
        </span>
      );
    }

    return (
      <bk-popover
        extCls="tool-jump-scope-popover"
        placement="bottom-start"
        theme="light"
        trigger="click"
        width="240"
        onAfterShow={() => {
          activeJumpPopoverUid.value = row.uid;
        }}
        onAfterHidden={() => {
          if (activeJumpPopoverUid.value === row.uid) {
            activeJumpPopoverUid.value = null;
          }
        }}>
        {{
          default: () => (
            <span
              class={[
                'tool-jump-trigger',
                'hover-show-icon',
                { 'is-popover-active': isPopoverActive },
              ]}>
              {jumpIcon}
            </span>
          ),
          content: () => (
            <JumpScopeMenu
              row={row}
              scenes={scenes}
              systems={systems} />
          ),
        }}
      </bk-popover>
    );
  };

  const tableColumns = ref([
    {
      title: t('工具名称'),
      colKey: 'name',
      width: 250,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span class="tool-name-cell">
          <span class="tool-name-text">
            <Tooltips data={formatCellText(row.name)} />
          </span>
          {renderJumpLink(row)}
        </span>
      ),
    },
    {
      title: t('工具说明'),
      colKey: 'description',
      width: 450,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>{formatCellText(row.description)}</span>
      ),
    },
    {
      title: t('工具类型'),
      colKey: 'tool_type',
      width: 150,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>{toolType[row.tool_type] || '--'}</span>
      ),
    },
    {
      title: t('可见范围'),
      colKey: 'visibility',
      width: 400,
      cell: (_h: any, { row }: { row: ToolModel }) => renderVisibilityContent(row),
    },
    {
      title: t('状态'),
      colKey: 'status',
      width: 120,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>
          {row.status === 'published' ? (
            <bk-tag radius="4px" theme="success">{t('已上架')}</bk-tag>
          ) : (
            <bk-tag radius="4px" theme="default">{t('未上架')}</bk-tag>
          )}
        </span>
      ),
    },
    {
      title: t('更新人'),
      colKey: 'updated_by',
      width: 120,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>{formatCellText(row.updated_by)}</span>
      ),
    },
    {
      title: t('更新时间'),
      colKey: 'updated_at',
      width: 150,
      ellipsis: true,
      sortType: 'all',
      sorter: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>{row.updated_at ? formatDate(row.updated_at) : '--'}</span>
      ),
    },
    {
      title: t('操作'),
      colKey: 'action',
      width: 120,
      fixed: 'right',
      cell: (_h: any, { row }: { row: ToolModel }) => {
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
              {isPublished ? t('下架') : t('上架')}
            </bk-button>
            <bk-popover
              extCls="tool-more-action-popover"
              placement="bottom-start"
              theme="light"
              trigger="click">
              {{
                default: () => (
                  <bk-button
                    text
                    class="more-action-btn">
                    <audit-icon type="more" />
                  </bk-button>
                ),
                content: () => (
                  <div class="more-action-menu">
                    {isPublished ? (
                      <span
                        v-bk-tooltips={{
                          content: t('请先下架后再删除'),
                          placement: 'bottom',
                        }}>
                        <span class="delete-disabled">{t('删除')}</span>
                      </span>
                    ) : (
                      <bk-button
                        text
                        class="mr8"
                        onClick={() => emit('delete', row)}>
                        {t('删除')}
                      </bk-button>
                    )}
                  </div>
                ),
              }}
            </bk-popover>
          </div>
        );
      },
    },
  ]);

  const handleClearSearch = () => {
    emit('clear-search');
  };

  const handleRequestSuccess = (data: any) => {
    emit('request-success', data);
    // 新建行绿底高亮（基于 sessionStorage 中记录的 ID）
    nextTick(() => {
      highlightNewRows(data?.results || []);
    });
  };

  // sessionStorage key：记录新建工具 uid（刷新后消失）
  const STORAGE_KEY_NEW_TOOLS = 'tool_manage_new_uids';

  // 获取新建工具 ID 列表
  const getNewUids = (): Set<string> => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY_NEW_TOOLS);
      return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
    } catch { /* ignore */ }
    return new Set();
  };

  // 判断是否是新建数据（ID 在 sessionStorage 的记录中）
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const isNewData = (item: ToolModel) => getNewUids().has(item.uid);

  // 给新建的行添加绿底背景（高亮后清除该 ID，避免重复高亮）
  const highlightNewRows = (list: ToolModel[]) => {
    setTimeout(() => {
      const newUids = getNewUids();
      list.forEach((item, index) => {
        if (newUids.has(item.uid)) {
          const rows = document.querySelectorAll('.report-config-list .t-table__body tr');
          const row = rows[index];
          if (row) {
            /* eslint-disable no-param-reassign */
            Array.from(row.querySelectorAll('td')).forEach((tdEl: HTMLElement) => {
              tdEl.style.background = '#f2fff4';
            });
            /* eslint-enable no-param-reassign */
          }
        }
      });
      // 高亮完成后清除记录
      try {
        sessionStorage.removeItem(STORAGE_KEY_NEW_TOOLS);
      } catch { /* ignore */ }
    }, 100);
  };

  // 暴露刷新方法
  const fetchData = (params: Record<string, any>) => {
    listRef.value.fetchData(params);
  };

  // 初始列表请求由父组件统一发起（含排序与搜索恢复），避免与缓存搜索条件竞态

  defineExpose({ fetchData });
</script>

<style lang="postcss" scoped>
  :deep(.tool-name-cell) {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
  }

  :deep(.tool-name-text) {
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;

    .show-tooltips-text {
      display: block;
    }
  }

  .action-cell {
    display: flex;
    gap: 16px;
    align-items: center;

    .action-btn {
      margin-right: 8px;
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
  }

  .report-config-list {
    :deep(.t-table__row--hover) {
      background-color: #fff !important;
    }

    :deep(.t-table td) {
      vertical-align: middle;
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
  :deep(.tool-jump-trigger[aria-expanded='true']) {
    visibility: visible;
  }

  :deep(tr:hover) {
    .hover-show-icon {
      visibility: visible;
    }
  }
</style>

<style lang="postcss">
  .tool-jump-scope-popover.bk-popover.bk-pop2-content {
    width: 240px !important;
    max-width: 240px !important;
    min-width: 240px !important;
    padding: 0;
    overflow: hidden;
  }

  .tool-jump-scope-popover.bk-popover.bk-pop2-content .bk-popover-content {
    max-height: none !important;
    overflow: hidden !important;
  }

  .tool-jump-scope-menu-outer {
    display: flex;
    flex-direction: column;
    width: 240px;
    max-height: 320px;
    overflow: hidden;
  }

  .tool-jump-scope-popover .jump-scope-search {
    display: flex;
    flex-shrink: 0;
    padding: 4px 0 0;
    margin: 0 12px;
    background: #fff;
    border-bottom: 1px solid #dcdee5;
    align-items: center;

    .bk-input {
      background: #fff !important;
      border: none !important;
      box-shadow: none !important;
      flex: 1;
    }

    .bk-input--text,
    .bk-input--default,
    .bk-input-text,
    input {
      background: #fff !important;
      background-color: #fff !important;
    }

    .bk-input--suffix-icon {
      background-color: #fff !important;
    }

    .bk-input.is-simplicity:hover:not(.is-disabled) {
      background-color: #fff !important;
      border-color: transparent !important;
      border-bottom-color: #dcdee5 !important;
      box-shadow: none !important;
    }

    .bk-input.is-simplicity:hover:not(.is-disabled) .bk-input--text,
    .bk-input.is-simplicity:hover:not(.is-disabled) .bk-input--suffix-icon {
      background-color: #fff !important;
    }

    .bk-input.is-focused:not(.is-readonly).is-simplicity .bk-input--text,
    .bk-input.is-focused:not(.is-readonly).is-simplicity .bk-input--suffix-icon {
      background-color: #fff !important;
    }

    .bk-input--suffix-icon:hover {
      color: #979ba5 !important;
      background-color: #fff !important;
    }
  }

  .tool-jump-scope-popover .search-prefix-wrap {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    margin-right: 4px;
    background: transparent;

    .search-prefix {
      font-size: 18px;
      line-height: 1;
      color: #979ba5;
    }
  }

  .tool-jump-scope-menu-wrap {
    position: relative;
    min-height: 0;
    overflow: hidden;
    flex: 1 1 auto;
  }

  .tool-jump-scope-menu {
    width: 100%;
    max-height: 272px;
    min-height: 0;
    padding: 4px 0;
    overflow: hidden auto;
    box-sizing: border-box;
    -ms-overflow-style: none;
    scrollbar-width: none;
  }

  .tool-jump-scope-menu::-webkit-scrollbar {
    display: none;
    width: 0;
    height: 0;
  }

  .jump-scope-scrollbar-track {
    position: absolute;
    top: 0;
    right: 2px;
    width: 4px;
    height: 100%;
    pointer-events: none;
  }

  .jump-scope-scrollbar-thumb {
    width: 4px;
    background-color: #c4c6cc;
    border-radius: 2px;
    transition: background-color .2s;
  }

  .tool-jump-scope-menu-wrap:hover .jump-scope-scrollbar-thumb {
    background-color: #979ba5;
  }

  .jump-scope-empty {
    padding: 16px 12px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
    text-align: center;
  }

  .jump-scope-section-title {
    padding: 8px 12px 4px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  .jump-scope-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;

    &:hover {
      background-color: #f5f7fa;

      .jump-scope-link-icon {
        visibility: visible;
      }
    }
  }

  .jump-scope-item-icon {
    flex-shrink: 0;
    width: 16px;
    height: 16px;
  }

  .jump-scope-item-name {
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;
    font-size: 12px;
    line-height: 20px;
    color: #313238;

    .show-tooltips-text {
      display: block;
    }
  }

  .jump-scope-item-content {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    overflow: hidden;
  }

  .jump-scope-link-icon {
    flex-shrink: 0;
    font-size: 14px;
    color: #3a84ff;
    visibility: hidden;
  }

  .tool-more-action-popover.bk-popover.bk-pop2-content {
    padding: 0;
  }

  .more-action-menu {
    display: flex;
    flex-direction: column;
    min-width: 30px;

    .mr8 {
      display: block;
      width: 100%;
      padding: 8px 15px;
      font-size: 12px;
      color: #63656e;

      &:hover {
        background-color: #f5f7fa;
      }
    }

    .mr8-disabled {
      color: #c4c6cc;

      &:hover {
        color: #c4c6cc;
        background-color: transparent;
      }
    }

    .delete-disabled {
      display: block;
      width: 100%;
      padding: 8px 15px;
      font-size: 12px;
      color: #c4c6cc;
      cursor: not-allowed;

      &:hover {
        background-color: transparent;
      }
    }
  }
</style>
