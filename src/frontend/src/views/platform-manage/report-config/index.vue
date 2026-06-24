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
            theme="primary"
            @click="handleCreateReport">
            <audit-icon
              class="mr4"
              type="plus-circle" />
            {{ t('新建报表') }}
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
          <bk-search-select
            v-model="searchKeyword"
            class="search-input"
            :data="searchSelectData"
            :get-menu-list="getMenuList"
            :placeholder="t('搜索 名称、描述、BKVision 报表、更新人')"
            @change="handleSearch" />
        </div>
      </div>

      <!-- 报表表格 -->
      <report-list-table
        ref="tableRef"
        :data-source="dataSource"
        :highlight-report-id="highlightReportId"
        @delete="handleShowDeleteConfirm"
        @edit="handleEdit"
        @request-success="handleRequestSuccess"
        @toggle-status="handleConfirmToggleStatus" />

      <!-- 新建/编辑报表侧边弹窗 -->
      <report-create-sideslider
        v-model:is-show="reportSidesliderVisible"
        :chart-lists="chartLists"
        :edit-data="editReportData"
        :group-list="groupListForSelect"
        @cancel="handleReportSidesliderCancel"
        @submit="handleReportSubmit"
        @success="handleCreateSuccess" />
    </div>
  </skeleton-loading>
</template>

