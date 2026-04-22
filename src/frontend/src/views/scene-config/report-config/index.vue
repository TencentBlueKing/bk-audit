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
          <bk-button
            class="mr8"
            @click="handleCreateGroup">
            <audit-icon
              class="mr4"
              type="add" />
            {{ t('新建分组') }}
          </bk-button>
          <bk-button @click="handleToggleExpand">
            <img
              class="mr4 expand-icon"
              :src="isAllExpanded ? collapseIcon : expandIcon">
            {{ isAllExpanded ? t('全部收起') : t('全部展开') }}
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
            </bk-radio-button>
            <bk-radio-button label="enabled">
              <audit-icon
                class="mr4"
                svg
                type="normal" />
              {{ t('启用') }}
            </bk-radio-button>
            <bk-radio-button label="disabled">
              <audit-icon
                class="mr4"
                svg
                type="unknown" />
              {{ t('停用') }}
            </bk-radio-button>
          </bk-radio-group>
          <bk-input
            v-model="searchKeyword"
            class="search-input"
            clearable
            :placeholder="t('搜索 报表ID、名称、描述、BKVision 报表、更新人')"
            type="search"
            @clear="handleSearch"
            @enter="handleSearch" />
        </div>
      </div>
      <div class="report-config-content">
        <bk-loading :loading="isDataLoading || isLoading">
          <bk-exception
            v-if="!isDataLoading && !isLoading && reportGroups.length === 0"
            class="report-empty"
            type="empty">
            {{ t('暂无数据') }}
          </bk-exception>
          <report-group-list
            v-else-if="!isDataLoading && !isLoading"
            :expand-all="isAllExpanded"
            :groups="reportGroups"
            @add-report="handleAddReport"
            @deleted="handleDeleted"
            @drag-sort="handleDragSort"
            @edit="handleEdit"
            @group-drag-sort="handleGroupDragSort"
            @order-updated="handleOrderUpdated"
            @status-updated="handleStatusUpdated" />
        </bk-loading>
      </div>

      <!-- 新建分组弹窗 -->
      <bk-dialog
        v-model:is-show="createGroupDialogVisible"
        :title="t('新建分组')"
        width="480">
        <bk-form
          ref="createGroupFormRef"
          form-type="vertical"
          :model="createGroupFormData"
          :rules="createGroupFormRules">
          <bk-form-item
            :label="t('分组名称')"
            property="name"
            required>
            <bk-input
              v-model="createGroupFormData.name"
              :placeholder="t('请输入')" />
          </bk-form-item>
        </bk-form>
        <template #footer>
          <bk-button
            class="mr8"
            :loading="createGroupLoading"
            theme="primary"
            @click="handleConfirmCreateGroup">
            {{ t('确定') }}
          </bk-button>
          <bk-button @click="handleCancelCreateGroup">
            {{ t('取消') }}
          </bk-button>
        </template>
      </bk-dialog>

      <!-- 新建/编辑报表侧边弹窗 -->
      <report-create-sideslider
        v-model:is-show="reportSidesliderVisible"
        :chart-lists="chartLists"
        :default-group-id="currentGroupId"
        :default-group-name="pendingOpenCreateWithGroup"
        :edit-data="editReportData"
        :group-list="groupListForSelect"
        @cancel="handleReportSidesliderCancel"
        @submit="handleReportSubmit"
        @success="handleCreateSuccess" />
    </div>
  </skeleton-loading>
</template>

