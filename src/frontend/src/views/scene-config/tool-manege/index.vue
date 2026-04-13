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
            {{ t('新建工具') }}
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

  <!-- 删除确认弹窗 -->
  <delete-confirm-dialog
    v-model:is-show="deleteDialogVisible"
    :delete-target="deleteTarget"
    @deleted="handleDeleted" />
</template>

<script setup lang='ts'>
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';
  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';

  import useRequest from '@hooks/use-request';

  import DeleteConfirmDialog from './components/delete-confirm-dialog.vue';
  import ToolListTable from './components/tool-list-table.vue';
  import ToolPreviewDrawer from './components/tool-preview-drawer.vue';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

  interface ToolItem {
    uid: string;
    name: string;
    status: 'enabled' | 'disabled';
    strategies: number[];
  }

  const { t } = useI18n();
  const router = useRouter();

  const isLoading = ref(true);
  const searchKeyword = ref('');
  const toolListRef = ref();
  const previewDrawerRef = ref();
  const searchModel = ref<Record<string, any>>({});
  const tagsEnums = ref<Array<TagItem>>([]);
  // 策略列表（用于匹配策略名称）
  const strategyList = ref<Array<{ label: string; value: number }>>([]);
  // 全部工具数据（用于下钻时获取工具名称）
  const allToolsData = ref<Array<ToolDetailModel>>([]);

  // 删除弹窗相关
  const deleteDialogVisible = ref(false);
  const deleteTarget = ref<ToolItem | null>(null);

  // 预览抽屉相关
  const isPreviewShow = ref(false);

  // 新建工具
  const handleCreateReport = () => {
    router.push({ name: 'sceneToolCreate' });
  };

  // 编辑工具
  const handleEdit = (row: ToolItem) => {
    router.push({
      name: 'sceneToolEdit',
      params: { id: row.uid },
    });
  };

  // 预览工具
  const handlePreview = (row: ToolItem) => {
    isPreviewShow.value = true;
    previewDrawerRef.value?.open(row.uid);
  };

  // 显示删除确认弹窗
  const handleDelete = (row: ToolItem) => {
    deleteTarget.value = row;
    deleteDialogVisible.value = true;
  };

  // 删除成功后刷新列表
  const handleDeleted = () => {
    deleteTarget.value = null;
    toolListRef.value?.fetchData({
      keyword: searchKeyword.value,
    });
  };

  // 启用/停用工具
  const handleToggleStatus = (row: ToolItem) => {
    const newStatus = row.status === 'enabled' ? 'disabled' : 'enabled';
    console.log('toggle status', row.uid, newStatus);
    // TODO: 实现启用/停用逻辑
  };

  // 搜索
  const handleSearch = () => {
    toolListRef.value?.fetchData({
      keyword: searchKeyword.value,
    });
  };

  const handleClearSearch = () => {
    searchKeyword.value = '';
    toolListRef.value?.fetchData({ keyword: '' });
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

  onMounted(() => {
    fetchToolsTagsList();
    fetchStrategyList();
    fetchAllToolsData();
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

  .search-input {
    width: 600px;
  }

  .report-config-content {
    min-height: 400px;
  }
</style>
