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

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  // 工具类型枚举
  type ToolTypeKey = 'api' | 'data_search' | 'bk_vision';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
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
  const dataSource = ToolManageService.fetchToolsList;

  const toolType: Record<ToolTypeKey, string> = {
    api: t('API接口'),
    data_search: t('数据查询'),
    bk_vision: t('BKVision图标'),
  };

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

  // 获取标签完整内容（用于 tooltip）
  const getTagsTooltipContent = (tags: string[]) => tags
    .slice(3)
    .map(tagId => returnTagsName(tagId))
    .join('、');

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
      width: 120,
      ellipsis: true,
    },
    {
      title: t('工具说明'),
      colKey: 'description',
      width: 200,
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
      width: 200,
      ellipsis: true,
      cell: (h: any, { row }: { row: ToolModel }) => (
        <div class="tags-cell">
          {row.tags && row.tags.length > 0 ? (
            <>
              {row.tags.slice(0, 3).map((tagId: string) => (
                <bk-tag class="desc-tag ml8">
                  {returnTagsName(tagId)}
                </bk-tag>
              ))}
              {row.tags.length > 3 && (
                <bk-tag
                  class="desc-tag ml8"
                  v-bk-tooltips={{
                    content: getTagsTooltipContent(row.tags),
                    placement: 'top',
                  }}>
                  + {row.tags.length - 3}
                </bk-tag>
              )}
            </>
          ) : (
            <span>--</span>
          )}
        </div>
      ),
    },
    {
      title: t('引用策略'),
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
      width: 80,
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
      width: 130,
      ellipsis: true,
    },
    {
      title: t('更新时间'),
      colKey: 'updated_at',
      width: 130,
      ellipsis: true,
    },
    {
      title: t('操作'),
      colKey: 'action',
      width: 90,
      fixed: 'right',
      cell: (_h: any, { row }: { row: ToolModel }) => {
        const isEnabled = row.status === 'published';
        const hasStrategies = row.strategies && row.strategies.length > 0;
        // 删除按钮禁用条件：启用状态或被策略引用
        const isDeleteDisabled = isEnabled || hasStrategies;
        // 删除按钮提示文字
        const getDeleteTooltip = () => {
          if (isEnabled) return t('请先停用后再删除');
          if (hasStrategies) return t('该工具已被策略引用，无法删除');
          return '';
        };
        const deleteTooltip = getDeleteTooltip();

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
                      text
                      class="mr8"
                      onClick={() => emit('toggle-status', row)}>
                      {isEnabled ? t('停用') : t('启用')}
                    </bk-button>
                    {isDeleteDisabled ? (
                      <span
                        v-bk-tooltips={{
                          content: deleteTooltip,
                          placement: 'bottom',
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
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
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
