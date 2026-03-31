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
          type="capsule">
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
        @delete="handleDelete"
        @drag-sort="handleDragSort"
        @edit="handleEdit"
        @group-drag-sort="handleGroupDragSort"
        @rename-group="handleRenameGroup"
        @toggle-status="handleToggleStatus" />
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
      :bkvision-report-list="bkvisionReportList"
      :default-group-id="currentGroupId"
      :edit-data="editReportData"
      :group-list="groupListForSelect"
      @cancel="handleReportSidesliderCancel"
      @submit="handleReportSubmit" />
  </div>
</template>

<script setup lang='ts'>
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ReportCreateSideslider, {
    type BkvisionReport,
    type ReportFormData,
  } from './components/report-create-sideslider.vue';
  import ReportGroupList, {
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
  const currentGroupId = ref('');
  const editReportData = ref<ReportFormData | null>(null);

  // 模拟 BKVision 报表列表数据
  const bkvisionReportList = ref<BkvisionReport[]>([
    {
      id: 'bkv-001',
      name: '【审计中心-BKVision工具验证】BKVision工具验证-frodomei',
      url: 'https://example.com/report/1',
    },
    {
      id: 'bkv-002',
      name: '【蓝鲸审计中心】审计中心报表',
      url: 'https://example.com/report/2',
    },
    {
      id: 'bkv-003',
      name: '【蓝鲸审计中心】风险分析报表',
      url: 'https://example.com/report/3',
    },
  ]);

  // 分组列表（用于选择器）
  const groupListForSelect = computed(() => reportGroups.value.map(g => ({
    id: g.id,
    name: g.name,
  })));

  // 模拟数据
  const reportGroups = ref<ReportGroup[]>([
    {
      id: '1',
      name: '专项分析',
      reports: [
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'enabled',
          updatedBy: 'Ralph Edwards',
          updatedAt: '2026-03-23 22:38:52',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'enabled',
          updatedBy: 'Jacob Jones',
          updatedAt: '2026-03-23 21:12:38',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'enabled',
          updatedBy: 'Darrell Steward',
          updatedAt: '2026-03-23 20:14:57',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'enabled',
          updatedBy: 'Brooklyn Simmons',
          updatedAt: '2026-03-20 23:21:12',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'enabled',
          updatedBy: 'Cameron Williamson',
          updatedAt: '2026-03-20 18:22:56',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          bkvisionUrl: 'https://example.com',
          status: 'disabled',
          updatedBy: 'Dianne Russell',
          updatedAt: '2026-03-20 07:20:08',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'enabled',
          updatedBy: 'Albert Flores',
          updatedAt: '2026-03-19 22:18:40',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'disabled',
          updatedBy: 'Jerome Bell',
          updatedAt: '2026-03-19 00:11:38',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'enabled',
          updatedBy: 'Floyd Miles',
          updatedAt: '2026-03-18 18:10:37',
        },
        {
          id: 'RPT-0014',
          name: 'raja 测试 doris 事件合流-实时策略',
          description: '-',
          bkvisionReport: '【蓝鲸审计中心】审计中心报表',
          status: 'enabled',
          updatedBy: 'Kristin Watson',
          updatedAt: '2026-03-17 16:26:08',
        },
      ],
    },
    {
      id: '2',
      name: '系统运维',
      reports: [],
    },
    {
      id: '3',
      name: '大屏看版',
      reports: [],
    },
    {
      id: '4',
      name: '测试分组',
      reports: [],
    },
    {
      id: '5',
      name: '分组名称',
      reports: [],
    },
  ]);

  // 新建报表 - 显示侧边弹窗
  const handleCreateReport = () => {
    currentGroupId.value = '';
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

      // 生成新分组 ID
      const newId = String(Date.now());
      const newGroup: ReportGroup = {
        id: newId,
        name: createGroupFormData.value.name,
        reports: [],
      };

      // 添加到分组列表
      reportGroups.value.push(newGroup);

      createGroupDialogVisible.value = false;
      createGroupFormData.value.name = '';
      createGroupLoading.value = false;

      // TODO: 调用后端接口创建分组，成功后可自动弹出新建报表抽屉
      console.log('新建分组成功:', newGroup);
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
    console.log('搜索:', searchKeyword.value);
  };

  // 在分组中添加报表
  const handleAddReport = (groupId: string) => {
    currentGroupId.value = groupId;
    editReportData.value = null;
    reportSidesliderVisible.value = true;
  };

  // 编辑报表
  const handleEdit = (report: Report) => {
    // 查找报表所属的分组
    const group = reportGroups.value.find(g => g.reports.some(r => r.id === report.id));
    currentGroupId.value = group?.id || '';
    editReportData.value = {
      bkvisionReport: report.bkvisionReport,
      name: report.name,
      groupId: group?.id || '',
      description: report.description,
      enabled: report.status === 'enabled',
    };
    reportSidesliderVisible.value = true;
  };

  // 启用/停用报表
  const handleToggleStatus = (report: Report) => {
    console.log('切换状态:', report);
  };

  // 处理表格拖拽排序
  const handleDragSort = (result: DragSortResult) => {
    const { groupId, currentIndex, targetIndex, newOrder } = result;
    console.log('拖拽排序结果:', {
      groupId,
      currentIndex,
      targetIndex,
      newOrder: newOrder.map(item => item.id),
    });
    // 更新对应分组的报表顺序
    const group = reportGroups.value.find(g => g.id === groupId);
    if (group) {
      group.reports = newOrder;
    }
  };

  // 处理分组拖拽排序
  const handleGroupDragSort = (result: GroupDragSortResult) => {
    console.log('分组拖拽排序结果:', result.newOrder.map(g => g.name));
    // 更新分组顺序
    reportGroups.value = result.newOrder;
  };

  // 删除报表
  const handleDelete = (report: Report) => {
    console.log('删除报表:', report);
    // TODO: 调用删除接口
  };

  // 重命名分组
  const handleRenameGroup = (groupId: string, newName: string) => {
    const group = reportGroups.value.find(g => g.id === groupId);
    if (group) {
      group.name = newName;
      console.log('重命名分组成功:', groupId, newName);
      // TODO: 调用后端接口更新分组名称
    }
  };

  // 报表提交（新建/编辑）
  const handleReportSubmit = (data: ReportFormData) => {
    console.log('报表提交:', data);

    if (editReportData.value) {
      // 编辑模式 - 更新报表
      // TODO: 调用后端接口更新报表
      console.log('编辑报表成功');
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

      // 添加到对应分组
      const group = reportGroups.value.find(g => g.id === data.groupId);
      if (group) {
        group.reports.push(newReport);
      }

      console.log('新建报表成功:', newReport);
      // TODO: 调用后端接口创建报表
    }

    reportSidesliderVisible.value = false;
    editReportData.value = null;
  };

  // 报表侧边弹窗取消
  const handleReportSidesliderCancel = () => {
    editReportData.value = null;
  };
</script>

<style lang="postcss" scoped>
  .report-config {
    position: relative;
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
