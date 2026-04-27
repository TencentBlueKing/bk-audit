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
  <div class="scene-info-page">
    <!-- 顶部统计卡片 -->
    <stat-cards
      :scene-data="statCardsData"
      @go-risk="handleGoRisk"
      @go-strategy="handleGoStrategy" />

    <!-- 基础信息 -->
    <base-info
      :scene-data="sceneData"
      @update:scene-data="handleUpdateSceneData" />

    <!-- 关联系统 -->
    <scene-table
      :columns="systemColumns"
      :data="systemTableData"
      resizable
      stripe
      :title="t('关联系统')"
      :tooltip="t('由蓝鲸审计中心管理员配置，场景管理员仅可查看，如需调整请联系 审计中心平台管理员')" />

    <!-- 关联数据报表 -->
    <scene-table
      :columns="dataTableColumns"
      :data="dataTableData"
      resizable
      stripe
      :title="t('关联数据报表')"
      :tooltip="t('由蓝鲸审计中心管理员配置，场景管理员仅可查看，可基于数据报表配置审计策略，在工具广场创建 SQL 工具，如需调整请联系 审计中心平台管理员')" />

    <!-- 最新数据样本弹窗 -->
    <sample-dialog
      v-model:is-show="sampleDialogVisible"
      :data="sampleTableData"
      :subtitle="sampleDialogSubtitle" />
  </div>
</template>

