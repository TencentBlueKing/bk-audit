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
              class="mr8"
              type="add" />
            {{ t('新建工具') }}
          </bk-button>
        </div>
        <div class="header-right">
          <bk-radio-group
            v-model="statusFilter"
            class="status-filter mr16"
            type="capsule"
            @change="handleStatusFilterChange">
            <bk-radio-button label="all">
              {{ t('全部') }}
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.all }}
              </bk-tag>
            </bk-radio-button>
            <bk-radio-button label="published">
              <audit-icon
                class="mr4"
                svg
                type="normal" />
              {{ t('启用') }}
              <bk-tag
                class="status-count"
                theme="success">
                {{ statusCounts.published }}
              </bk-tag>
            </bk-radio-button>
            <bk-radio-button label="unpublished">
              <audit-icon
                class="mr4"
                svg
                type="unknown" />
              {{ t('停用') }}
              <bk-tag
                class="status-count"
                theme="warning">
                {{ statusCounts.unpublished }}
              </bk-tag>
            </bk-radio-button>
          </bk-radio-group>
          <bk-search-select
            v-model="searchValue"
            class="search-input"
            clearable
            :data="searchSelectData"
            :placeholder="t('搜索工具名称、工具说明、工具类型、更新人')"
            unique-select
            @update:model-value="handleSearch" />
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="report-config-content">
        <tool-list-table
          ref="toolListRef"
          :search-params="searchModel"
          :strategy-list="strategyList"
          :tags-enums="tagsEnums"
          @clear-search="handleClearSearch"
          @delete="handleDelete"
          @edit="handleEdit"
          @preview="handlePreview"
          @request-success="handleRequestSuccess"
          @toggle-status="handleToggleStatus" />
      </div>
    </div>
  </skeleton-loading>

  <!-- 工具预览抽屉 -->
  <tool-preview-drawer
    ref="previewDrawerRef"
    v-model:is-show="isPreviewShow"
    :all-tools-data="allToolsData"
    :tags-enums="tagsEnums" />

  <!-- 确认操作弹窗（删除/启用/停用） -->
  <confirm-action-dialog
    ref="confirmDialogRef"
    v-model:is-show="confirmDialogVisible"
    :action-type="confirmActionType"
    :target="confirmTarget"
    @success="handleActionSuccess" />
</template>

