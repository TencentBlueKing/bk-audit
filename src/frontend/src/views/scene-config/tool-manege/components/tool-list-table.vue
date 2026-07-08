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

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  // 工具类型枚举
  type ToolTypeKey = 'api' | 'data_search' | 'bk_vision';

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
  }

  const props = defineProps<Props>();
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

  const isPlatformTool = (row: ToolModel) => row.visibility?.binding_type === 'platform_binding';

  const platformToolTooltip = t('平台工具不支持进行任何操作');

  // 标签名称
  const returnTagsName = (tagId: string) => {
    let tagName = '';
    props.tagsEnums.forEach((item: TagItem) => {
      if (item.tag_id === tagId) {
        tagName = item.tag_name;
      }
    });
    return tagName;
  };

  const renderTagsContent = (tags: string[], rowKey: string) => {
    if (!tags || tags.length === 0) {
      return <span>--</span>;
    }
    const labels = tags.map((tagId: string) => returnTagsName(tagId));
    return <EditTag data={labels} key={rowKey} showCopy={false} />;
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
      minWidth: 200,
      ellipsis: true,
    },
    {
      title: t('工具类型'),
      colKey: 'tool_type',
      width: 200,
      ellipsis: true,
      cell: (h: any, { row }: { row: ToolModel }) => <span>
        {toolType[row.tool_type]}
        </span>,
    },
    {
      title: t('标签'),
      colKey: 'tags',
      width: 300,
      cell: (_h: any, { row }: { row: ToolModel }) => renderTagsContent(row.tags, row.uid),
    },
    {
      title: t('引用策略'),
      colKey: 'strategies',
      width: 150,
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
      width: 150,
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
      width: 150,
      ellipsis: true,
    },
    {
      title: t('更新时间'),
      colKey: 'updated_at',
      width: 200,
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
        const hasStrategies = row.strategies && row.strategies.length > 0;
        // 删除按钮禁用条件：平台工具、启用状态或被策略引用
        const isDeleteDisabled = isPlatform || isEnabled || hasStrategies;
        // 删除按钮提示文字
        const getDeleteTooltip = () => {
          if (isPlatform) return platformToolTooltip;
          if (isEnabled) return t('请先停用后再删除');
          if (hasStrategies) return t('该工具已被策略引用，无法删除');
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
                    <bk-button
                      v-bk-tooltips={{
                        content: platformToolTooltip,
                        disabled: !isPlatform,
                        placement: 'top',
                      }}
                      text
                      disabled={isPlatform}
                      class={['mr8', isPlatform ? 'mr8-disabled' : '']}
                      onClick={() => !isPlatform && emit('toggle-status', row)}>
                      {isEnabled ? t('停用') : t('启用')}
                    </bk-button>
                    {isDeleteDisabled ? (
                      <span
                        v-bk-tooltips={{
                          content: deleteTooltip,
                          placement: 'top',
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
    gap: 7px;
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
    padding: 0 8px;
    font-size: 12px;
    line-height: 18px;
    color: #63656e;
    background-color: #f0f1f5;
    border: none;
    border-radius: 2px;

    &:hover {
      color: #63656e;
      background-color: #f0f1f5;
    }
  }

  .action-cell {
    display: flex;
    flex-wrap: nowrap;
    gap: 8px;
    align-items: center;
    white-space: nowrap;

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
    :deep(.t-table) {
      table-layout: fixed;
    }

    :deep(.t-table__row--hover) {
      background-color: #fff !important;
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
  .report-config-list .platform-binding-tag.bk-tag {
    flex-shrink: 0;
    height: 18px;
    padding: 0 8px;
    font-size: 12px;
    line-height: 18px;
    color: #4d4f56;
    background-color: #f0f1f5;
    border: none;
    border-radius: 2px;
  }

  .report-config-list .platform-binding-tag.bk-tag:hover {
    color: #4d4f56;
    background-color: #f0f1f5;
  }

  .report-config-list .action-cell .action-btn-disabled.bk-button.bk-button-primary.is-text,
  .report-config-list .action-cell .action-btn-disabled.bk-button.bk-button-primary.is-text.is-disabled {
    color: #c4c6cc !important;
    cursor: not-allowed;
  }

  .report-config-list .action-cell .action-btn-disabled.bk-button.bk-button-primary.is-text:hover,
  .report-config-list .action-cell .action-btn-disabled.bk-button.bk-button-primary.is-text.is-disabled:hover {
    color: #c4c6cc !important;
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
  }

  .strategies-count {
    color: #4d4f56;
    cursor: pointer;
    border-bottom: 1px dashed #c4c6cc;
  }

  .strategies-tooltip-content {
    .strategy-item {
      display: flex;
      gap: 4px;
      align-items: center;
      padding: 4px 0;
      cursor: pointer;
    }

    .strategy-name {
      color: #fff;
    }

    .strategy-link-icon {
      font-size: 16px;
      color: #699df4;
    }
  }
</style>
