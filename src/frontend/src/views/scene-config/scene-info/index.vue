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
        enable-search
        :loading="systemDetailLoading"
        resizable
        :search-data="systemSearchData"
        :search-loading="!systemAllLoaded"
        :search-placeholder="t('搜索 系统名称、系统管理员、系统域名')"
        show-pagination
        stripe
        :title="t('关联系统')"
        :tooltip="t('由蓝鲸审计中心管理员配置，场景管理员仅可查看，如需调整请联系 审计中心平台管理员: ') + configData.platform_admin_users.join(',')"
        :total="systemTotal" />

      <!-- 关联数据报表 -->
      <scene-table
        :columns="dataTableColumns"
        :data="dataTableData"
        enable-search
        :loading="dataTableDetailLoading"
        resizable
        :search-data="dataTableSearchData"
        :search-loading="!dataTableAllLoaded"
        :search-placeholder="t('搜索 数据表名称、数据表ID、管理员')"
        show-pagination
        stripe
        :title="t('关联数据表')"
        :tooltip="t('由蓝鲸审计中心管理员配置，场景管理员仅可查看，可基于数据表配置审计策略，在工具广场创建 SQL 工具，如需调整请联系 审计中心平台管理员: ')
          + configData.platform_admin_users.join(',')"
        :total="dataTableTotal" />
    </div>
  </skeleton-loading>
</template>

