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
  <skeleton-loading
    fullscreen
    :loading="isLoading"
    name="storageList">
    <div class="report-config">
      <!-- 头部操作区 -->
      <div class="report-config-header">
        <div class="header-left">
          <bk-button
            class="mr8"
            theme="primary"
            @click="handleCreateReport">
            <audit-icon
              class="mr4"
              type="plus-circle" />
            {{ t('新建报表') }}
          </bk-button>
        </div>
        <div class="header-right">
          <bk-input
            v-model="searchKeyword"
            class="search-input"
            clearable
            :placeholder="t('搜索 工具名称、工具说明、工具类型、工具来源、更新人')"
            type="search"
            @clear="handleSearch"
            @enter="handleSearch" />
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="report-config-content">
        <tdesign-list
          ref="listRef"
          class="report-config-list"
          :columns="tableColumns"
          :data-source="dataSource"
          need-empty-search-tip
          row-key="risk_id"
          :search-params="searchModel"
          secondary-sort-field="-event_time"
          @clear-search="handleClearSearch"
          @request-success="handleRequestSuccess" />
      </div>
    </div>
  </skeleton-loading>
</template>

<script setup lang='tsx'>
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import useRequest from '@hooks/use-request';

  // 工具类型枚举
  type ToolTypeKey = 'api' | 'data_search' | 'bk_vision';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

  // 工具模型接口定义
  interface toolModel {
    uid: string;
    name: string;
    tool_type: ToolTypeKey;
    version: number;
    description: string;
    favorite: boolean;
    is_bkvision: boolean;
    namespace: string;
    status: 'enabled' | 'disabled'; // 启用/停用状态
    permission: {
      use_tool: boolean;
      manage_tool: boolean;
    };
    strategies: number[];
    tags: string[];
    created_at: string;
    created_by: string;
    updated_at: string;
    updated_by: string;
  }

  const { t } = useI18n();
  const router = useRouter();

  const isLoading = ref(true);
  const searchKeyword = ref('');
  const listRef = ref();
  const dataSource = ToolManageService.fetchToolsList;
  const searchModel = ref<Record<string, any>>({});
  const toolType: Record<ToolTypeKey, string> = {
    api: t('API接口'),
    data_search: t('数据查询'),
    bk_vision: t('BKVision图标'),
  };
  const tagsEnums = ref<Array<TagItem>>([]);
  // 标签名称
  const returnTagsName = (tagId: string) => {
    let tagName = '';
    tagsEnums.value.forEach((item: TagItem) => {
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
      cell: (h: any, { row }: { row: toolModel }) => <span>
        {toolType[row.tool_type]}
        </span>,
    },
    {
      title: t('标签'),
      colKey: 'tags',
      width: 200,
      ellipsis: true,
      cell: (h: any, { row }: { row: toolModel }) => (
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
      cell: (h: any, { row }: { row: toolModel }) => <span>
        {row.strategies.length} 个
        </span>,
    },
    {
      title: t('状态'),
      colKey: 'strategies',
      width: 80,
      ellipsis: true,
      cell: () => <span>
          <bk-tag radius="4px" theme="success" > 启用</bk-tag>
        </span>,
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
      cell: (_h: any, { row }: { row: toolModel }) => {
        const isEnabled = row.status === 'enabled';
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
              onClick={() => handleEdit(row)}>
              {t('编辑')}
            </bk-button>
            <bk-button
              text
              theme="primary"
              class="mr8"
              onClick={() => handlePreview(row)}>
              {t('预览')}
            </bk-button>
            <bk-popover
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
                      onClick={() => handleToggleStatus(row)}>
                      {isEnabled ? t('停用') : t('启用')}
                    </bk-button>
                    {isDeleteDisabled ? (
                      <bk-tooltips
                        content={deleteTooltip}
                        placement="top">
                        <bk-button
                          text
                          disabled
                          class="mr8 mr8-disabled">
                          {t('删除')}
                        </bk-button>
                      </bk-tooltips>
                    ) : (
                      <bk-button
                        text
                        class="mr8"
                        onClick={() => handleDelete(row)}>
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

  // 新建报表
  const handleCreateReport = () => {
    router.push({ name: 'toolCreate' });
  };

  // 编辑工具
  const handleEdit = (row: toolModel) => {
    router.push({
      name: 'toolEdit',
      params: { uid: row.uid },
    });
  };

  // 预览工具
  const handlePreview = (row: toolModel) => {
    router.push({
      name: 'toolPreview',
      params: { uid: row.uid },
    });
  };

  // 删除工具
  const handleDelete = (row: toolModel) => {
    console.log('delete', row);
    // TODO: 实现删除逻辑
  };

  // 启用/停用工具
  const handleToggleStatus = (row: toolModel) => {
    const newStatus = row.status === 'enabled' ? 'disabled' : 'enabled';
    console.log('toggle status', row.uid, newStatus);
    // TODO: 实现启用/停用逻辑
  };

  // 搜索
  const handleSearch = () => {
    fetchData();
  };

  // 获取数据
  const fetchData = () => {
  };

  const handleClearSearch = () => {
    searchKeyword.value = '';
    searchModel.value = {};
  };

  const handleRequestSuccess = (data: any) => {
    isLoading.value = false;
    console.log('handleRequestSuccess', data);
  };

  const {
    run: fetchToolsTagsList,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    onSuccess: (data) => {
      console.log('fetchToolsTagsList', data);
      tagsEnums.value = data;
    },
  });

  onMounted(() => {
    fetchToolsTagsList();
  });
</script>

<style lang="postcss" scoped>
  .report-config {
    position: relative;
    min-height: 85vh;
    padding: 24px;
    background-color: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);
  }

  .report-config-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .header-left {
    display: flex;
    align-items: center;
  }

  .header-right {
    display: flex;
    align-items: center;
  }

  .mr4 {
    margin-right: 4px;
  }

  .mr8 {
    margin-right: 8px;
  }

  .mr16 {
    margin-right: 16px;
  }

  .status-filter {
    :deep(.bk-radio-button) {
      .bk-radio-button-label {
        display: flex;
        align-items: center;
      }
    }
  }

  .search-input {
    width: 600px;
  }

  .report-config-content {
    min-height: 400px;
  }

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

  .more-action-menu {
    display: flex;
    flex-direction: column;
    min-width: 80px;

    .mr8 {
      display: block;
      width: 100%;
      padding: 8px 12px;
      font-size: 12px;
      color: #63656e;
      text-align: left;

      &:hover {
        color: #3a84ff;
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

  .report-config-list {
    :deep(.t-table__row--hover) {
      background-color: #fff !important;
    }
  }
</style>