<script setup lang="ts">
  import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
  import { InfoBox } from 'bkui-vue';
  import { useI18n } from 'vue-i18n';

  import PanelModelService from '@service/report-config';
  import ToolManageService from '@service/tool-manage';
  import MetaManageService from '@service/meta-manage';

  import PanelModel from '@model/report-config/panel';

  import useEventBus from '@hooks/use-event-bus';
  import useRequest from '@hooks/use-request';
  import useMessage from '@/hooks/use-message';

  import ReportCreateSideslider, {
    type ReportFormData,
  } from './components/report-create-sideslider.vue';
  import ReportListTable from './components/report-list-table.vue';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const { on: onEvent, off } = useEventBus();

  // 表格 ref
  const tableRef = ref();

  // 状态筛选
  const statusFilter = ref('all');

  // 搜索关键词
  const searchKeyword = ref<any[]>([]);
  const searchSelectData = ref([
    { name: '名称', id: 'name', placeholder: '请输入名称' },
    { name: '描述', id: 'description', placeholder: '请输入描述' },
    { name: 'BKVision 报表', id: 'bkvision_report', placeholder: '请输入BKVision报表' },
    { name: '更新人', id: 'updated_by', placeholder: '请输入更新人', children: [] as Array<{ id: string; name: string }> },
  ]);

  // 全量报表数据（扁平化）
  const allReportList = ref<any[]>([]);
  // 新建报表高亮ID
  const highlightReportId = ref<string | null>(null);

  // 分组列表（用于新建/编辑侧边弹窗）
  const groups = ref<Array<{ id: number; name: string; priority_index: number }>>([]);
  const groupListForSelect = computed(() => groups.value.map(g => ({
    id: g.id,
    name: g.name,
  })));

  // 图表列表数据
  const chartLists = ref<any[]>([]);

  // 新建/编辑报表侧边弹窗相关状态
  const reportSidesliderVisible = ref(false);
  const editReportData = ref<ReportFormData | null>(null);

  // 根据 vision_id 查找 BKVision 报表名称
  const findVisionName = (visionId: string): string => {
    for (const parent of chartLists.value) {
      if (parent.share) {
        const child = parent.share.find((item: any) => item.uid === visionId);
        if (child) {
          return child.name;
        }
      }
    }
    return '';
  };

  // dataSource 适配器：从全量数据中筛选+分页
  const dataSource = (params: any) => {
    const page = params?.page || 1;
    const pageSize = params?.page_size || 20;

    // 前端筛选
    let filtered = allReportList.value;

    // 状态筛选
    if (statusFilter.value === 'enabled') {
      filtered = filtered.filter(r => r.status === 'published');
    } else if (statusFilter.value === 'disabled') {
      filtered = filtered.filter(r => r.status === 'unpublished');
    }

    // 搜索筛选
    const searchParams = getSearchParams();
    if (searchParams.name) {
      filtered = filtered.filter(r => r.name.toLowerCase().includes(searchParams.name.toLowerCase()));
    }
    if (searchParams.description) {
      filtered = filtered.filter(r => r.description && r.description !== '--'
        && r.description.toLowerCase().includes(searchParams.description.toLowerCase()));
    }
    if (searchParams.bkvision_report) {
      filtered = filtered.filter(r => (r.bkvisionReportName ?? '').toLowerCase()
        .includes(searchParams.bkvision_report.toLowerCase()));
    }
    if (searchParams.updated_by) {
      filtered = filtered.filter(r => r.updated_by && r.updated_by !== '--'
        && r.updated_by.toLowerCase().includes(searchParams.updated_by.toLowerCase()));
    }

    const start = (page - 1) * pageSize;
    const end = start + pageSize;

    return Promise.resolve({
      results: filtered.slice(start, end),
      page,
      num_pages: Math.ceil(filtered.length / pageSize) || 1,
      total: filtered.length,
    });
  };

  // 从 searchSelect 数组中提取对应字段参数
  const getSearchParams = (): Record<string, any> => {
    const search = {
      name: '',
      description: '',
      bkvision_report: '',
      updated_by: '',
    } as Record<string, any>;

    searchKeyword.value.forEach((item) => {
      if (item.values && item.values.length) {
        const value = item.values.map((v: any) => v.id).join(',');
        if (item.id === 'name') {
          search.name = value;
        } else if (item.id === 'description') {
          search.description = value;
        } else if (item.id === 'bkvision_report') {
          search.bkvision_report = value;
        } else if (item.id === 'updated_by') {
          search.updated_by = value;
        }
      }
    });
    return search;
  };

  // 获取用户列表（用于更新人远程搜索）
  const { run: fetchUserList } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: { page: 1, page_size: 30 },
    defaultValue: { count: 0, results: [] as any[] },
  });

  // 远程搜索菜单列表（更新人输入时实时搜索）
  const getMenuList = async (item: any, keyword: string) => {
    if (!item) return searchSelectData.value;
    const searchItem = searchSelectData.value.find(s => s.id === item?.id);
    if (searchItem && item.id === 'updated_by') {
      if (keyword) {
        const userList = await fetchUserList({ fuzzy_lookups: keyword });
        searchItem.children = userList.results.map((u: any) => ({
          id: u.username,
          name: `${u.username}(${u.display_name})`,
        }));
      } else {
        searchItem.children = [];
      }
    }
    return (searchSelectData.value.find(s => s.id === item?.id)?.children) || [];
  };

  // 获取图表列表
  const { loading: isLoading, run: fetchChartLists } = useRequest(ToolManageService.fetchChartLists, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      if (Array.isArray(data)) {
        chartLists.value = data;
      }
    },
  });

  // 获取分组
  const { run: fetchGroups } = useRequest(PanelModelService.fetchGroups, {
    defaultValue: {},
    onSuccess: (data) => {
      groups.value = data;
      fetchPanels();
    },
  });

  // 获取报表列表
  const { run: fetchPanels } = useRequest(PanelModelService.fetchPanels, {
    defaultValue: [],
    onSuccess: (panelsData) => {
      // 扁平化：将分组+报表的树形结构转为报表列表
      const flatList: any[] = [];
      panelsData.forEach((panel: PanelModel) => {
        flatList.push({
          id: panel.id,
          group_id: panel.group_id,
          binding_type: panel.binding_type,
          name: panel.name,
          description: panel.description || '--',
          vision_id: panel.vision_id,
          bkvisionReportName: findVisionName(panel.vision_id),
          status: panel.status || 'unpublished',
          updated_by: panel.updated_by || '--',
          updated_at: panel.updated_at || '--',
        });
      });
      allReportList.value = flatList;
      // 刷新表格
      nextTick(() => {
        tableRef.value?.fetchData({});
      });
    },
  });

  // 搜索
  const handleSearch = () => {
    nextTick(() => {
      tableRef.value?.fetchData({ page: 1 });
    });
  };

  // 状态筛选变化
  const handleStatusFilterChange = () => {
    nextTick(() => {
      tableRef.value?.fetchData({ page: 1 });
    });
  };

  // 新建报表
  const handleCreateReport = () => {
    editReportData.value = null;
    reportSidesliderVisible.value = true;
  };

  // 编辑报表
  const handleEdit = (report: any) => {
    editReportData.value = {
      id: String(report.id),
      bkvisionReport: report.vision_id || '',
      name: report.name,
      groupId: null,
      description: report.description === '--' ? '' : report.description,
      status: report.status,
      enabled: report.status === 'published',
    };
    reportSidesliderVisible.value = true;
  };

  // 确认启用/停用
  const handleConfirmToggleStatus = (report: any) => {
    const isPublish = report.status !== 'published';
    InfoBox({
      title: isPublish ? t('确定启用该报表？') : t('确定停用该报表？'),
      subTitle: isPublish ? t('启用后该报表将正常展示') : t('停用后该报表将不再展示'),
      theme: 'warning',
      confirmText: t('确定'),
      cancelText: t('取消'),
      onConfirm: () => {
        const params: any = {
          id: report.id,
          scene_id: getSceneSystemParams().scope_id,
          group_id: report.group_id,
          panel_id: report.id,
          name: report.name,
          status: isPublish ? 'published' as const : 'unpublished' as const,
        };
        PanelModelService.updatePanel(params).then(() => {
          messageSuccess(isPublish ? t('启用成功') : t('停用成功'));
          refreshList();
        });
      },
    });
  };

  // 确认删除
  const handleShowDeleteConfirm = (report: any) => {
    InfoBox({
      title: t('确定删除该报表？'),
      subTitle: t('删除后不可恢复，请谨慎操作'),
      theme: 'danger',
      confirmText: t('确定'),
      cancelText: t('取消'),
      onConfirm: () => {
        PanelModelService.deletePanel({
          id: report.id,
          scene_id: getSceneSystemParams().scope_id,
        }).then(() => {
          messageSuccess(t('删除成功'));
          refreshList();
        });
      },
    });
  };

  // 刷新列表
  const refreshList = () => {
    fetchGroups({
      scope_id: getSceneSystemParams().scope_id,
      scope_type: getSceneSystemParams().scope_type,
    });
  };

  // 报表提交成功
  const handleReportSubmit = () => {
    reportSidesliderVisible.value = false;
    editReportData.value = null;
  };

  // 新建成功
  const handleCreateSuccess = (panelId?: string) => {
    if (panelId) {
      highlightReportId.value = panelId;
    }
    refreshList();
  };

  // 侧边弹窗取消
  const handleReportSidesliderCancel = () => {
    editReportData.value = null;
  };

  // 请求成功回调
  const handleRequestSuccess = () => {
    // 可以在这里处理请求成功后的逻辑
  };

  // 场景变化
  const handleSceneChange = () => {
    fetchChartLists().then(() => {
      fetchGroups({
        scope_id: getSceneSystemParams().scope_id,
        scope_type: getSceneSystemParams().scope_type,
      });
    });
  };

  onMounted(() => {
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
  }

  .search-input {
    width: 400px;
  }
</style>
