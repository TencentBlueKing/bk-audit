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
            :placeholder="t('搜索 名称、描述、更新人')"
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
        @cancel="handleReportSidesliderCancel"
        @submit="handleReportSubmit"
        @success="handleCreateSuccess" />
    </div>
  </skeleton-loading>
</template>

<script setup lang="ts">
  import { ref, onMounted, nextTick } from 'vue';
  import { InfoBox } from 'bkui-vue';
  import { useI18n } from 'vue-i18n';

  import PanelModelService from '@service/report-config';
  import ToolManageService from '@service/tool-manage';
  import MetaManageService from '@service/meta-manage';

  import PanelModel from '@model/report-config/panel';

  import useRequest from '@hooks/use-request';
  import useMessage from '@/hooks/use-message';

  import ReportCreateSideslider, {
    type ReportFormData,
  } from './components/report-create-sideslider.vue';
  import ReportListTable from './components/report-list-table.vue';

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const tableRef = ref();
  const statusFilter = ref('all');
  const searchKeyword = ref<any[]>([]);
  const searchSelectData = ref([
    { name: t('报表名称'), id: 'name', placeholder: t('请输入报表名称') },
    { name: '描述', id: 'description', placeholder: '请输入描述' },
    { name: '更新人', id: 'updated_by', placeholder: '请输入更新人', children: [] as Array<{ id: string; name: string }> },
  ]);
  const highlightReportId = ref<string | null>(null);
  const chartLists = ref<any[]>([]);
  const reportSidesliderVisible = ref(false);
  const editReportData = ref<ReportFormData | null>(null);

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

  const getSearchParams = (): Record<string, string> => {
    const search = {
      name: '',
      description: '',
      updated_by: '',
    };

    searchKeyword.value.forEach((item) => {
      if (item.values && item.values.length) {
        const value = item.values.map((v: any) => v.id).join(',');
        if (item.id === 'name') {
          search.name = value;
        } else if (item.id === 'description') {
          search.description = value;
        } else if (item.id === 'updated_by') {
          search.updated_by = value;
        }
      }
    });
    return search;
  };

  const buildListParams = (params: Record<string, any> = {}) => {
    const searchParams = getSearchParams();
    const listParams: Record<string, any> = {
      page: params.page || 1,
      page_size: params.page_size || 20,
      ...searchParams,
    };

    if (statusFilter.value === 'enabled') {
      listParams.status = 'published';
    } else if (statusFilter.value === 'disabled') {
      listParams.status = 'unpublished';
    }

    Object.keys(listParams).forEach((key) => {
      if (listParams[key] === '' || listParams[key] === undefined || listParams[key] === null) {
        delete listParams[key];
      }
    });

    return listParams;
  };

  const dataSource = (params: any) => PanelModelService.fetchPlatformPanels(buildListParams(params))
    .then(data => ({
      ...data,
      results: data.results.map((panel: PanelModel) => ({
        id: panel.id,
        binding_type: panel.binding_type,
        name: panel.name,
        description: panel.description || '--',
        vision_id: panel.vision_id,
        bkvisionReportName: findVisionName(panel.vision_id),
        status: panel.status || 'unpublished',
        updated_by: panel.updated_by || '--',
        updated_at: panel.updated_at || '--',
        visibility_type: panel.visibility_type,
        scene_ids: panel.scene_ids || [],
        system_ids: panel.system_ids || [],
      })),
    }));

  const { run: fetchUserList } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: { page: 1, page_size: 30 },
    defaultValue: { count: 0, results: [] as any[] },
  });

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

  const { loading: isLoading, run: fetchChartLists } = useRequest(ToolManageService.fetchChartLists, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      if (Array.isArray(data)) {
        chartLists.value = data;
      }
    },
  });

  const handleSearch = () => {
    nextTick(() => {
      tableRef.value?.fetchData({ page: 1 });
    });
  };

  const handleStatusFilterChange = () => {
    nextTick(() => {
      tableRef.value?.fetchData({ page: 1 });
    });
  };

  const handleCreateReport = () => {
    editReportData.value = null;
    reportSidesliderVisible.value = true;
  };

  const handleEdit = (report: any) => {
    editReportData.value = {
      id: String(report.id),
      bkvisionReport: report.vision_id || '',
      name: report.name,
      description: report.description === '--' ? '' : report.description,
      status: report.status,
      enabled: report.status === 'published',
      visibility_type: report.visibility_type || 'all_visible',
      scene_ids: report.scene_ids || [],
      system_ids: report.system_ids || [],
    };
    reportSidesliderVisible.value = true;
  };

  const handleConfirmToggleStatus = (report: any) => {
    const isPublish = report.status !== 'published';
    InfoBox({
      title: isPublish ? t('确定启用该报表？') : t('确定停用该报表？'),
      subTitle: isPublish ? t('启用后该报表将正常展示') : t('停用后该报表将不再展示'),
      theme: 'warning',
      confirmText: t('确定'),
      cancelText: t('取消'),
      onConfirm: () => {
        PanelModelService.publishPlatformPanel({
          panel_id: report.id,
          status: isPublish ? 'published' : 'unpublished',
        }).then(() => {
          messageSuccess(isPublish ? t('启用成功') : t('停用成功'));
          refreshList();
        });
      },
    });
  };

  const handleShowDeleteConfirm = (report: any) => {
    InfoBox({
      title: t('确定删除该报表？'),
      subTitle: t('删除后不可恢复，请谨慎操作'),
      theme: 'danger',
      confirmText: t('确定'),
      cancelText: t('取消'),
      onConfirm: () => {
        PanelModelService.deletePlatformPanel({
          panel_id: report.id,
        }).then(() => {
          messageSuccess(t('删除成功'));
          refreshList();
        });
      },
    });
  };

  const refreshList = () => {
    nextTick(() => {
      tableRef.value?.fetchData({});
    });
  };

  const handleReportSubmit = () => {
    reportSidesliderVisible.value = false;
    editReportData.value = null;
  };

  const handleCreateSuccess = (panelId?: string) => {
    if (panelId) {
      highlightReportId.value = panelId;
    }
    refreshList();
  };

  const handleReportSidesliderCancel = () => {
    editReportData.value = null;
  };

  const handleRequestSuccess = () => {
    // 可以在这里处理请求成功后的逻辑
  };

  onMounted(() => {
    fetchChartLists();
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