<script setup lang='ts'>
  import { onMounted, onUnmounted, reactive, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';
  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';

  import useEventBus from '@hooks/use-event-bus';
  import useRequest from '@hooks/use-request';

  import ConfirmActionDialog from './components/confirm-action-dialog.vue';
  import ToolListTable from './components/tool-list-table.vue';
  import ToolPreviewDrawer from './components/tool-preview-drawer.vue';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  type ActionType = 'delete' | 'enable' | 'disable';

  interface SearchKey {
    id: string;
    name: string;
    values: Array<{ id: string; name: string }>;
  }

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

  interface ToolItem {
    uid: string;
    name: string;
    status: 'published' | '';
    strategies: number[];
  }

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const isLoading = ref(true);
  // bk-search-select 搜索值
  const searchValue = ref<SearchKey[]>([]);

  // bk-search-select 搜索条件配置（对应接口参数）
  const searchSelectData = [
    {
      name: '工具名称',
      id: 'name',
      placeholder: '请输入工具名称',
    },
    {
      name: '工具说明',
      id: 'description',
      placeholder: '请输入工具说明',
    },
    {
      name: '工具类型',
      id: 'tool_type',
      placeholder: '请选择工具类型',
      multiple: false,
      children: [
        { id: 'data_search', name: '数据查询' },
        { id: 'api', name: 'API' },
        { id: 'bk_vision', name: 'BK-Vision' },
      ],
    },
    {
      name: '更新人',
      id: 'updated_by',
      placeholder: '请选择更新人',
      multiple: false,
    },
  ];

  // 表格引用
  const toolListRef = ref();
  const previewDrawerRef = ref();
  const searchModel = ref<Record<string, any>>({});
  const tagsEnums = ref<Array<TagItem>>([]);
  // 策略列表（用于匹配策略名称）
  const strategyList = ref<Array<{ label: string; value: number }>>([]);
  // 全部工具数据（用于下钻时获取工具名称）
  const allToolsData = ref<Array<ToolDetailModel>>([]);

  // 状态筛选
  const statusFilter = ref('all');
  const statusCounts = reactive({
    all: 0,
    published: 0,
    unpublished: 0,
  });

  // 确认操作弹窗相关（删除/启用/停用）
  const confirmDialogVisible = ref(false);
  const confirmActionType = ref<ActionType>('delete');
  const confirmTarget = ref<ToolItem | null>(null);

  // 预览抽屉相关
  const isPreviewShow = ref(false);

  // 新建工具
  const handleCreateReport = () => {
    router.push({ name: 'sceneToolCreate', query: {
      scene_id: route.query.scene_id,
      scope_id: route.query.scope_id,
      scope_type: route.query.scope_type,
    } });
  };

  // 编辑工具
  const handleEdit = (row: ToolItem) => {
    router.push({
      name: 'sceneToolEdit',
      params: { id: row.uid },
      query: {
        scene_id: route.query.scene_id,
        scope_id: route.query.scope_id,
        scope_type: route.query.scope_type,
      },
    });
  };

  // 预览工具
  const handlePreview = (row: ToolItem) => {
    isPreviewShow.value = true;
    previewDrawerRef.value?.open(row.uid);
  };

  // 显示删除确认弹窗
  const handleDelete = (row: ToolItem) => {
    confirmTarget.value = row;
    confirmActionType.value = 'delete';
    confirmDialogVisible.value = true;
  };

  // 显示启用/停用确认弹窗
  const confirmDialogRef = ref();
  const handleToggleStatus = (row: ToolItem) => {
    confirmTarget.value = row;
    const actionType = row.status === 'published' ? 'disable' : 'enable';
    confirmActionType.value = actionType;
    confirmDialogRef.value?.showToggleStatusInfoBox(row, actionType);
  };

  // 操作成功后刷新列表和状态统计
  const handleActionSuccess = () => {
    confirmTarget.value = null;
    refreshList();
    // 操作（删除/启用/停用）成功后，重新获取状态统计
    fetchStatusCounts();
  };

  // 刷新列表（统一入口）
  const refreshList = (searchParams?: Record<string, any>) => {
    const params: Record<string, any> = {
      ...searchParams,
      sort: ['-created_at'],
    };
    if (statusFilter.value !== 'all') {
      params.status = [statusFilter.value];
    } else {
      // 全部状态时，显式清除 status 参数，避免 paramsMemo 中残留上次的 status 值
      params.status = undefined;
    }
    toolListRef.value?.fetchData(params);
  };

  // 搜索 - 参考 platform-manage/scene-manage 的 handleSearch 实现
  const handleSearch = (keyword: SearchKey[]) => {
    const search: Record<string, any> = {
      name: undefined,
      description: '',
      tool_type: undefined,
      updated_by: '',
    };

    keyword.forEach((item) => {
      if (item.values && item.values.length) {
        const value = item.values.map(v => v.id).join(',');
        if (item.id === 'name') {
          search.name = value;
        } else if (item.id === 'description') {
          search.description = value;
        } else if (item.id === 'tool_type') {
          // tool_type 接口期望 array<string>
          search.tool_type = value.split(',').map(v => v.trim());
        } else if (item.id === 'updated_by') {
          search.updated_by = value;
        }
      }
    });

    refreshList(search);
  };

  // 状态筛选变化
  const handleStatusFilterChange = () => {
    handleSearch(searchValue.value);
  };

  const handleClearSearch = () => {
    searchValue.value = [];
    statusFilter.value = 'all';
    toolListRef.value?.fetchData({ sort: ['-created_at'] });
  };

  const handleRequestSuccess = (data: any) => {
    isLoading.value = false;
    console.log('handleRequestSuccess', data);
  };

  // 获取全局状态统计（分别请求各状态数量）
  const fetchStatusCounts = () => {
    // 不传 status 即获取全部工具
    const allPromise = ToolManageService.fetchAllTools();
    const publishedPromise = ToolManageService.fetchAllTools({ status: ['published'] });
    const unpublishedPromise = ToolManageService.fetchAllTools({ status: ['unpublished'] });
    Promise.all([allPromise, publishedPromise, unpublishedPromise]).then(([all, published, unpublished]) => {
      statusCounts.all = all.length;
      statusCounts.published = published.length;
      statusCounts.unpublished = unpublished.length;
    });
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

  const {
    run: fetchStrategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    defaultValue: [],
    onSuccess: (data) => {
      strategyList.value = data;
    },
  });

  // 获取全部工具（用于下钻时获取工具名称）
  const {
    run: fetchAllToolsData,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    onSuccess: (data) => {
      allToolsData.value = data;
    },
  });

  // 监听场景切换事件
  const { on: onEvent, off } = useEventBus();

  // 刷新所有数据（场景切换时调用）
  const refreshAllData = () => {
    const scopeParams = getSceneSystemParams();
    fetchToolsTagsList(scopeParams);
    fetchAllToolsData();
    refreshList();
    // 场景切换时也需要刷新状态统计
    fetchStatusCounts();
  };

  onMounted(() => {
    const scopeParams = getSceneSystemParams();
    fetchToolsTagsList(scopeParams);
    fetchStrategyList();
    fetchAllToolsData();
    // 初始化时获取一次状态统计
    fetchStatusCounts();
    // 监听场景切换事件
    onEvent('scene:change', () => {
      refreshAllData();
    });
  });

  onUnmounted(() => {
    off('scene:change');
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
        padding: 0 12px;
      }
    }

    :deep(.bk-radio-button:not(.is-checked)) {
      .status-count {
        color: #979ba5;
        background-color: #fff !important;
        border-color: #fff !important;
      }
    }
  }

  .status-count {
    height: 18px;
    min-width: 18px;
    padding: 0 4px;
    margin-left: 4px;
    font-size: 12px;
    line-height: 18px;
    pointer-events: none;
  }

  .search-input {
    width: 600px;
  }

  .report-config-content {
    min-height: 400px;

    :deep(.audit-tdesign-list) {
      border: none;
    }
  }
</style>
