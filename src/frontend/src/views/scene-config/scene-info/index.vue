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
    :loading="isSkeletonLoading"
    name="storageList">
    <bk-loading
      :loading="pageLoading">
      <div class="scene-info-page">
        <!-- 顶部统计卡片 -->
        <stat-cards
          :scene-data="statCardsData"
          @go-risk="handleGoRisk"
          @go-strategy="handleGoStrategy" />

        <!-- 基础信息 -->
        <base-info
          :can-edit="canEdit"
          :saving-field="savingField"
          :scene-data="sceneData"
          @update:scene-data="handleUpdateSceneData" />

        <!-- 关联系统 -->
        <scene-table
          :columns="systemColumns"
          :data="systemTableData"
          resizable
          stripe
          :title="t('关联系统')"
          :tooltip="t('由蓝鲸审计中心管理员配置，场景管理员仅可查看，如需调整请联系 审计中心平台管理员: ') + configData.platform_admin_users.join(',')" />

        <!-- 关联数据报表 -->
        <scene-table
          :columns="dataTableColumns"
          :data="dataTableData"
          resizable
          stripe
          :title="t('关联数据表')"
          :tooltip="t('由蓝鲸审计中心管理员配置，场景管理员仅可查看，可基于数据表配置审计策略，在工具广场创建 SQL 工具，如需调整请联系 审计中心平台管理员: ')
            + configData.platform_admin_users.join(',')" />
      </div>
    </bk-loading>
  </skeleton-loading>
</template>