<script setup lang="tsx">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import SceneManageService from '@service/scene-manage';

  import SceneModel from '@model/scene/scene';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import BaseInfo from './components/base-info.vue';
  import SampleDialog from './components/sample-dialog.vue';
  import SceneTable from './components/scene-table.vue';
  import StatCards from './components/stat-cards.vue';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  const router = useRouter();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  // 从 sessionStorage 获取当前场景 ID
  const scopeParams = getSceneSystemParams();
  const sceneId = scopeParams.scope_id;

  // 调用接口获取场景信息
  const {
    data: sceneInfoData,
    run: fetchSceneInfo,
  } = useRequest(SceneManageService.fetchSceneInfo, {
    defaultValue: new SceneModel(),
    defaultParams: sceneId,
    manual: true,
  });

  // 调用接口更新场景基础信息（场景管理员）
  const {
    run: fetchUpdateSceneInfo,
  } = useRequest(SceneManageService.updateSceneInfo, {
    defaultValue: new SceneModel(),
    onSuccess: () => {
      messageSuccess(t('保存成功'));
      // 刷新场景信息
      fetchSceneInfo(sceneId);
    },
  });

  // 场景基础数据（从接口返回数据中映射）
  const sceneData = computed(() => ({
    id: sceneInfoData.value.scene_id,
    name: sceneInfoData.value.name,
    description: sceneInfoData.value.description,
    manager: sceneInfoData.value.managers || [],
    users: sceneInfoData.value.users || [],
    updatedBy: sceneInfoData.value.updated_by || '--',
    updatedAt: sceneInfoData.value.updated_at || '--',
  }));

  // 统计卡片数据（从接口返回数据中提取）
  const statCardsData = computed(() => ({
    systemCount: sceneInfoData.value.systems?.length || 0,
    dataTableCount: sceneInfoData.value.tables?.length || 0,
    strategyCount: sceneInfoData.value.strategy_ids?.length || 0,
    activeRiskCount: sceneInfoData.value.risk_count || 0,
  }));

  // 关联系统表格数据（从接口返回数据中提取，后端暂时返回空数组）
  const systemTableData = computed(() => sceneInfoData.value.systems || []);

  // 关联数据报表表格数据（从接口返回数据中提取，后端暂时返回空数组）
  const dataTableData = computed(() => sceneInfoData.value.tables || []);

  // 更新场景数据（来自基础信息组件的行内编辑）
  const handleUpdateSceneData = (newData: any) => {
    // 构建更新参数，将前端字段映射回后端字段
    const updateParams: Record<string, any> = {
      sceneId: sceneInfoData.value.scene_id,
    };
    // 检查哪些字段发生了变化并只提交变化的字段
    if (newData.manager !== undefined) {
      updateParams.managers = newData.manager;
    }
    if (newData.users !== undefined) {
      updateParams.users = newData.users;
    }
    if (newData.name !== undefined) {
      updateParams.name = newData.name;
    }
    if (newData.description !== undefined) {
      updateParams.description = newData.description;
    }
    fetchUpdateSceneInfo(updateParams);
  };

  // 跳转到审计策略列表页（携带 strategy_ids）
  const handleGoStrategy = () => {
    const strategyIds = sceneInfoData.value.strategy_ids || [];
    router.push({
      name: 'strategyList',
      query: strategyIds.length ? { strategy_id: strategyIds.join(',') } : {},
    });
  };

  // 新开标签页跳转到风险列表页
  const handleGoRisk = () => {
    const routeData = router.resolve({ name: 'riskManageList' });
    window.open(routeData.href, '_blank');
  };

  // ==================== 可用字段模拟数据 ====================
  const mockFieldData = [
    { fieldName: 'action_id', fieldLabel: '操作 ID', fieldDesc: '系统上报的操作唯一标识，如 create_host、edit_biz' },
    { fieldName: 'resource_type', fieldLabel: '资源类型', fieldDesc: '操作涉及的资源类型标识' },
    { fieldName: 'operator', fieldLabel: '操作人', fieldDesc: '执行该操作的用户名' },
    { fieldName: 'operate_time', fieldLabel: '操作时间', fieldDesc: '操作发生的时间戳' },
    { fieldName: 'bk_biz_id', fieldLabel: '业务 ID', fieldDesc: '操作所属的蓝鲸业务 ID' },
    { fieldName: 'source_ip', fieldLabel: '来源 IP', fieldDesc: '发起操作的客户端 IP 地址' },
    { fieldName: 'result_code', fieldLabel: '结果码', fieldDesc: '操作执行的返回码，0 表示成功' },
    { fieldName: 'result_content', fieldLabel: '结果内容', fieldDesc: '操作执行的返回内容描述' },
    { fieldName: 'extend_data', fieldLabel: '扩展数据', fieldDesc: '操作的扩展信息，JSON 格式' },
    { fieldName: 'snapshot_data', fieldLabel: '快照数据', fieldDesc: '操作前后的资源快照数据' },
  ];

  // 可用字段表格列配置（用于 popover 内的 SceneTable）
  const fieldTableColumns = [
    { colKey: 'fieldName', title: () => t('字段名'), width: 160 },
    { colKey: 'fieldLabel', title: () => t('字段中文名'), width: 140 },
    { colKey: 'fieldDesc', title: () => t('字段说明') },
  ];

  // ==================== 最新数据样本弹窗 ====================
  const sampleDialogVisible = ref(false);
  const sampleDialogSubtitle = ref('');

  // 模拟最新数据样本数据
  const sampleTableData = ref<Array<{ fieldName: string; fieldLabel: string; value: string }>>([
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
    { fieldName: 'action_id', fieldLabel: '操作 ID', value: 'evt-20260316-00847293' },
  ]);

  // 打开最新数据样本弹窗
  const handleShowSample = (row: any) => {
    sampleDialogSubtitle.value = row.name || '';
    sampleDialogVisible.value = true;
  };

  // ==================== 公共列渲染函数 ====================
  // 获取时间标签的颜色样式
  const getTimeLabelClass = (theme: string) => {
    const classMap: Record<string, string> = {
      danger: 'time-label-danger',
      warning: 'time-label-warning',
      success: 'time-label-success',
    };
    return classMap[theme] || '';
  };

  // 渲染可用字段列（带下划线 + hover 气泡窗）
  const renderFieldCountCell = (_h: any, { row }: { row: any }) => (
    <bk-popover
      placement="bottom"
      theme="light"
      trigger="hover"
      width={560}>
      {{
        default: () => (
          <span class="field-count-link">{row.fieldCount}</span>
        ),
        content: () => (
          <div class="field-popover-content">
            <SceneTable
              columns={fieldTableColumns}
              data={mockFieldData}
              resizable
              row-height={32}
              show-pagination
              limit={10}
              limit-list={[10, 20]}
              max-height={400}
            />
          </div>
        ),
      }}
    </bk-popover>
  );

  // 渲染近 7 天数据量列
  const renderRecentDataCountCell = (_h: any, { row }: { row: any }) => (
    <span>{row.recentDataCount != null ? row.recentDataCount.toLocaleString() : '--'}</span>
  );

  // 渲染最近数据时间列
  const renderRecentDataTimeCell = (_h: any, { row }: { row: any }) => (
    <span>
      <span class={['time-label', getTimeLabelClass(row.recentDataTimeLabelTheme)]}>
        {row.recentDataTimeLabel || '--'}
      </span>
      <span class="ml8">{row.recentDataTime || '--'}</span>
    </span>
  );

  // 渲染操作列（最新数据样本按钮）
  const renderActionCell = (_h: any, { row }: { row: any }) => (
    <bk-button
      text
      theme="primary"
      onClick={() => handleShowSample(row)}>
      {t('最新数据样本')}
    </bk-button>
  );

  // ==================== 关联系统表格列配置 ====================
  const systemColumns = [
    {
      colKey: 'name',
      title: () => t('系统名称'),
      width: 180,
      resizable: true,
    },
    {
      colKey: 'admin',
      title: () => t('系统管理员'),
      width: 120,
      resizable: true,
    },
    {
      colKey: 'domain',
      title: () => t('系统域名'),
      width: 220,
      resizable: true,
      cell: (_h: any, { row }: { row: any }) => (
        <span class="domain-cell">
          <span class="domain-text">{row.domain}</span>
          <a
            href={row.domain}
            target="_blank"
            class="domain-jump-icon"
            onClick={(e: Event) => e.stopPropagation()}>
            <audit-icon type="jump-link" />
          </a>
        </span>
      ),
    },
    {
      colKey: 'dataScope',
      title: () => t('数据范围'),
      width: 120,
      resizable: true,
    },
    {
      colKey: 'fieldCount',
      title: () => t('可用字段'),
      width: 100,
      resizable: true,
      cell: renderFieldCountCell,
    },
    {
      colKey: 'recentDataCount',
      title: () => t('近 7 天数据量'),
      width: 130,
      resizable: true,
      cell: renderRecentDataCountCell,
    },
    {
      colKey: 'recentDataTime',
      title: () => t('最近数据时间'),
      width: 280,
      resizable: true,
      cell: renderRecentDataTimeCell,
    },
    {
      colKey: 'action',
      title: () => t('操作'),
      width: 120,
      resizable: true,
      cell: renderActionCell,
    },
  ];

  // ==================== 关联数据报表表格列配置 ====================
  const dataTableColumns = [
    {
      colKey: 'name',
      title: () => t('数据报表名称'),
      width: 260,
      resizable: true,
    },
    {
      colKey: 'admin',
      title: () => t('管理员'),
      width: 120,
      resizable: true,
    },
    {
      colKey: 'dataScope',
      title: () => t('数据范围'),
      width: 120,
      resizable: true,
    },
    {
      colKey: 'fieldCount',
      title: () => t('可用字段'),
      width: 100,
      resizable: true,
      cell: renderFieldCountCell,
    },
    {
      colKey: 'recentDataCount',
      title: () => t('近 7 天数据量'),
      width: 130,
      resizable: true,
      cell: renderRecentDataCountCell,
    },
    {
      colKey: 'recentDataTime',
      title: () => t('最近数据时间'),
      width: 280,
      resizable: true,
      cell: renderRecentDataTimeCell,
    },
    {
      colKey: 'action',
      title: () => t('操作'),
      width: 120,
      resizable: true,
      cell: renderActionCell,
    },
  ];
</script>
