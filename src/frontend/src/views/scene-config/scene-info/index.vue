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

  import BaseInfo from './components/base-info.vue';
  import SampleDialog from './components/sample-dialog.vue';
  import SceneTable from './components/scene-table.vue';
  import StatCards from './components/stat-cards.vue';

  const router = useRouter();
  const { t } = useI18n();

  // 模拟场景基础数据
  const sceneData = ref({
    id: 100001,
    name: '主机安全审计',
    description: '覆盖主机登录、文件变更、进程启停、权限变更等操作的安全审计，结合CMDB业务拓扑进行关联分析，识别异常运维行为和潜在入侵风险。',
    manager: '赵明辉（zhaominghui）',
    managerCount: 2,
    users: '张三（zhangsan）、李四（lisi）、王五（wangwu）',
    updatedBy: '赵明辉（zhaominghui）',
    updatedAt: '2026-03-04 16:22:37',
    systemCount: 3,
    dataTableCount: 5,
    strategyCount: 18,
    activeRiskCount: 127,
  });

  // 统计卡片数据（从 sceneData 中提取）
  const statCardsData = computed(() => ({
    systemCount: sceneData.value.systemCount,
    dataTableCount: sceneData.value.dataTableCount,
    strategyCount: sceneData.value.strategyCount,
    activeRiskCount: sceneData.value.activeRiskCount,
  }));

  // 更新场景数据（来自基础信息组件的行内编辑）
  const handleUpdateSceneData = (newData: any) => {
    sceneData.value = {
      ...sceneData.value,
      ...newData,
    };
  };

  // 跳转到审计策略列表页
  const handleGoStrategy = () => {
    router.push({ name: 'strategyList' });
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
    <span>{row.recentDataCount.toLocaleString()}</span>
  );

  // 渲染最近数据时间列
  const renderRecentDataTimeCell = (_h: any, { row }: { row: any }) => (
    <span>
      <span class={['time-label', getTimeLabelClass(row.recentDataTimeLabelTheme)]}>
        {row.recentDataTimeLabel}
      </span>
      <span class="ml8">{row.recentDataTime}</span>
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

  // ==================== 关联系统模拟数据 ====================
  const systemTableData = ref([
    {
      id: 1,
      name: '蓝鲸权限中心',
      admin: '李梓发',
      domain: 'http://xima.ec/jzlf',
      dataScope: '部分数据',
      fieldCount: '10 个',
      recentDataCount: 67440,
      recentDataTimeLabel: '2分钟前',
      recentDataTimeLabelTheme: 'success',
      recentDataTime: '2026-03-30 02:12:55',
    },
    {
      id: 2,
      name: '蓝鲸配置平台',
      admin: '吴令',
      domain: 'http://vcqmomib.np/dhdxtup',
      dataScope: '全部数据',
      fieldCount: '10 个',
      recentDataCount: 94922,
      recentDataTimeLabel: '2分钟前',
      recentDataTimeLabelTheme: 'success',
      recentDataTime: '2026-03-24 13:37:24',
    },
    {
      id: 3,
      name: '蓝鲸作业平台',
      admin: '李金泽',
      domain: 'http://pefgffci.bj/jshvg',
      dataScope: '全部数据',
      fieldCount: '10 个',
      recentDataCount: 10595,
      recentDataTimeLabel: '3小时前',
      recentDataTimeLabelTheme: 'warning',
      recentDataTime: '2026-01-29 08:34:04',
    },
    {
      id: 4,
      name: '蓝鲸容器管理平台',
      admin: '孙书贤',
      domain: 'http://hrndkdpi.cn/pnhw',
      dataScope: '全部数据',
      fieldCount: '10 个',
      recentDataCount: 88410,
      recentDataTimeLabel: '10小时前',
      recentDataTimeLabelTheme: 'warning',
      recentDataTime: '2026-01-27 20:35:20',
    },
    {
      id: 5,
      name: '蓝鲸监控平台',
      admin: '郑清予',
      domain: 'http://wvqlq.lt/vbptc',
      dataScope: '全部数据',
      fieldCount: '10 个',
      recentDataCount: 91933,
      recentDataTimeLabel: '1 天前',
      recentDataTimeLabelTheme: 'danger',
      recentDataTime: '2026-01-07 01:59:52',
    },
  ]);

  // ==================== 关联数据报表模拟数据 ====================
  const dataTableData = [
    {
      id: 1,
      name: '审计事件总表（bk_audit_event）',
      admin: '李辉煌',
      dataScope: '部分数据',
      fieldCount: '10 个',
      recentDataCount: 67440,
      recentDataTimeLabel: '2分钟前',
      recentDataTimeLabelTheme: 'success',
      recentDataTime: '2026-03-30 02:12:55',
    },
    {
      id: 2,
      name: '审计事件总表（bk_audit_event）',
      admin: '王艳娇',
      dataScope: '部分数据',
      fieldCount: '10 个',
      recentDataCount: 94922,
      recentDataTimeLabel: '2分钟前',
      recentDataTimeLabelTheme: 'success',
      recentDataTime: '2026-03-24 13:37:24',
    },
    {
      id: 3,
      name: '审计事件总表（bk_audit_event）',
      admin: '李孜斌',
      dataScope: '部分数据',
      fieldCount: '10 个',
      recentDataCount: 10595,
      recentDataTimeLabel: '3分钟前',
      recentDataTimeLabelTheme: 'success',
      recentDataTime: '2026-01-29 08:34:04',
    },
    {
      id: 4,
      name: '审计事件总表（bk_audit_event）',
      admin: '钱洲西',
      dataScope: '部分数据',
      fieldCount: '10 个',
      recentDataCount: 88410,
      recentDataTimeLabel: '5分钟前',
      recentDataTimeLabelTheme: 'success',
      recentDataTime: '2026-01-27 20:35:20',
    },
    {
      id: 5,
      name: '审计事件总表（bk_audit_event）',
      admin: '孙恒香',
      dataScope: '部分数据',
      fieldCount: '10 个',
      recentDataCount: 91933,
      recentDataTimeLabel: '15 分钟前',
      recentDataTimeLabelTheme: 'success',
      recentDataTime: '2026-01-07 01:59:52',
    },
  ];
</script>