<script setup lang='ts'>
  import { computed, onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import PanelModelService from '@service/report-config';
  import ToolManageService from '@service/tool-manage';

  import PanelModel from '@model/report-config/panel';

  import useEventBus from '@hooks/use-event-bus';
  import useRequest from '@hooks/use-request';

  import collapseIcon from '@images/collapse.svg';
  import expandIcon from '@images/expand.svg';

  import ReportCreateSideslider, {
    type ReportFormData,
  } from './components/report-create-sideslider.vue';
  import ReportGroupList, {
    type DragSortResult,
    type GroupDragSortResult,
    type Report,
    type ReportGroup,
  } from './components/report-group-list.vue';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  const { t } = useI18n();

  // 状态筛选
  const statusFilter = ref('all');
  // 搜索关键词
  const searchKeyword = ref('');
  // 是否全部展开
  const isAllExpanded = ref(false);

  // 新建分组相关状态
  const createGroupDialogVisible = ref(false);
  const createGroupFormRef = ref();
  const createGroupLoading = ref(false);
  const createGroupFormData = ref({
    name: '',
  });
  const createGroupFormRules = {
    name: [
      {
        required: true,
        message: t('分组名称不能为空'),
        trigger: 'blur',
      },
    ],
  };
  const { on: onEvent, off } = useEventBus();

  // 新建/编辑报表侧边弹窗相关状态
  const reportSidesliderVisible = ref(false);
  const currentGroupId = ref<number | null>(null);
  const editReportData = ref<ReportFormData | null>(null);
  // 新建分组后自动打开新建报表的分组名称
  const pendingOpenCreateWithGroup = ref<string | null>(null);

  // 分组列表（用于选择器）
  const groupListForSelect = computed(() => reportGroups.value.map(g => ({
    id: g.id,
    name: g.name,
  })));

  const groups = ref<Array<{ id: number; name: string; priority_index: number }>>([]);
  const reportGroups = ref<ReportGroup[]>([]);
  // 数据加载状态（覆盖 fetchGroups + fetchPanels 完整链路）
  const isDataLoading = ref(false);

  // 图表列表数据
  interface ChartListModel {
    uid: string;
    name: string;
    share: Array<{
      uid: string;
      name: string;
    }>;
  }
  const chartLists = ref<ChartListModel[]>([]);

  // 根据 vision_id 查找 BKVision 报表名称
  const findVisionName = (visionId: string): string => {
    for (const parent of chartLists.value) {
      if (parent.share) {
        const child = parent.share.find(item => item.uid === visionId);
        if (child) {
          return child.name;
        }
      }
    }
    return '';
  };

  // 根据 vision_id 查找父级空间的 uid
  const findVisionSpaceUid = (visionId: string): string => {
    for (const parent of chartLists.value) {
      if (parent.share) {
        const child = parent.share.find(item => item.uid === visionId);
        if (child) {
          return parent.uid;
        }
      }
    }
    return '';
  };

  // 获取图表列表
  const {
    loading: isLoading,
    run: fetchChartLists,
  } = useRequest(ToolManageService.fetchChartLists, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      if (Array.isArray(data)) {
        chartLists.value = data;
      }
    },
  });

  // 获取场景报表列表
  const {
    run: fetchPanels,
  } = useRequest(PanelModelService.fetchPanels, {
    defaultValue: [],
    onSuccess: (panelsData) => {
      // 处理分组Panel数据，将panelsData中group_priority_index与groups中的priority_index相等的项合到groups.reports 中
      // 过滤掉 reports 为空的分组，按 priority_index 从大到小排列
      reportGroups.value = groups.value
        .map(group => ({
          id: group.id,
          name: group.name,
          priority_index: group.priority_index,
          reports: panelsData
            .filter((panel: PanelModel) => panel.group_id === group.id)
            .map((panel: PanelModel) => ({
              id: panel.id,
              name: panel.name,
              description: panel.description || '--',
              vision_id: panel.vision_id,
              bkvisionReportName: findVisionName(panel.vision_id),
              bkvisionSpaceUid: findVisionSpaceUid(panel.vision_id),
              status: panel.status || 'unpublished',
              updatedBy: panel.updated_by || '--',
              updatedAt: panel.updated_at || '--',
            })) as Report[],
        }))
        .sort((a, b) => b.priority_index - a.priority_index);
    },
    onFinally: () => {
      isDataLoading.value = false;
    },
  });
  // 获取分组
  const {
    run: fetchGroups,
  } = useRequest(PanelModelService.fetchGroups, {
    defaultValue: {},
    onSuccess: (data) => {
      groups.value = data;
      fetchPanels({
        page: 1,
        page_size: 10000,
        status: '',
        scene_id: getSceneSystemParams().scope_id,
        keyword: searchKeyword.value || undefined,
      });
    },
    onFinally: () => {
      isDataLoading.value = false;
    },
  });
  // 新建报表 - 显示侧边弹窗
  const handleCreateReport = () => {
    currentGroupId.value = null;
    editReportData.value = null;
    reportSidesliderVisible.value = true;
  };

  // 新建分组 - 显示弹窗
  const handleCreateGroup = () => {
    createGroupFormData.value.name = '';
    createGroupDialogVisible.value = true;
  };

  // 确认新建分组
  const handleConfirmCreateGroup = async () => {
    try {
      await createGroupFormRef.value?.validate();
      createGroupLoading.value = true;

      const groupName = createGroupFormData.value.name.trim();

      // 记录返回结果的分组 ID
      const result = await PanelModelService.createGroup({
        scene_id: getSceneSystemParams().scope_id,
        name: groupName,
        priority_index: groups.value.length + 1,
      });

      createGroupDialogVisible.value = false;
      createGroupFormData.value.name = '';
      createGroupLoading.value = false;
      // 用返回的分组 ID 赋值给所属分组
      pendingOpenCreateWithGroup.value = null;
      currentGroupId.value = (result as any)?.id ?? null;
      editReportData.value = null;
      // 刷新分组列表
      await fetchGroups({
        scope_id: getSceneSystemParams().scope_id,
        scope_type: getSceneSystemParams().scope_type,
      });
      // 分组列表刷新完成后再打开侧边栏
      reportSidesliderVisible.value = true;
    } catch (e) {
      createGroupLoading.value = false;
    }
  };

  // 取消新建分组
  const handleCancelCreateGroup = () => {
    createGroupDialogVisible.value = false;
    createGroupFormData.value.name = '';
  };

  // 全部展开/收起
  const handleToggleExpand = () => {
    isAllExpanded.value = !isAllExpanded.value;
  };

  // 搜索/筛选
  const handleSearch = () => {
    // 根据状态筛选确定 status 参数
    let statusParam: 'published' | 'unpublished' | '' = '';
    if (statusFilter.value === 'enabled') {
      statusParam = 'published';
    } else if (statusFilter.value === 'disabled') {
      statusParam = 'unpublished';
    }
    isDataLoading.value = true;
    reportGroups.value = [];
    fetchPanels({
      page: 1,
      page_size: 10000,
      status: statusParam,
      keyword: searchKeyword.value || undefined,
      scene_id: getSceneSystemParams().scope_id,
    });
  };

  // 状态筛选变化
  const handleStatusFilterChange = () => {
    handleSearch();
  };

  // 在分组中添加报表
  const handleAddReport = (groupId: number) => {
    currentGroupId.value = groupId;
    editReportData.value = null;
    reportSidesliderVisible.value = true;
  };

  // 编辑报表
  const handleEdit = (report: Report) => {
    // 查找报表所属的分组
    let reportGroupId: number | null = null;
    for (const group of reportGroups.value) {
      if (group.reports.some(r => r.id === report.id)) {
        reportGroupId = group.id;
        break;
      }
    }

    // 构建编辑数据并打开侧边栏
    editReportData.value = {
      id: String(report.id),
      bkvisionReport: report.vision_id || '',
      name: report.name,
      groupId: reportGroupId,
      description: report.description === '-' ? '' : report.description,
      status: report.status,
      enabled: report.status === 'published',
      vision_id: [],
    };
    currentGroupId.value = null;
    reportSidesliderVisible.value = true;
  };


  // 启用/停用成功后刷新列表
  const handleStatusUpdated = () => {
    handleSearch();
  };

  // 删除成功后刷新列表
  const handleDeleted = () => {
    handleSearch();
  };

  // 排序成功后刷新列表
  const handleOrderUpdated = () => {
    // 排序成功后重新获取分组和Panel数据，确保数据与后端同步
    // 需要先获取分组（因为分组排序可能变化），fetchGroups 成功后会自动调用 fetchPanels
    isDataLoading.value = true;
    reportGroups.value = [];
    fetchGroups({
      scope_id: getSceneSystemParams().scope_id,
      scope_type: getSceneSystemParams().scope_type,
    });
  };

  // 处理表格拖拽排序
  const handleDragSort = (result: DragSortResult) => {
    const { groupId, newOrder } = result;
    // 更新对应分组的报表顺序
    const group = reportGroups.value.find(g => g.id === groupId);
    if (group) {
      group.reports = newOrder;
    }
  };

  // 处理分组拖拽排序
  const handleGroupDragSort = (result: GroupDragSortResult) => {
    // 更新分组顺序
    reportGroups.value = result.newOrder;
  };


  // 报表提交（新建/编辑）— 侧边栏内部已调用 API，此处仅关闭弹窗
  const handleReportSubmit = () => {
    reportSidesliderVisible.value = false;
    editReportData.value = null;
  };

  // 创建成功后刷新列表
  const handleCreateSuccess = () => {
    // 重新获取分组和Panel列表
    isDataLoading.value = true;
    reportGroups.value = [];
    fetchGroups({
      scope_id: getSceneSystemParams().scope_id,
      scope_type: getSceneSystemParams().scope_type,
    });
  };

  // 报表侧边弹窗取消
  const handleReportSidesliderCancel = () => {
    editReportData.value = null;
  };
  const handleSceneChange = () => {
    isDataLoading.value = true;
    reportGroups.value = [];
    fetchChartLists().then(() => {
      fetchGroups({
        scope_id: getSceneSystemParams().scope_id,
        scope_type: getSceneSystemParams().scope_type,
      });
    });
  };
  onMounted(() => {
    // 先获取图表列表，再获取分组数据
    handleSceneChange();
    setTimeout(() => {
      onEvent('scene:change', handleSceneChange);
    }, 1000);
  });

  onUnmounted(() => {
    off('scene:change', handleSceneChange);
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

  .expand-icon {
    width: 14px;
    height: 14px;
    vertical-align: middle;
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
    width: 400px;
  }

  .report-config-content {
    min-height: 400px;
  }

  .report-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 400px;
  }
</style>
