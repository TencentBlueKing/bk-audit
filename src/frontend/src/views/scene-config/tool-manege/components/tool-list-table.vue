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
    is-need-scene-params
    use-skeleton
    need-empty-search-tip
    row-key="uid"
    :search-params="searchParams"
    @clear-search="handleClearSearch"
    @filter-change="handleFilterChange"
    @request-success="handleRequestSuccess" />
</template>

<script setup lang="tsx">
  import { computed, nextTick, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import ToolManageService from '@service/tool-manage';

  import useMessage from '@hooks/use-message';

  import { formatDate } from '@utils/assist/timestamp-conversion';

  import InlineTag from '@components/edit-box/inline-tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import { formatReferencedStrategyNames } from '@views/tool-manage-shared/strategy-reference';

  import { filterVirtualToolTags } from '@/utils/assist/filter-virtual-tags';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  // 工具类型枚举
  type ToolTypeKey = 'api' | 'data_search' | 'bk_vision' | 'smart_page';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

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
    status: 'published' | '';
    strategies: number[];
    tags: string[];
    visibility?: VisibilityInfo;
    created_at: string;
    created_by: string;
    updated_at: string;
    updated_by: string;
  }

  interface Props {
    searchParams: Record<string, any>;
    tagsEnums: TagItem[];
    strategyList: Array<{ label: string; value: number }>;
  }

  interface Emits {
    (e: 'edit', row: ToolModel): void;
    (e: 'preview', row: ToolModel): void;
    (e: 'delete', row: ToolModel): void;
    (e: 'toggle-status', row: ToolModel): void;
    (e: 'clear-search'): void;
    (e: 'request-success', data: any): void;
    (e: 'filter-change', filters: Record<string, any>): void;
    (e: 'tags-change'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const router = useRouter();

  const listRef = ref();
  const shouldHidePlatformDisabledTool = (tool: any) => tool.visibility?.binding_type === 'platform_binding'
    && tool.status !== 'published';
  // 适配器：将 fetchToolsList 返回的数组包装为 tdesign-list 期望的分页结构
  const dataSource = (params: any) => ToolManageService.fetchToolsList(params).then((list) => {
    const visibleList = list.filter(tool => !shouldHidePlatformDisabledTool(tool));
    const page = params?.page || 1;
    const pageSize = params?.page_size || 10;
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    return {
      results: visibleList.slice(start, end),
      page,
      num_pages: Math.ceil(visibleList.length / pageSize),
      total: visibleList.length,
    };
  });

  const toolType: Record<ToolTypeKey, string> = {
    api: t('API接口'),
    data_search: t('数据查询'),
    bk_vision: t('BKVision图表'),
    smart_page: t('智能用户画像'),
  };

  const toolTypeFilterList = (Object.keys(toolType) as ToolTypeKey[]).map(key => ({
    label: toolType[key],
    value: key,
  }));

  const isPlatformTool = (row: ToolModel) => row.visibility?.binding_type === 'platform_binding';

  const platformToolTooltip = t('平台工具不支持进行任何操作');

  // 保存标签后父组件重新拉取标签枚举前，用接口返回的新标签兜底展示
  const savedTagNameMap = ref<Record<string, string>>({});

  // 标签名称
  const returnTagsName = (tagId: string) => {
    let tagName = savedTagNameMap.value[tagId] || '';
    props.tagsEnums.forEach((item: TagItem) => {
      if (item.tag_id === tagId) {
        tagName = item.tag_name;
      }
    });
    return tagName;
  };

  const editingTagUid = ref('');
  const savingTagUid = ref('');
  const tagOptions = computed(() => filterVirtualToolTags(props.tagsEnums));

  const handleTagEdit = (row: ToolModel) => {
    editingTagUid.value = row.uid;
  };

  const handleTagEditCancel = () => {
    editingTagUid.value = '';
  };

  const handleTagSave = (row: ToolModel, tags: string[]) => {
    savingTagUid.value = row.uid;
    MetaManageService.saveTagBindings({
      resource_type: 'tool',
      resource_id: row.uid,
      tags,
    }).then((result) => {
      result.forEach((item) => {
        savedTagNameMap.value[String(item.tag_id)] = item.tag_name;
      });
      const targetRow = listRef.value?.getListData()?.find((item: ToolModel) => item.uid === row.uid);
      if (targetRow) {
        targetRow.tags = result.map(item => String(item.tag_id));
      }
      editingTagUid.value = '';
      messageSuccess(t('更新成功'));
      emit('tags-change');
    })
      .catch(() => undefined)
      .finally(() => {
        savingTagUid.value = '';
      });
  };

  const renderTagsContent = (row: ToolModel) => {
    const labels = (row.tags || []).map((tagId: string) => returnTagsName(tagId));
    return (
      <InlineTag
        editable={!isPlatformTool(row)}
        isEditing={editingTagUid.value === row.uid}
        key={row.uid}
        saving={savingTagUid.value === row.uid}
        showCopy={false}
        tagList={tagOptions.value}
        tags={labels}
        onCancel={handleTagEditCancel}
        onEdit={() => handleTagEdit(row)}
        onSave={(values: string[]) => handleTagSave(row, values)} />
    );
  };

  // 根据策略ID获取策略名称
  const getStrategyName = (strategyId: number) => {
    const strategy = props.strategyList.find(item => item.value === strategyId);
    return strategy ? strategy.label : `${strategyId}`;
  };

  // 策略跳转
  const handleStrategyClick = (strategyId: number) => {
    const sceneParams = getSceneSystemParams();
    const query: Record<string, string> = {
      strategy_id: String(strategyId),
    };
    // 携带场景信息
    if (sceneParams.scope_id) {
      query.scene_id = sceneParams.scope_id;
      query.scope_id = sceneParams.scope_id;
      query.scope_type = sceneParams.scope_type;
    } else if (sceneParams.scope_type) {
      query.scope_type = sceneParams.scope_type;
    }
    const url = router.resolve({
      name: 'strategyList',
      query,
    }).href;
    window.open(url, '_blank');
  };

  // 跳转至工具广场并打开该工具
  const handleOpenToolInSquare = (uid: string) => {
    const url = router.resolve({
      name: 'toolDetail',
      params: { uid },
    }).href;
    window.open(url, '_blank');
  };

  // 引用策略hover弹窗内容
  const renderStrategiesTooltipContent = (strategies: number[]) => (
    <div class="strategies-tooltip-content">
      {strategies.map((strategyId: number) => (
        <div
          class="strategy-item"
          onClick={() => handleStrategyClick(strategyId)}>
          <span class="strategy-name">
            {getStrategyName(strategyId)}（{strategyId}）
          </span>
          <audit-icon
            class="strategy-link-icon"
            type="jump-link" />
        </div>
      ))}
    </div>
  );

  const tableColumns = ref([
    {
      title: t('工具名称'),
      colKey: 'name',
      width: 400,
      fixed: 'left',
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span class="tool-name-cell">
          <span class="tool-name-text">
            <Tooltips data={row.name} />
          </span>
          {isPlatformTool(row) && (
            <bk-tag
              class="platform-binding-tag"
              radius="2px">
              {t('平台')}
            </bk-tag>
          )}
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
      minWidth: 400,
      ellipsis: true,
    },
    {
      title: t('工具类型'),
      colKey: 'tool_type',
      width: 140,
      ellipsis: true,
      filter: {
        type: 'multiple',
        showConfirmAndReset: true,
        resetValue: [],
        list: toolTypeFilterList,
      },
      cell: (h: any, { row }: { row: ToolModel }) => <span>
        {toolType[row.tool_type] || '--'}
        </span>,
    },
    {
      title: t('标签'),
      colKey: 'tags',
      width: 240,
      cell: (_h: any, { row }: { row: ToolModel }) => renderTagsContent(row),
    },
    {
      title: t('被引用'),
      colKey: 'strategies',
      width: 100,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => {
        if (!row.strategies || row.strategies.length === 0) {
          return <span>--</span>;
        }
        return (
          <bk-popover
            placement="bottom"
            theme="dark"
            trigger="hover">
            {{
              default: () => (
                <span class="strategies-count">
                  {row.strategies.length} {t('个')}
                </span>
              ),
              content: () => renderStrategiesTooltipContent(row.strategies),
            }}
          </bk-popover>
        );
      },
    },
    {
      title: t('状态'),
      colKey: 'status',
      width: 100,
      ellipsis: true,
      cell: (_h: any, { row }: { row: ToolModel }) => (
        <span>
          {row.status === 'published' ? (
            <bk-tag radius="4px" theme="success">{t('启用')}</bk-tag>
          ) : (
            <bk-tag radius="4px" theme="default">{t('停用')}</bk-tag>
          )}
        </span>
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
      width: 170,
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
      width: 150,
      fixed: 'right',
      cell: (_h: any, { row }: { row: ToolModel }) => {
        const isPlatform = isPlatformTool(row);
        const isEnabled = row.status === 'published';
        const referencedStrategyNames = formatReferencedStrategyNames(row.strategies, props.strategyList);
        const hasStrategies = Boolean(referencedStrategyNames);
        // 被策略引用的启用工具不可停用
        const isToggleDisabled = isPlatform || (isEnabled && hasStrategies);
        const toggleTooltip = isPlatform
          ? platformToolTooltip
          : t('该工具正在被{strategies}使用，无法停用', { strategies: referencedStrategyNames });
        // 删除按钮禁用条件：平台工具、启用状态或被策略引用
        const isDeleteDisabled = isPlatform || isEnabled || hasStrategies;
        // 删除按钮提示文字
        const getDeleteTooltip = () => {
          if (isPlatform) return platformToolTooltip;
          if (hasStrategies) return t('该工具正在被{strategies}使用，无法删除', { strategies: referencedStrategyNames });
          if (isEnabled) return t('请先停用后再删除');
          return '';
        };
        const deleteTooltip = getDeleteTooltip();

        return (
          <div class="action-cell">
            <bk-button
              v-bk-tooltips={{
                content: platformToolTooltip,
                disabled: !isPlatform,
                placement: 'top',
              }}
              text
              theme="primary"
              class={['mr8', isPlatform ? 'action-btn-disabled' : '']}
              disabled={isPlatform}
              onClick={() => !isPlatform && emit('edit', row)}>
              {t('编辑')}
            </bk-button>
            <bk-button
              text
              theme="primary"
              class="mr8"
              onClick={() => emit('preview', row)}>
              {t('预览')}
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
                    {isToggleDisabled ? (
                      <span
                        v-bk-tooltips={{
                          content: toggleTooltip,
                          placement: 'top',
                          extCls: 'tool-strategy-ref-tips',
                        }}>
                        <bk-button
                          text
                          disabled
                          class="mr8 mr8-disabled">
                          {isEnabled ? t('停用') : t('启用')}
                        </bk-button>
                      </span>
                    ) : (
                      <bk-button
                        text
                        class="mr8"
                        onClick={() => emit('toggle-status', row)}>
                        {isEnabled ? t('停用') : t('启用')}
                      </bk-button>
                    )}
                    {isDeleteDisabled ? (
                      <span
                        v-bk-tooltips={{
                          content: deleteTooltip,
                          placement: 'top',
                          extCls: 'tool-strategy-ref-tips',
                        }}>
                        <bk-button
                          text
                          disabled
                          class="mr8 mr8-disabled">
                          {t('删除')}
                        </bk-button>
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

  const handleFilterChange = (filters: Record<string, any>) => {
    emit('filter-change', filters);
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
  :deep(.tool-name-cell) {
    display: inline-flex;
    gap: var(--bk-theme-space-8);
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

  :deep(.platform-binding-tag.bk-tag) {
    flex-shrink: 0;
    height: 18px;
    padding: 0 var(--bk-theme-space-8);
    font-size: 12px;
    line-height: 18px;
    color: var(--bk-theme-text-default);
    background-color: var(--bk-theme-surface-muted);
    border: none;
    border-radius: var(--bk-theme-tag-radius);

    &:hover {
      color: var(--bk-theme-text-default);
      background-color: var(--bk-theme-surface-muted);
    }
  }

  .action-cell {
    display: flex;
    flex-wrap: nowrap;
    gap: var(--bk-theme-space-8);
    align-items: center;
    white-space: nowrap;

    .action-btn {
      margin-right: var(--bk-theme-space-8);
    }

    .more-action-btn {
      padding: 0 var(--bk-theme-space-4);
      font-size: 16px;
      color: var(--bk-theme-text-weak);
      cursor: pointer;

      &:hover {
        color: var(--bk-theme-color-brand-2);
      }
    }
  }

  .report-config-list {
    :deep(.t-table) {
      table-layout: fixed;
    }

    :deep(.t-table__row--hover) {
      background-color: var(--bk-theme-surface-default) !important;
    }
  }

  :deep(.jump-link) {
    flex-shrink: 0;
    padding-left: var(--bk-theme-space-4);
    font-size: 14px;
    color: var(--bk-theme-color-brand-2);
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
  .report-config-list .platform-binding-tag.bk-tag {
    flex-shrink: 0;
    height: 18px;
    padding: 0 var(--bk-theme-space-8);
    font-size: 12px;
    line-height: 18px;
    color: var(--bk-theme-text-default);
    background-color: var(--bk-theme-surface-muted);
    border: none;
    border-radius: var(--bk-theme-tag-radius);
  }

  .report-config-list .platform-binding-tag.bk-tag:hover {
    color: var(--bk-theme-text-default);
    background-color: var(--bk-theme-surface-muted);
  }

  .report-config-list .action-cell .action-btn-disabled.bk-button.bk-button-primary.is-text,
  .report-config-list .action-cell .action-btn-disabled.bk-button.bk-button-primary.is-text.is-disabled {
    color: var(--bk-theme-border-strong) !important;
    cursor: not-allowed;
  }

  .report-config-list .action-cell .action-btn-disabled.bk-button.bk-button-primary.is-text:hover,
  .report-config-list .action-cell .action-btn-disabled.bk-button.bk-button-primary.is-text.is-disabled:hover {
    color: var(--bk-theme-border-strong) !important;
  }

  .tool-more-action-popover.bk-popover.bk-pop2-content {
    padding: 0;
  }

  .tool-strategy-ref-tips {
    max-width: 400px;
    word-break: break-all;
    white-space: normal;
  }

  .more-action-menu {
    display: flex;
    flex-direction: column;
    min-width: 30px;

    .mr8 {
      display: block;
      width: 100%;padding: var(--bk-theme-space-8) var(--bk-theme-space-16);
      font-size: 12px;
      color: var(--bk-theme-text-default);

      &:hover {
        background-color: var(--bk-theme-surface-subtle);
      }
    }

    .mr8-disabled {
      color: var(--bk-theme-border-strong);

      &:hover {
        color: var(--bk-theme-border-strong);
        background-color: transparent;
      }
    }
  }

  .strategies-count {
    color: var(--bk-theme-text-default);
    cursor: pointer;
    border-bottom: 1px dashed var(--bk-theme-border-strong);
  }

  .strategies-tooltip-content {
    .strategy-item {
      display: flex;
      gap: var(--bk-theme-space-4);
      align-items: center;
      padding: var(--bk-theme-space-4) 0;
      cursor: pointer;
    }

    .strategy-name {
      color: var(--bk-theme-surface-default);
    }

    .strategy-link-icon {
      font-size: 16px;
      color: var(--bk-theme-color-brand-3);
    }
  }
</style>
