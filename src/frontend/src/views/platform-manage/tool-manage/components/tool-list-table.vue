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
  import { nextTick, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import { formatDate } from '@utils/assist/timestamp-conversion';

  import Tooltips from '@components/show-tooltips-text/index.vue';

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
    visibility: VisibilityInfo;
    strategies: number[];
    created_at: string;
    created_by: string;
    updated_at: string;
    updated_by: string;
  }

  interface Props {
    searchParams: Record<string, any>;
    sceneNameMap?: Record<string, string>;
    systemNameMap?: Record<string, string>;
  }

  interface Emits {
    (e: 'edit', row: ToolModel): void;
    (e: 'delete', row: ToolModel): void;
    (e: 'toggle-status', row: ToolModel): void;
    (e: 'clear-search'): void;
    (e: 'request-success', data: any): void;
    (e: 'status-counts', counts: { all: number; published: number; unpublished: number }): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    sceneNameMap: () => ({}),
    systemNameMap: () => ({}),
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const router = useRouter();

  const listRef = ref();
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
    bk_vision: t('BKVision图标'),
  };

  const formatCellText = (value: unknown) => {
    if (value === null || value === undefined || value === '') {
      return '--';
    }
    return String(value);
  };

  // 根据可见范围信息渲染内容（场景 + 平台/系统）
  // 后端 visibility_type 枚举值：
  //   all_visible=全部可见, all_scenes=全部场景, all_systems=全部系统,
  //   specific_scenes=指定场景, specific_systems=指定系统, scenes_and_systems=场景和系统
  const MAX_VISIBLE_TAGS = 2;
  const renderVisibilityContent = (visibility: VisibilityInfo) => {
    if (!visibility || !visibility.visibility_type) {
      return <span>--</span>;
    }
    const { visibility_type: visibilityType, scene_ids: sceneIds, system_ids: systemIds } = visibility;

    // 全部可见
    if (visibilityType === 'all_visible') {
      return (
        <div class="tags-cell">
          <bk-tag
            class="desc-tag ml8"
            radius="4px"
            theme="default">
            {t('全部可见')}
          </bk-tag>
        </div>
      );
    }

    // 合并场景和系统标签
    const allTags: Array<{ label: string }> = [];

    // 全部场景
    if (visibilityType === 'all_scenes') {
      allTags.push({ label: t('全部场景') });
    } else if (sceneIds && sceneIds.length > 0) {
      // 指定场景 / 场景和系统：逐个展示场景
      sceneIds.forEach((id: number | string) => {
        const key = String(id);
        allTags.push({ label: props.sceneNameMap[key] || `场景${id}` });
      });
    }

    // 全部系统
    if (visibilityType === 'all_systems') {
      allTags.push({ label: t('全部系统') });
    } else if (systemIds && systemIds.length > 0) {
      // 指定系统 / 场景和系统：逐个展示系统
      systemIds.forEach((id: number | string) => {
        const key = String(id);
        allTags.push({ label: props.systemNameMap[key] || `平台${id}` });
      });
    }

    if (allTags.length === 0) {
      return <span>--</span>;
    }

    const visibleTags = allTags.slice(0, MAX_VISIBLE_TAGS);
    const overflowTags = allTags.slice(MAX_VISIBLE_TAGS);

    return (
      <div class="tags-cell">
        {visibleTags.map(tag => (
          <bk-tag
            class="desc-tag ml8"
            radius="4px"
            theme="default">
            {tag.label}
          </bk-tag>
        ))}
        {overflowTags.length > 0 && (
          <bk-tag
            class="desc-tag ml8"
            radius="4px"
            theme="default"
            v-bk-tooltips={{
              content: overflowTags.map(t => t.label).join('、'),
              placement: 'top',
            }}>
            + {overflowTags.length}
          </bk-tag>
        )}
      </div>
    );
  };

  // 跳转至工具广场并打开该工具
  const handleOpenToolInSquare = (uid: string) => {
    const url = router.resolve({
      name: 'toolDetail',
      params: { uid },
    }).href;
    window.open(url, '_blank');
  };

  const tableColumns = ref([
    {
      title: t('工具名称'),
      colKey: 'name',
      width: 120,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span class="tool-name-cell">
          <span class="tool-name-text">
            <Tooltips data={formatCellText(row.name)} />
          </span>
          {row.status === 'published' && (
            <audit-icon
              v-bk-tooltips={t('点击查看工具')}
              class="jump-link hover-show-icon"
              type="jump-link"
              onClick={(e: Event) => {
                e.stopPropagation();
                handleOpenToolInSquare(row.uid);
              }} />
          )}
        </span>
      ),
    },
    {
      title: t('工具说明'),
      colKey: 'description',
      width: 200,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>{formatCellText(row.description)}</span>
      ),
    },
    {
      title: t('工具类型'),
      colKey: 'tool_type',
      width: 200,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>{toolType[row.tool_type] || '--'}</span>
      ),
    },
    {
      title: t('可见范围'),
      colKey: 'visibility',
      width: 200,
      cell: (_h: any, { row }: { row: ToolModel }) => renderVisibilityContent(row.visibility),
    },
    {
      title: t('状态'),
      colKey: 'status',
      width: 80,
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
      width: 130,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>{formatCellText(row.updated_by)}</span>
      ),
    },
    {
      title: t('更新时间'),
      colKey: 'updated_at',
      width: 180,
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
      width: 140,
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

  // 组件初始化后，立即带排序参数重新请求（覆盖 tdesign-list 的默认无排序请求）
  onMounted(() => {
    nextTick(() => {
      listRef.value?.fetchData({ sort: ['-created_at'] });
    });
  });

  defineExpose({ fetchData });
</script>

<style lang="postcss" scoped>
  .tags-cell {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
    line-height: 1;
    vertical-align: middle;
  }

  :deep(.tags-cell > *) {
    display: inline-flex;
    align-items: center;
    flex-shrink: 0;
  }

  :deep(.tags-cell .desc-tag) {
    font-size: 12px;
    font-weight: 500;
    line-height: 22px;
  }

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