<script setup lang="tsx">
  import { computed, onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import RootManageService from '@service/root-manage';
  import SceneManageService from '@service/scene-manage';
  import StrategyManageService from '@service/strategy-manage';

  import ConfigModel from '@model/root/config';
  import SceneModel from '@model/scene/scene';

  import useEventBus from '@hooks/use-event-bus';
  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';
  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  import BaseInfo from './components/base-info.vue';
  import SceneTable from './components/scene-table.vue';
  import StatCards from './components/stat-cards.vue';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  const router = useRouter();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const { on: onEvent, off } = useEventBus();

  const sceneId = ref(getSceneSystemParams().scope_id);
  // 骨架屏 loading 状态（首次进入页面时展示）
  const isSkeletonLoading = ref(true);
  // 页面整体 loading 状态（切换场景时）
  const pageLoading = ref(false);
  // 基础信息字段保存 loading 状态
  const savingField = ref('');

  // 是否有编辑权限：平台管理或场景管理权限
  const canEdit = computed(() => {
    try {
      const permissionStr = sessionStorage.getItem('userScenePermission');
      if (permissionStr) {
        const permission = JSON.parse(permissionStr);
        return !!(permission.manage_platform || permission.manage_scene);
      }
      return false;
    } catch {
      return false;
    }
  });

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  const {
    data: sceneInfoData,
    run: fetchSceneInfo,
  } = useRequest(SceneManageService.fetchSceneInfo, {
    defaultValue: new SceneModel(),
  });
  const {
    run: fetchUpdateSceneInfo,
  } = useRequest(SceneManageService.updateSceneInfo, {
    defaultValue: new SceneModel(),
    onSuccess: () => {
      messageSuccess(t('保存成功'));
      // 刷新场景信息
      fetchSceneInfo(sceneId.value);
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
    systemCount: systemDetailList.value.length || 0,
    dataTableCount: sceneInfoData.value.tables?.length || 0,
    strategyCount: sceneInfoData.value.strategy_ids?.length || 0,
    activeRiskCount: sceneInfoData.value.risk_count || 0,
  }));

  // 关联系统表格数据（通过新接口获取有权限的系统列表，再获取详情）
  const systemDetailList = ref<Array<Record<string, any>>>([]);
  const systemDetailLoading = ref(false);

  // 获取场景下有权限的系统列表，再逐个获取系统详情
  const fetchPermissionSystems = async () => {
    if (!sceneId.value) return;
    systemDetailLoading.value = true;
    try {
      const systems = await SceneManageService.fetchScenePermissionSystems(sceneId.value);
      if (!systems || systems.length === 0) {
        systemDetailList.value = [];
        return;
      }
      const detailPromises = systems.map((sys: { system_id: string; system_name: string }) => MetaManageService
        .fetchSystemInfo({ id: sys.system_id })
        .catch(() => null));
      const details = await Promise.all(detailPromises);
      systemDetailList.value = details
        .filter(Boolean)
        .map((detail: any) => ({
          system_id: detail.system_id,
          name: detail.name || '--',
          managers: detail.managers || [],
          system_url: detail.system_url || '',
          description: detail.description || '',
          source_type: detail.source_type || '',
          status: detail.status || '',
          status_msg: detail.status_msg || '',
          last_time: detail.last_time || '',
        }));
    } catch (e) {
      systemDetailList.value = [];
    } finally {
      systemDetailLoading.value = false;
    }
  };

  const systemTableData = computed(() => systemDetailList.value);

  // 关联数据报表表格数据（从场景详情接口中获取 tables 数据，再获取详情）
  const dataTableDetailList = ref<Array<Record<string, any>>>([]);
  const dataTableDetailLoading = ref(false);

  // 根据场景详情中的 tables 列表，逐个获取数据表详情
  const fetchPermissionTables = async () => {
    if (!sceneId.value) return;
    dataTableDetailLoading.value = true;
    try {
      const tables = sceneInfoData.value.tables || [];
      if (!tables || tables.length === 0) {
        dataTableDetailList.value = [];
        return;
      }
      const detailPromises = tables.map((table: Record<string, any>) => StrategyManageService
        .fetchTableRtMeta({ table_id: table.table_id })
        .catch(() => null));
      const details = await Promise.all(detailPromises);
      dataTableDetailList.value = details
        .filter(Boolean)
        .map((detail: any) => ({
          result_table_id: detail.result_table_id || '',
          result_table_name_alias: detail.result_table_name_alias
            || detail.result_table_name || '--',
          managers: detail.managers || [],
          updated_at: detail.updated_at || '',
          created_at: detail.created_at || '',
          sensitivity: detail.sensitivity || '',
          description: detail.description || '',
        }));
    } catch (e) {
      dataTableDetailList.value = [];
    } finally {
      dataTableDetailLoading.value = false;
    }
  };

  const dataTableData = computed(() => dataTableDetailList.value);

  // ==================== 最近数据时间渲染工具函数 ====================
  // 计算相对时间文本
  const getRelativeTimeText = (timeStr: string) => {
    const now = new Date().getTime();
    const target = new Date(timeStr).getTime();
    const diffMs = now - target;
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMinutes < 60) {
      return `${Math.max(diffMinutes, 1)}${t('分钟前')}`;
    }
    if (diffHours < 24) {
      return `${diffHours}${t('小时前')}`;
    }
    return `${diffDays}${t('天前')}`;
  };

  // 根据时间差获取标签颜色主题
  // ≤2小时(120分钟): 绿色(success)  >2小时且≤24小时: 橙色(warning)  >24小时: 红色(danger)
  const getTimeTagTheme = (timeStr: string) => {
    const now = new Date().getTime();
    const target = new Date(timeStr).getTime();
    const diffMs = now - target;
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours <= 2) return 'success';
    if (diffHours <= 24) return 'warning';
    return 'danger';
  };

  // 渲染最近数据时间单元格
  const renderLastTimeCell = (_h: any, { row }: { row: any }, field: string) => {
    const timeStr = row[field];
    if (!timeStr) return <span>--</span>;
    return (
      <span class="last-time-cell">
        <bk-tag theme={getTimeTagTheme(timeStr)}>
          {getRelativeTimeText(timeStr)}
        </bk-tag>
        <span class="last-time-text">{timeStr}</span>
      </span>
    );
  };

  // 更新场景数据（来自基础信息组件的行内编辑）
  const handleUpdateSceneData = (newData: any, changedKey = '') => {
    // 子组件直接传入正在编辑的字段 key，用于显示 loading 状态
    savingField.value = changedKey;

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
    fetchUpdateSceneInfo(updateParams)
      .finally(() => {
        savingField.value = '';
      });
  };

  // 新开标签页跳转到审计策略列表页（带已启用状态筛选，不带策略ID）
  const handleGoStrategy = () => {
    const routeData = router.resolve({
      name: 'strategyList',
      query: { status: 'running' },
    });
    window.open(routeData.href, '_blank');
  };

  // 新开标签页跳转到场景风险列表页（带活跃状态筛选）
  const handleGoRisk = () => {
    // 活跃状态：录入中、待处理、处理中、自动处理审批中、套餐处理中
    const activeStatuses = ['new', 'await_deal', 'processing', 'for_approve', 'auto_process'];
    const routeData = router.resolve({
      name: 'sceneRiskManageList',
      query: {
        scene_id: sceneId.value,
        status: activeStatuses.join(','),
      },
    });
    window.open(routeData.href, '_blank');
  };

  // 已加载过的 sceneId，用于去重（onMounted 主动加载 + 选择器初始化 emit 两个触发源可能重复）
  let lastLoadedSceneId: string | undefined;

  const handleSceneChange = async () => {
    const params = getSceneSystemParams();
    // 只处理 scene 类型，过滤掉从其他页面残留的 system / cross_xxx 类型旧值
    const newSceneId = params.scope_type === 'scene' ? params.scope_id : '';
    // 同场景重复触发，跳过
    if (newSceneId && newSceneId === lastLoadedSceneId) {
      isSkeletonLoading.value = false;
      return;
    }
    sceneId.value = newSceneId;
    systemDetailList.value = [];
    dataTableDetailList.value = [];
    // 不是有效的场景（如选择了聚合项 / sessionStorage 是 system 类型旧值），不发起请求
    // 此时等待场景选择器初始化后 emit scene:change 事件来触发真正的加载
    if (!sceneId.value) {
      lastLoadedSceneId = undefined;
      return;
    }
    lastLoadedSceneId = sceneId.value;
    // 非首次加载（场景切换）展示页面 loading
    if (!isSkeletonLoading.value) {
      pageLoading.value = true;
    }
    try {
      // 先获取场景信息（fetchPermissionTables 依赖 sceneInfoData 中的 tables 数据）
      await Promise.all([
        fetchSceneInfo(sceneId.value).catch(() => null),
        fetchPermissionSystems(),
      ]);
      // 场景信息获取完成后，再根据其中的 tables 获取数据表详情
      await fetchPermissionTables();
    } finally {
      isSkeletonLoading.value = false;
      pageLoading.value = false;
    }
  };

  // 监听场景变化（场景选择器切换 / 自动选中第一个场景时触发）
  onEvent('scene:change', handleSceneChange);

  // 进入页面时主动加载一次，解决"同场景下切 tab 回来选择器不再 emit"的问题。
  // 仅当 sessionStorage 里是有效的 scene 类型时才会真正发起请求；
  // 否则（如从系统页面切过来，残留的是 system 类型）会跳过，等待选择器自动选场景后 emit 事件触发。
  onMounted(() => {
    handleSceneChange();
  });

  onUnmounted(() => {
    off('scene:change', handleSceneChange);
  });

  // ==================== 关联系统表格列配置 ====================
  const systemColumns = [
    {
      colKey: 'name',
      title: () => t('系统名称'),
      width: 180,
      resizable: true,
    },
    {
      colKey: 'managers',
      title: () => t('系统管理员'),
      width: 180,
      resizable: true,
      cell: (_h: any, { row }: { row: any }) => (
        <EditTag data={row.managers || []} />
      ),
    },
    {
      colKey: 'system_url',
      title: () => t('系统域名'),
      width: 220,
      resizable: true,
      cell: (_h: any, { row }: { row: any }) => (
        row.system_url
          ? <span class="domain-cell">
              <span class="domain-text">{row.system_url}</span>
              <a
                href={row.system_url}
                target="_blank"
                class="domain-jump-icon"
                onClick={(e: Event) => e.stopPropagation()}>
                <audit-icon type="jump-link" />
              </a>
            </span>
          : <span>--</span>
      ),
    },
    {
      colKey: 'data_scope',
      title: () => t('数据范围'),
      width: 150,
      resizable: true,
      cell: () => <span>{t('全部数据')}</span>,
    },
    {
      colKey: 'last_time',
      title: () => t('最近数据时间'),
      width: 280,
      resizable: true,
      cell: (_h: any, { row }: { row: any }) => renderLastTimeCell(_h, { row }, 'last_time'),
    },
  ];

  // ==================== 关联数据报表表格列配置 ====================
  const dataTableColumns = [
    {
      colKey: 'result_table_name_alias',
      title: () => t('数据表名称'),
      width: 250,
      resizable: true,
      cell: (_h: any, { row }: { row: any }) => {
        const text = `${row.result_table_name_alias}${row.result_table_id ? `(${row.result_table_id})` : ''}`;
        return (
          <div style="max-width: 450px;">
            <ShowTooltipsText data={text} />
          </div>
        );
      },
    },
    {
      colKey: 'managers',
      title: () => t('管理员'),
      width: 180,
      resizable: true,
      cell: (_h: any, { row }: { row: any }) => (
        <EditTag data={row.managers || []}  />
      ),
    },
    {
      colKey: 'data_scope',
      title: () => t('数据范围'),
      width: 150,
      resizable: true,
      cell: () => <span>{t('全部数据')}</span>,
    },
    {
      colKey: 'updated_at',
      title: () => t('最近数据时间'),
      width: 280,
      resizable: true,
      cell: (_h: any, { row }: { row: any }) => renderLastTimeCell(_h, { row }, 'updated_at'),
    },
  ];
</script>