<script setup lang="tsx">
  import axios, { type CancelTokenSource } from 'axios';
  import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

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

  const { CancelToken } = axios;
  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const { on: onEvent, off, emit } = useEventBus();

  const SCENE_SELECTOR_STORAGE_KEY = 'scene-system-selector:selected';

  const sceneId = ref(getSceneSystemParams().scope_id);
  // 骨架屏 loading 状态（仅等待场景基础信息）
  const isSkeletonLoading = ref(true);
  // 基础信息字段保存 loading 状态
  const savingField = ref('');
  // 去掉自己管理员后不再刷新当前场景，避免 403 弹出 IAM 权限申请窗
  let skipRefreshAfterUpdate = false;

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
  // ==================== 关联系统表格列配置 ====================
  const systemSearchData = [
    { name: t('系统名称'), id: 'name', placeholder: t('请输入系统名称') },
    {
      name: t('系统管理员'),
      id: 'managers',
      placeholder: t('请选择系统管理员'),
      children: [] as Array<{ id: string; name: string }>,
    },
    { name: t('系统域名'), id: 'system_url', placeholder: t('请输入系统域名') },
  ];

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
  // 数据表名称（ID）组合列配置
  const dataTableCombinedColumn = {
    colKey: 'result_table_name_alias',
    title: () => t('数据表名称（ID）'),
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
  };

  // 固定的数据表列配置（不再根据搜索状态动态切换）
  const dataTableColumns = [
    dataTableCombinedColumn,
    {
      colKey: 'managers',
      title: () => t('管理员'),
      width: 180,
      resizable: true,
      cell: (_h: any, { row }: { row: any }) => (
        <EditTag data={row.managers || []} />
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

  const dataTableSearchData = [
    {
      name: t('数据表名称'),
      id: 'result_table_name_alias',
      placeholder: t('请输入数据表名称'),
      // 数据表名称同时匹配别名/英文ID
      match: (row: Record<string, any>, kw: string) => {
        const lower = kw.toLowerCase();
        return String(row.result_table_name_alias || '').toLowerCase()
          .includes(lower);
      },
    },
    {
      name: t('数据表ID'),
      id: 'result_table_id',
      placeholder: t('请输入数据表ID'),
      // 数据表ID只匹配result_table_id，不匹配名称
      match: (row: Record<string, any>, kw: string) => {
        const lower = kw.toLowerCase();
        return String(row.result_table_id || '').toLowerCase()
          .includes(lower);
      },
    },
    {
      name: t('管理员'),
      id: 'managers',
      placeholder: t('请选择管理员'),
      children: [] as Array<{ id: string; name: string }>,
    },
  ];
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
      if (skipRefreshAfterUpdate) {
        return;
      }
      // 刷新场景信息
      fetchSceneInfo(sceneId.value as any);
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
    systemCount: systemTotal.value || systemDetailList.value.length || 0,
    dataTableCount: sceneInfoData.value.tables?.length || 0,
    strategyCount: sceneInfoData.value.strategy_ids?.length || 0,
    activeRiskCount: sceneInfoData.value.risk_count || 0,
  }));

  const DETAIL_BATCH_SIZE = 10;
  // 详情批量拉取的世代号：离开页面 / 切换场景时递增，用于中止未完成的遍历请求
  let detailFetchToken = 0;
  // 同一轮批量详情共享 CancelToken，离开页时一并取消进行中的 HTTP
  let detailCancelSource: CancelTokenSource | null = null;

  const getDetailRequestPayload = () => ({
    silent: true,
    ...(detailCancelSource ? { cancelTokenSource: detailCancelSource } : {}),
  });

  const abortDetailFetches = () => {
    detailFetchToken += 1;
    detailCancelSource?.cancel('scene-info detail aborted');
    detailCancelSource = null;
  };

  const beginDetailFetches = () => {
    abortDetailFetches();
    detailCancelSource = CancelToken.source();
    detailFetchToken += 1;
    return detailFetchToken;
  };

  // 关联系统表格数据（通过新接口获取有权限的系统列表，再分批获取详情）
  const systemDetailList = ref<Array<Record<string, any>>>([]);
  const systemDetailLoading = ref(false);
  const systemTotal = ref(0);
  const systemAllLoaded = ref(false);

  const mapSystemDetail = (detail: any) => ({
    system_id: detail.system_id,
    name: detail.name || '--',
    managers: detail.managers || [],
    system_url: detail.system_url || '',
    description: detail.description || '',
    source_type: detail.source_type || '',
    status: detail.status || '',
    status_msg: detail.status_msg || '',
    last_time: detail.last_time || '',
  });

  type SystemItem = { system_id: string };

  const fetchSystemDetailsBatch = (systems: SystemItem[]) => Promise.all(systems.map(sys => MetaManageService
    .fetchSystemInfo({ id: sys.system_id }, getDetailRequestPayload())
    .catch(() => null))).then(details => details.filter(Boolean).map(mapSystemDetail));

  const fetchPermissionSystems = async (token: number) => {
    if (!sceneId.value) return;
    systemDetailLoading.value = true;
    systemAllLoaded.value = false;
    systemDetailList.value = [];
    systemTotal.value = 0;
    try {
      const systems = await SceneManageService.fetchScenePermissionSystems(sceneId.value);
      if (token !== detailFetchToken) return;
      if (!systems?.length) {
        return;
      }
      systemTotal.value = systems.length;
      for (let i = 0; i < systems.length; i += DETAIL_BATCH_SIZE) {
        if (token !== detailFetchToken) return;
        const batch = systems.slice(i, i + DETAIL_BATCH_SIZE);
        const batchData = await fetchSystemDetailsBatch(batch);
        if (token !== detailFetchToken) return;
        if (i === 0) {
          systemDetailList.value = batchData;
          systemDetailLoading.value = false;
        } else {
          systemDetailList.value = [...systemDetailList.value, ...batchData];
        }
      }
    } catch {
      if (token !== detailFetchToken) return;
      systemDetailList.value = [];
      systemTotal.value = 0;
    } finally {
      if (token === detailFetchToken) {
        systemDetailLoading.value = false;
        systemAllLoaded.value = true;
      }
    }
  };

  const systemTableData = computed(() => systemDetailList.value);

  // 关联数据报表表格数据（从场景详情接口中获取 tables 数据，再获取详情）
  const dataTableDetailList = ref<Array<Record<string, any>>>([]);
  const dataTableDetailLoading = ref(false);
  // 数据表总条数（用于分页器显示正确总数）
  const dataTableTotal = computed(() => sceneInfoData.value.tables?.length || 0);
  // 数据表是否全部加载完成（用于搜索区域 loading 提示）
  const dataTableAllLoaded = ref(false);

  const mapTableDetail = (detail: any) => ({
    result_table_id: detail.result_table_id || '',
    result_table_name_alias: detail.result_table_name_alias
      || detail.result_table_name || '--',
    managers: detail.managers || [],
    updated_at: detail.updated_at || '',
    created_at: detail.created_at || '',
    sensitivity: detail.sensitivity || '',
    description: detail.description || '',
  });

  // 根据场景详情中的 tables 列表，分批获取数据表详情
  type TableItem = Record<string, any>;

  const fetchTableDetailsBatch = (tables: TableItem[]) => Promise.all(tables.map(table => StrategyManageService
    .fetchTableRtMeta({ table_id: table.table_id }, getDetailRequestPayload())
    .catch(() => null))).then(details => details.filter(Boolean).map(mapTableDetail));

  const fetchPermissionTables = async (token: number) => {
    if (!sceneId.value) return;
    dataTableDetailLoading.value = true;
    dataTableAllLoaded.value = false;
    dataTableDetailList.value = [];
    const tables = sceneInfoData.value.tables || [];
    if (!tables.length) {
      dataTableAllLoaded.value = true;
      dataTableDetailLoading.value = false;
      return;
    }
    try {
      for (let i = 0; i < tables.length; i += DETAIL_BATCH_SIZE) {
        if (token !== detailFetchToken) return;
        const batch = tables.slice(i, i + DETAIL_BATCH_SIZE);
        const batchData = await fetchTableDetailsBatch(batch);
        if (token !== detailFetchToken) return;
        if (i === 0) {
          dataTableDetailList.value = batchData;
          dataTableDetailLoading.value = false;
        } else {
          dataTableDetailList.value = [...dataTableDetailList.value, ...batchData];
        }
      }
    } catch {
      if (token !== detailFetchToken) return;
      dataTableDetailList.value = [];
    } finally {
      if (token === detailFetchToken) {
        dataTableAllLoaded.value = true;
        dataTableDetailLoading.value = false;
      }
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

  const includesUsername = (users: string[] = [], username = '') => {
    if (!username) return false;
    return users.some((item) => {
      const value = String(item || '');
      return value === username || value.split('(')[0] === username;
    });
  };

  const persistSelectedScene = (scene: {
    scene_id: string | number;
    name: string;
    permission?: Record<string, boolean>;
  }) => {
    localStorage.setItem(SCENE_SELECTOR_STORAGE_KEY, JSON.stringify({
      id: String(scene.scene_id),
      name: scene.name,
      type: 'scene',
      permission: scene.permission,
    }));
  };

  const isPlatformAdmin = () => {
    try {
      const permission = JSON.parse(sessionStorage.getItem('userScenePermission') || '{}');
      return Boolean(permission.manage_platform);
    } catch {
      return false;
    }
  };

  // 去掉自己管理员后：切到第一个仍有管理权限的场景；一个都没有则进当前场景权限申请页
  const redirectAfterRemovedSelf = async () => {
    abortDetailFetches();
    const currentId = String(sceneInfoData.value.scene_id || sceneId.value);
    emit('scene-selector-lost-manage', currentId);
    let sceneList: Array<{
      scene_id: number;
      name: string;
      permission?: { manage_scene?: boolean; view_scene?: boolean };
    }> = [];
    try {
      sceneList = await SceneManageService.fetchSceneAll({ status: 'enabled' }) || [];
    } catch {
      sceneList = [];
    }

    const firstManageable = sceneList.find(item => (
      item.permission?.manage_scene === true
      && String(item.scene_id) !== currentId
    ));
    if (firstManageable) {
      persistSelectedScene(firstManageable);
      const nextId = String(firstManageable.scene_id);
      lastLoadedSceneId = undefined;
      await router.replace({
        name: 'sceneInfo',
        query: {
          scene_id: nextId,
          scope_id: nextId,
          scope_type: 'scene',
        },
      });
      await handleSceneChange(nextId);
      return;
    }

    localStorage.removeItem(SCENE_SELECTOR_STORAGE_KEY);
    await router.replace({
      name: 'userLandingPage',
      query: { scene_id: currentId },
    });
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

    const { username } = configData.value;
    const removedSelf = changedKey === 'manager'
      && !isPlatformAdmin()
      && includesUsername(sceneInfoData.value.managers || [], username)
      && Array.isArray(newData.manager)
      && !includesUsername(newData.manager, username);
    skipRefreshAfterUpdate = removedSelf;

    fetchUpdateSceneInfo(updateParams)
      .then(() => {
        if (removedSelf) {
          return redirectAfterRemovedSelf();
        }
        return undefined;
      })
      .finally(() => {
        skipRefreshAfterUpdate = false;
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

  const resolveSceneId = (payload?: unknown) => {
    if (typeof payload === 'string' && payload && payload !== 'allSecen') {
      return payload;
    }
    if (payload && typeof payload === 'object') {
      const item = payload as { id?: string; type?: string };
      if (item.type === 'scene' && item.id && item.id !== 'allSecen') {
        return String(item.id);
      }
    }
    const params = getSceneSystemParams();
    return params.scope_type === 'scene' ? params.scope_id : '';
  };

  const handleSceneChange = async (payload?: unknown) => {
    // 只处理 scene 类型，过滤掉从其他页面残留的 system / cross_xxx 类型旧值
    const newSceneId = resolveSceneId(payload);
    // 同场景重复触发，跳过；请求尚未返回时不要提前关掉骨架屏
    if (newSceneId && newSceneId === lastLoadedSceneId) {
      if (String(sceneInfoData.value.scene_id) === String(newSceneId)) {
        isSkeletonLoading.value = false;
      }
      return;
    }
    // 切换场景前先中止上一轮未完成的详情遍历与进行中的 HTTP
    abortDetailFetches();
    sceneId.value = newSceneId;
    systemDetailList.value = [];
    systemTotal.value = 0;
    systemAllLoaded.value = false;
    dataTableDetailList.value = [];
    dataTableAllLoaded.value = false;
    // 不是有效的场景（如选择了聚合项 / sessionStorage 是 system 类型旧值），不发起请求
    // 此时等待场景选择器初始化后 emit scene:change 事件来触发真正的加载
    if (!sceneId.value) {
      lastLoadedSceneId = undefined;
      return;
    }
    const loadingSceneId = sceneId.value;
    lastLoadedSceneId = loadingSceneId;
    try {
      // 先加载场景基础信息，完成后立即展示统计卡片与基础信息
      await fetchSceneInfo(loadingSceneId as any).catch(() => null);
      // 等待期间已离开页面 / 再次切换场景，不再启动详情遍历
      if (sceneId.value !== loadingSceneId || lastLoadedSceneId !== loadingSceneId) {
        return;
      }
      isSkeletonLoading.value = false;

      // 关联系统、关联数据表异步加载，表格区域各自展示 loading
      const fetchToken = beginDetailFetches();
      void fetchPermissionSystems(fetchToken);
      void fetchPermissionTables(fetchToken);
    } catch {
      if (sceneId.value === loadingSceneId) {
        isSkeletonLoading.value = false;
      }
    }
  };


  // 进入页面时主动加载一次，解决"同场景下切 tab 回来选择器不再 emit"的问题。
  // 无 scene_id 时跳过，等选择器选中后通过 scene:change / 路由 query 再加载。
  onEvent('scene:change', handleSceneChange);
  watch(
    () => String(route.query.scene_id || route.query.scope_id || ''),
    (id) => {
      if (!id || id === 'allSecen') return;
      handleSceneChange(id);
    },
  );
  onMounted(() => {
    handleSceneChange();
  });

  onUnmounted(() => {
    // 离开页面时中止未完成的关联系统 / 关联数据表详情遍历，并取消进行中的 HTTP
    lastLoadedSceneId = undefined;
    sceneId.value = '';
    abortDetailFetches();
    off('scene:change', handleSceneChange);
  });

</script>
