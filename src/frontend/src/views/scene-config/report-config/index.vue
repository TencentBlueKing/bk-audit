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
            <audit-icon
              class="mr4"
              :type="isAllExpanded ? 'un-full-screen' : 'fullscreen'" />
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

      <!-- 内容区域 -->
      <div class="report-config-content">
        <report-group-list
          :expand-all="isAllExpanded"
          :groups="reportGroups"
          @add-report="handleAddReport"
          @cross-group-drag="handleCrossGroupDrag"
          @deleted="handleDeleted"
          @drag-sort="handleDragSort"
          @edit="handleEdit"
          @group-drag-sort="handleGroupDragSort"
          @order-updated="handleOrderUpdated"
          @status-updated="handleStatusUpdated" />
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
        :edit-data="editReportData"
        :group-list="groupListForSelect"
        @cancel="handleReportSidesliderCancel"
        @submit="handleReportSubmit"
        @success="handleCreateSuccess" />
    </div>
  </skeleton-loading>
</template>

<script setup lang='ts'>
  import { computed, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import PanelModelService from '@service/report-config';
  import ToolManageService from '@service/tool-manage';

  import PanelModel from '@model/report-config/panel';

  import useRequest from '@hooks/use-request';

  import ReportCreateSideslider, {
    type ReportFormData,
  } from './components/report-create-sideslider.vue';
  import ReportGroupList, {
    type CrossGroupDragResult,
    type DragSortResult,
    type GroupDragSortResult,
    type Report,
    type ReportGroup,
  } from './components/report-group-list.vue';

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

  // 新建/编辑报表侧边弹窗相关状态
  const reportSidesliderVisible = ref(false);
  const currentGroupId = ref<number | null>(null);
  const editReportData = ref<ReportFormData | null>(null);

  // 分组列表（用于选择器），包含临时新建的分组
  const tempNewGroup = ref<{ id: number; name: string; priority_index: number } | null>(null);
  const groupListForSelect = computed(() => {
    const list = reportGroups.value.map(g => ({
      id: g.id,
      name: g.name,
    }));
    // 如果有临时新建的分组，添加到列表开头
    if (tempNewGroup.value) {
      list.unshift({
        id: tempNewGroup.value.id,
        name: tempNewGroup.value.name,
      });
    }
    return list;
  });

  const groups = ref<Array<{ id: number; name: string; priority_index: number }>>([]);
  const reportGroups = ref<ReportGroup[]>([]);

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

  // 获取分组Panel
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
              description: panel.description || '-',
              bkvisionReport: panel.vision_id,
              bkvisionReportName: findVisionName(panel.vision_id),
              bkvisionSpaceUid: findVisionSpaceUid(panel.vision_id),
              status: panel.is_enabled ? 'enabled' : 'disabled',
              updatedBy: panel.updated_by,
              updatedAt: panel.updated_at,
            })) as Report[],
        }))
        .filter(group => group.reports.length > 0)
        .sort((a, b) => b.priority_index - a.priority_index);
    },
  });
  // 获取分组
  const {
    run: fetchGroups,
  } = useRequest(PanelModelService.fetchGroups, {
    defaultValue: {},
    onSuccess: (data) => {
      groups.value = data;
      // 根据状态筛选确定 is_enabled 参数
      const isEnabled = statusFilter.value === 'all'
        ? undefined
        : statusFilter.value === 'enabled';
      fetchPanels({
        page: 1,
        page_size: 10000,
        is_enabled: isEnabled,
        keyword: searchKeyword.value || undefined,
      });
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

      // 生成新分组 ID 和 priority_index（取当前最大值 + 1）
      const newId = Date.now();
      const maxPriorityIndex = reportGroups.value.length > 0
        ? Math.max(...reportGroups.value.map(g => g.priority_index))
        : -1;

      // 设置为临时分组（只在下拉选择器中显示，不加入主列表）
      tempNewGroup.value = {
        id: newId,
        name: createGroupFormData.value.name,
        priority_index: maxPriorityIndex + 1,
      };

      createGroupDialogVisible.value = false;
      createGroupFormData.value.name = '';
      createGroupLoading.value = false;
      // 自动弹出新建报表侧边抽屉，并默认选中新创建的分组
      currentGroupId.value = newId;
      editReportData.value = null;
      reportSidesliderVisible.value = true;
    } catch {
      // 表单验证失败
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

  // 搜索
  const handleSearch = () => {
    // 根据状态筛选确定 is_enabled 参数
    const isEnabled = statusFilter.value === 'all'
      ? undefined
      : statusFilter.value === 'enabled';
    fetchPanels({
      page: 1,
      page_size: 10000,
      is_enabled: isEnabled,
      keyword: searchKeyword.value || undefined,
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
    const group = reportGroups.value.find(g => g.reports.some(r => r.id === report.id));
    currentGroupId.value = group?.id ?? null;
    editReportData.value = {
      id: report.id,
      bkvisionReport: report.bkvisionReport,
      vision_id: report.bkvisionReport ? [report.bkvisionReport] : [],
      name: report.name,
      groupId: group?.id ?? null,
      description: report.description,
      enabled: report.status === 'enabled',
    };
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
    fetchGroups();
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

  // 处理跨分组拖拽
  const handleCrossGroupDrag = (result: CrossGroupDragResult) => {
    const { fromGroupId, toGroupId } = result;

    // 找到源分组和目标分组
    const fromGroup = reportGroups.value.find(g => g.id === fromGroupId);
    const toGroup = reportGroups.value.find(g => g.id === toGroupId);

    if (fromGroup && toGroup) {
      // 报表已经被 vuedraggable 自动移动了，这里只需要调用 API 更新
      // TODO: 调用后端接口更新报表所属分组
    }
  };


  // 报表提交（新建/编辑）
  const handleReportSubmit = (data: ReportFormData) => {
    if (editReportData.value) {
      // 编辑模式 - 更新报表
      // TODO: 调用后端接口更新报表
    } else {
      // 新建模式 - 创建报表
      const newReport: Report = {
        id: `RPT-${Date.now()}`,
        name: data.name,
        description: data.description || '-',
        bkvisionReport: data.bkvisionReport,
        status: data.enabled ? 'enabled' : 'disabled',
        updatedBy: 'Current User',
        updatedAt: new Date().toLocaleString(),
      };

      // 检查是否选择了临时新建的分组
      if (tempNewGroup.value && data.groupId === tempNewGroup.value.id) {
        // 将临时分组正式加入主列表
        const newGroup: ReportGroup = {
          id: tempNewGroup.value.id,
          name: tempNewGroup.value.name,
          priority_index: tempNewGroup.value.priority_index,
          reports: [newReport],
        };
        reportGroups.value.unshift(newGroup);
        tempNewGroup.value = null;
      } else {
        // 添加到已有分组
        const group = reportGroups.value.find(g => g.id === data.groupId);
        if (group) {
          group.reports.push(newReport);
        }
        // 清除临时分组（如果有）
        tempNewGroup.value = null;
      }
    }

    reportSidesliderVisible.value = false;
    editReportData.value = null;
  };

  // 创建成功后刷新列表
  const handleCreateSuccess = () => {
    // 清除临时分组
    tempNewGroup.value = null;
    // 重新获取分组和Panel列表
    fetchGroups({
      page: 1,
      page_size: 10000,
    });
  };

  // 报表侧边弹窗取消
  const handleReportSidesliderCancel = () => {
    editReportData.value = null;
    // 取消时清除临时分组
    tempNewGroup.value = null;
  };

  onMounted(() => {
    // 先获取图表列表，再获取分组数据
    fetchChartLists().then(() => {
      fetchGroups({
        page: 1,
        page_size: 10000,
      });
    });
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
    width: 400px;
  }

  .report-config-content {
    min-height: 400px;
  }
</style>
