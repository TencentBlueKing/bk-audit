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
    <div class="scene-manage-page">
      <!-- 头部操作区 -->
      <div class="scene-manage-header">
        <div class="header-left">
          <bk-button
            class="mr8"
            theme="primary"
            @click="handleCreateScene">
            <audit-icon
              class="mr4"
              type="add" />
            {{ t('新建场景') }}
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
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.all }}
              </bk-tag>
            </bk-radio-button>
            <bk-radio-button label="enabled">
              <audit-icon
                class="mr4"
                svg
                type="normal" />
              {{ t('已启用') }}
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.enabled }}
              </bk-tag>
            </bk-radio-button>
            <bk-radio-button label="disabled">
              <audit-icon
                class="mr4"
                svg
                type="unknown" />
              {{ t('已停用') }}
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.disabled }}
              </bk-tag>
            </bk-radio-button>
          </bk-radio-group>
          <bk-search-select
            v-model="searchValue"
            class="search-input"
            clearable
            :data="searchSelectData"
            :defaut-using-item="{ inputHtml: t('请选择') }"
            :get-menu-list="getMenuList"
            :placeholder="t('搜索场景 ID、场景名称、场景描述、管理员、使用者、更新人')"
            unique-select
            @update:model-value="handleSearch" />
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="scene-manage-content">
        <tdesign-list
          ref="listRef"
          allow-multiple-sort
          :columns="tableColumns"
          :data-source="dataSource"
          need-empty-search-tip
          :row-class-name="getSceneRowClassName"
          row-key="scene_id"
          @clear-search="handleClearSearch"
          @request-success="handleRequestSuccess" />
      </div>

      <!-- 删除确认弹窗 -->
      <bk-dialog
        v-model:is-show="deleteDialogVisible"
        dialog-type="confirm"
        footer-align="center"
        header-align="center"
        :quick-close="false"
        :title="t('')">
        <div class="confirm-dialog-content">
          <div class="dialog-title-row">
            <img
              class="tip-icon"
              src="@images/tip-icon.svg">
            <div class="dialog-title-text">
              {{ t('确定删除该场景？') }}
            </div>
          </div>
          <div class="warning-message">
            <span>{{ t('此操作将') }}</span>
            <span class="warning-text">{{ t(' 永久删除该场景及其所有关联配置（策略、规则、通知组等）') }}</span>
            <span>{{ t('，不可恢复，请谨慎操作！') }}</span>
          </div>
          <div class="confirm-input-label">
            {{ t('请输入场景名称「') }}
            <span
              v-bk-tooltips="t('点击复制')"
              class="scene-name"
              @click="handleCopySceneName(currentDeleteScene?.name)">
              {{ currentDeleteScene?.name }}
            </span>{{ t('」以确认删除') }}
          </div>
          <bk-input
            v-model="deleteConfirmName"
            :placeholder="t('请输入待删除的场景名称')" />
        </div>
        <template #footer>
          <bk-button
            class="mr8"
            :disabled="deleteConfirmName !== currentDeleteScene?.name"
            theme="danger"
            @click="handleConfirmDelete">
            {{ t('删除') }}
          </bk-button>
          <bk-button @click="handleCancelDelete">
            {{ t('取消') }}
          </bk-button>
        </template>
      </bk-dialog>

      <!-- 停用确认弹窗 -->
      <bk-dialog
        v-model:is-show="disableDialogVisible"
        dialog-type="confirm"
        footer-align="center"
        header-align="center"
        :quick-close="false"
        :title="t('')">
        <div class="confirm-dialog-content">
          <div class="dialog-title-row">
            <img
              class="tip-icon"
              src="@images/tip-icon.svg">
            <div class="dialog-title-text">
              {{ t('确定停用该场景？') }}
            </div>
          </div>
          <div class="warning-message">
            {{ t('停用后，该场景下的所有资源将不可用，已产生的风险数据不受影响，请谨慎操作！') }}
          </div>
          <div class="confirm-input-label">
            {{ t('请输入场景名称「') }}<span
              v-bk-tooltips="t('点击复制')"
              class="scene-name copyable"
              @click="handleCopySceneName(currentDisableScene?.name)">{{
                currentDisableScene?.name
              }}</span>{{ t('」以确认停用') }}
          </div>
          <bk-input
            v-model="disableConfirmName"
            :placeholder="t('请输入场景名称')" />
        </div>
        <template #footer>
          <bk-button
            class="mr8"
            :disabled="disableConfirmName !== currentDisableScene?.name"
            theme="danger"
            @click="handleConfirmDisable">
            {{ t('停用') }}
          </bk-button>
          <bk-button @click="handleCancelDisable">
            {{ t('取消') }}
          </bk-button>
        </template>
      </bk-dialog>

      <!-- 新建/编辑场景侧边栏 -->
      <create-scene-sideslider
        v-model:is-show="createSceneVisible"
        :scene-id="editSceneId"
        @success="handleCreateSceneSuccess" />

      <!-- 场景详情侧边栏 -->
      <scene-detail-sideslider
        ref="sceneDetailRef"
        v-model:is-show="sceneDetailVisible"
        :scene-id="currentDetailSceneId"
        @delete="handleDeleteScene"
        @edit="handleDetailEdit"
        @toggle-status="handleToggleStatus" />
    </div>
  </skeleton-loading>
</template>

<script setup lang='tsx'>
  import {
    onMounted,
    reactive,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import SceneManageService from '@service/scene-manage';
  import MetaManageService from '@service/meta-manage';

  import SceneModel from '@model/scene/scene';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import Tooltips from '@components/show-tooltips-text/index.vue';
  import TdesignList from '@components/tdesign-list/index.vue';

  import CreateSceneSideslider from './components/create-scene-sideslider.vue';
  import SceneDetailSideslider from './components/scene-detail-sideslider.vue';

  interface SearchKey {
    id: string;
    name: string;
    values: Array<{ id: string; name: string }>;
  }

  const router = useRouter();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const { replaceSearchParams } = useUrlSearch();

  const isLoading = ref(false);
  // 状态筛选
  const statusFilter = ref('all');
  // bk-search-select 搜索值
  const searchValue = ref<SearchKey[]>([]);

  // bk-search-select 搜索条件配置
  const searchSelectData = ref([
    {
      name: '场景ID',
      id: 'scene_id',
      placeholder: '请输入场景ID',
    },
    {
      name: '场景名称',
      id: 'name',
      placeholder: '请输入场景名称',
    },
    {
      name: '场景描述',
      id: 'description',
      placeholder: '请输入场景描述',
    },
    {
      name: '场景管理员',
      id: 'manager',
      placeholder: '请选择场景管理员',
      children: [] as Array<{ id: string; name: string }>,
    },
    {
      name: '场景使用者',
      id: 'user',
      placeholder: '请选择场景使用者',
      children: [] as Array<{ id: string; name: string }>,
    },
    {
      name: '更新人',
      id: 'updated_by',
      placeholder: '请选择更新人',
      children: [] as Array<{ id: string; name: string }>,
    },
  ]);

  // 获取用户列表（用于远程搜索人员字段）
  const {
    run: fetchUserList,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: { page: 1, page_size: 30 },
    defaultValue: { count: 0, results: [] } as { count: number; results: any[] },
  });

  // 远程搜索菜单列表（管理员/使用者/更新人输入时实时搜索）
  const getMenuList = async (item: any, keyword: string) => {
    if (!item) return searchSelectData.value;
    const searchItem = searchSelectData.value.find(s => s.id === item?.id);
    if (searchItem && ['manager', 'user', 'updated_by'].includes(item.id)) {
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
  // 表格引用
  const listRef = ref<InstanceType<typeof TdesignList>>();

  // 删除弹窗相关
  const deleteDialogVisible = ref(false);
  const deleteConfirmName = ref('');
  const currentDeleteScene = ref<SceneModel | null>(null);

  // 停用弹窗相关
  const disableDialogVisible = ref(false);
  const disableConfirmName = ref('');
  const currentDisableScene = ref<SceneModel | null>(null);

  // 新建/编辑场景侧边栏
  const createSceneVisible = ref(false);
  const editSceneId = ref<string | number | undefined>(undefined);
  // 新增的场景ID集合（用于高亮显示绿色底）
  const newSceneIds = ref<Set<string | number>>(new Set());

  // 场景详情侧边栏
  const sceneDetailVisible = ref(false);
  const currentDetailSceneId = ref<string | number>('');
  const sceneDetailRef = ref<InstanceType<typeof SceneDetailSideslider>>();

  // 状态统计
  const statusCounts = reactive({
    all: 0,
    enabled: 0,
    disabled: 0,
  });

  // 获取删除按钮的 tooltips 配置
  const getDeleteTooltips = (row: SceneModel) => {
    if (row.status === 'enabled') {
      return { content: t('请先停用后再删除'), disabled: false };
    }
    if (row.status === 'disabled' && row.strategy_ids.length > 0) {
      return { content: t('该场景已被策略引用，无法删除'), disabled: false };
    }
    return { disabled: true };
  };

  // 判断删除按钮是否禁用
  const isDeleteDisabled = (row: SceneModel) => row.status === 'enabled'
    || (row.status === 'disabled' && row.strategy_ids.length > 0);

  // 表格列配置
  const tableColumns = [
    {
      title: t('场景ID'),
      colKey: 'scene_id',
      width: 180,
      ellipsis: true,
    },
    {
      title: () => (
      <span class="column-title-required">
        {t('场景名称')}
      </span>
    ),
      colKey: 'name',
      minWidth: 180,
      ellipsis: true,
      cell: (_: any, { row }: { row: SceneModel }) => (
      <span
        class="scene-name-cell"
        style="color: #3A84FF;">
        <span
          class="scene-name-link"
          onClick={() => handleShowSceneDetail(row)}>
          {row.name}
        </span>
        <audit-icon
          v-bk-tooltips={t('跳转至「场景信息」查看')}
          class="ml8 jump-link hover-show-icon"
          type="jump-link"
          onClick={(e: Event) => {
            e.stopPropagation();
            handleJumpToSceneInfo(row);
          }} />
      </span>
    ),
    },
    {
      title: t('场景描述'),
      colKey: 'description',
      minWidth: 120,
      ellipsis: true,
      cell: (_: any, { row }: { row: SceneModel }) => (
      <Tooltips data={row.description || '--'} />
    ),
    },
    {
      title: t('数据来源'),
      colKey: 'data_source',
      minWidth: 150,
      ellipsis: true,
      cell: (_: any, { row }: { row: SceneModel }) => (
      <Tooltips data={dataSourceRender(row) || '--'} />
    ),
    },
    {
      title: t('场景管理员'),
      colKey: 'managers',
      minWidth: 360,
      cell: (_: any, { row }: { row: SceneModel }) => (
        row.managers.length > 0
          ? <div class="tag-list">
              {row.managers.slice(0, 2).map((manager: string) => <bk-tag class="mr8" key={manager}>{manager}</bk-tag>)}
              {row.managers.length > 2 && (
                <bk-popover placement="top" theme="light">
                  {{
                    default: () => <bk-tag>+{row.managers.length - 2}</bk-tag>,
                    content: () => <div class="tag-popover-content">{row.managers.join('、')}</div>,
                  }}
                </bk-popover>
              )}
            </div>
          : '--'
      ),
    },
    {
      title: t('场景使用者'),
      colKey: 'users',
      minWidth: 140,
      cell: (_: any, { row }: { row: SceneModel }) => (
        row.users.length > 0
          ? <div class="tag-list">
              {row.users.slice(0, 2).map((user: string) => <bk-tag class="mr8" key={user}>{user}</bk-tag>)}
              {row.users.length > 2 && (
                <bk-popover placement="top" theme="light">
                  {{
                    default: () => <bk-tag>+{row.users.length - 2}</bk-tag>,
                    content: () => <div class="tag-popover-content">{row.users.join('、')}</div>,
                  }}
                </bk-popover>
              )}
            </div>
          : '--'
      ),
    },
    {
      title: t('策略数'),
      colKey: 'strategy_count',
      width: 100,
      sortType: 'all',
      sorter: true,
      align: 'right',
      cell: (_: any, { row }: { row: SceneModel }) => (
      <span class="strategy-count-cell">
        {row.strategy_ids.length}
        <audit-icon
          v-bk-tooltips={t('跳转至「审计策略」查看')}
          class="ml8 jump-link hover-show-icon"
          type="jump-link"
          onClick={(e: Event) => {
            e.stopPropagation();
            handleJumpToStrategy(row);
          }} />
      </span>
    ),
    },
    {
      title: t('风险数'),
      colKey: 'risk_count',
      width: 100,
      sortType: 'all',
      sorter: true,
      align: 'right',
      cell: (_: any, { row }: { row: SceneModel }) => (
      <span class="risk-count-cell">
        {row.risk_count}
        <audit-icon
          v-bk-tooltips={t('跳转至「风险」查看')}
          class="ml8 jump-link hover-show-icon"
          type="jump-link"
          onClick={(e: Event) => {
            e.stopPropagation();
            handleJumpToRisk(row);
          }} />
      </span>
    ),
    },
    {
      title: t('状态'),
      colKey: 'status',
      width: 100,
      cell: (_: any, { row }: { row: SceneModel }) => (
      <bk-tag theme={row.status === 'enabled' ? 'success' : ''}>
        {row.status === 'enabled' ? t('启用') : t('停用')}
      </bk-tag>
    ),
    },
    {
      title: t('更新人'),
      colKey: 'updated_by',
      width: 120,
      cell: (_: any, { row }: { row: SceneModel }) => (
      <span>{row.updated_by || '--'}</span>
    ),
    },
    {
      title: t('更新时间'),
      colKey: 'updated_at',
      width: 180,
      sortType: 'all',
      sorter: true,
      cell: (_: any, { row }: { row: SceneModel }) => (
      <span>{row.updated_at || '--'}</span>
    ),
    },
    {
      title: () => (
      <span class="column-title-required">
        {t('操作')}
      </span>
    ),
      colKey: 'action',
      width: 150,
      fixed: 'right',
      cell: (_: any, { row }: { row: SceneModel }) => (
      <div class="action-btns">
        <bk-button
          text
          theme="primary"
          onClick={() => handleEditScene(row)}>
          {t('编辑')}
        </bk-button>
        <bk-button
          class="ml8"
          text
          theme="primary"
          onClick={() => handleToggleStatus(row)}>
          {row.status === 'enabled' ? t('停用') : t('启用')}
        </bk-button>
        <bk-popover
          placement="bottom"
          theme="light"
          arrow={false}
          offset={0}>
          {{
            default: () => (
              <audit-icon
                class="ml8 more-action-icon"
                type="more" />
            ),
            content: () => (
              <div class="more-action-menu">
                <div
                  v-bk-tooltips={getDeleteTooltips(row)}
                  class={['more-action-item', isDeleteDisabled(row) ? 'is-disabled' : '']}
                  onClick={() => !isDeleteDisabled(row) && handleDeleteScene(row)}>
                  {t('删除')}
                </div>
              </div>
            ),
          }}
        </bk-popover>
      </div>
    ),
    },
  ];
  // 模拟数据源 - 实际应替换为真实API
  const dataSource = (params: any) => SceneManageService.fetchSceneList({
    ...params,
    sort: params?.sort || ['-scene_id'],
  });

  const dataSourceRender = (row: SceneModel) => `${row.system_count} ${t('个系统')}，${row.table_count} ${t('个数据表')}` || '--';

  // 获取全局状态统计（不受筛选条件影响）
  const fetchStatusCounts = () => {
    SceneManageService.fetchSceneAll().then((allScenes) => {
      statusCounts.all = allScenes.length;
      statusCounts.enabled = allScenes.filter((item: { status: string }) => item.status === 'enabled').length;
      statusCounts.disabled = allScenes.filter((item: { status: string }) => item.status === 'disabled').length;
    });
  };

  // 处理请求成功
  const handleRequestSuccess = () => {
    isLoading.value = false;
    // 每次列表请求成功后，单独获取全局状态统计
    fetchStatusCounts();
  };

  // 搜索 - 仿造 strategy-manage/list/index.vue
  const handleSearch = (keyword: SearchKey[]) => {
    const search = {
      scene_id: undefined,
      name: '',
      description: '',
      manager: '',
      user: '',
      updated_by: '',
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
    } as Record<string, any>;

    keyword.forEach((item) => {
      if (item.values && item.values.length) {
        const value = item.values.map(v => v.id).join(',');
        if (item.id === 'scene_id') {
          search.scene_id = value;
        } else if (item.id === 'name') {
          search.name = value;
        } else if (item.id === 'description') {
          search.description = value;
        } else if (item.id === 'manager') {
          search.manager = value;
        } else if (item.id === 'user') {
          search.user = value;
        } else if (item.id === 'updated_by') {
          search.updated_by = value;
        }
      }
    });

    listRef.value?.fetchData(search);
  };

  // 状态筛选变化
  const handleStatusFilterChange = () => {
    handleSearch(searchValue.value);
  };

  // 清空搜索条件，重新请求初始化数据
  const handleClearSearch = () => {
    searchValue.value = [];
    statusFilter.value = 'all';
    // 清除 URL 中的所有搜索参数，只保留基础分页参数
    replaceSearchParams({
      page: 1,
      page_size: 10,
    });
    listRef.value?.fetchData({});
  };

  // 新建场景
  const handleCreateScene = () => {
    editSceneId.value = undefined;
    createSceneVisible.value = true;
  };

  // 新建场景成功
  const handleCreateSceneSuccess = (newSceneId?: string | number) => {
    // 如果返回了新场景ID，记录下来用于高亮显示
    if (newSceneId !== undefined && newSceneId !== null) {
      // 统一转为字符串存储，避免类型不匹配
      newSceneIds.value.add(String(newSceneId));
    }
    listRef.value?.fetchData({});
  };

  // 获取场景行的类名（新增的场景显示绿色底）
  const getSceneRowClassName = (row: any): string => {
    // 兼容 TDesign 传入 { row } 或直接 row 的情况
    const rowData = row?.row || row;
    if (rowData && newSceneIds.value.has(String(rowData.scene_id))) {
      return 'new-row';
    }
    return '';
  };

  // 显示场景详情
  const handleShowSceneDetail = (row: SceneModel) => {
    currentDetailSceneId.value = row.scene_id;
    sceneDetailVisible.value = true;
  };

  const handleJumpToSceneInfo = (row: SceneModel) => {
    const routeData = router.resolve({
      name: 'sceneInfo',
      query: {
        scene_id: String(row.scene_id),
      },
    });
    window.open(routeData.href, '_blank');
  };

  // 新开标签页跳转到审计策略列表页
  const handleJumpToStrategy = (row: SceneModel) => {
    const strategyIds = row.strategy_ids || [];
    const query: Record<string, string> = {
      scene_id: String(row.scene_id),
    };
    if (strategyIds.length) {
      query.strategy_id = strategyIds.join(',');
    }
    const routeData = router.resolve({
      name: 'strategyList',
      query,
    });
    window.open(routeData.href, '_blank');
  };

  // 新开标签页跳转到场景风险列表页
  const handleJumpToRisk = (row: SceneModel) => {
    const routeData = router.resolve({
      name: 'sceneRiskManageList',
      query: { scene_id: String(row.scene_id) },
    });
    window.open(routeData.href, '_blank');
  };

  // 编辑场景
  const handleEditScene = (row: SceneModel) => {
    editSceneId.value = row.scene_id;
    createSceneVisible.value = true;
  };

  // 从详情侧边栏触发编辑
  const handleDetailEdit = (row: SceneModel) => {
    sceneDetailVisible.value = false;
    handleEditScene(row);
  };

  // 切换状态
  const handleToggleStatus = (row: SceneModel) => {
    if (row.status === 'enabled') {
      // 停用需要二次确认
      currentDisableScene.value = row;
      disableConfirmName.value = '';
      disableDialogVisible.value = true;
    } else {
      // 启用直接执行
      SceneManageService.enableScene(row.scene_id).then(() => {
        messageSuccess(t('启用成功'));
        listRef.value?.fetchData({});
        sceneDetailRef.value?.refresh();
      });
    }
  };

  // 确认停用
  const handleConfirmDisable = () => {
    if (!currentDisableScene.value) return;
    if (disableConfirmName.value !== currentDisableScene.value.name) {
      return;
    }
    SceneManageService.disableScene(currentDisableScene.value.scene_id).then(() => {
      messageSuccess(t('停用成功'));
      disableDialogVisible.value = false;
      disableConfirmName.value = '';
      currentDisableScene.value = null;
      listRef.value?.fetchData({});
      sceneDetailRef.value?.refresh();
    });
  };

  // 取消停用
  const handleCancelDisable = () => {
    disableDialogVisible.value = false;
    disableConfirmName.value = '';
    currentDisableScene.value = null;
  };

  // 删除场景
  const handleDeleteScene = (row: SceneModel) => {
    currentDeleteScene.value = row;
    deleteConfirmName.value = '';
    deleteDialogVisible.value = true;
  };

  // 确认删除
  const handleConfirmDelete = () => {
    if (!currentDeleteScene.value) return;
    if (deleteConfirmName.value !== currentDeleteScene.value.name) {
      return;
    }
    SceneManageService.deleteScene(currentDeleteScene.value.scene_id).then(() => {
      messageSuccess(t('删除成功'));
      deleteDialogVisible.value = false;
      deleteConfirmName.value = '';
      currentDeleteScene.value = null;
      listRef.value?.fetchData({});
    });
  };

  // 取消删除
  const handleCancelDelete = () => {
    deleteDialogVisible.value = false;
    deleteConfirmName.value = '';
    currentDeleteScene.value = null;
  };

  // 复制场景名称到剪贴板
  const handleCopySceneName = (name: string | undefined) => {
    if (!name) return;
    navigator.clipboard.writeText(name).then(() => {
      messageSuccess(t('复制成功'));
    });
  };

  onMounted(() => {
    listRef.value?.fetchData({});
  });
</script>

<style lang="postcss" scoped>
.scene-manage-page {
  min-height: 85vh;
  padding: 24px;
  background-color: #fff;
  border-radius: 2px;
  box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);
}

.scene-manage-header {
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

.ml4 {
  margin-left: 4px;
}

.ml8 {
  margin-left: 8px;
}

.status-filter {
  :deep(.bk-radio-button) {
    .bk-radio-button-label {
      display: flex;
      align-items: center;
      padding: 0 12px;
    }
  }

  :deep(.bk-radio-button:not(.is-checked)) {
    .status-count {
      color: #979ba5;
      background-color: #fff !important;
      border-color: #fff !important;
    }
  }
}

.status-count {
  height: 18px;
  min-width: 18px;
  padding: 0 4px;
  margin-left: 4px;
  font-size: 12px;
  line-height: 18px;
  pointer-events: none;
}

.search-input {
  width: 600px;
}

.scene-manage-content {
  min-height: 400px;

  :deep(.audit-tdesign-list) {
    border: none;
  }
}

.scene-id-cell {
  color: #63656e;
}

.column-title-required::before {
  margin-right: 4px;
  color: #ea3636;
  content: '*';
}

.action-btns {
  display: flex;
  align-items: center;
}

:deep(.jump-link) {
  color: #3a84ff;
  cursor: pointer;
}

:deep(.scene-name-link) {
  cursor: pointer;
}

/* 默认隐藏 hover-show-icon */
:deep(.hover-show-icon) {
  visibility: hidden;
}

/* 鼠标移入表格行时显示图标 */
:deep(tr:hover) {
  .hover-show-icon {
    visibility: visible;
  }
}

/* 更多操作图标 */
.more-action-icon {
  font-size: 18px;
  color: #979ba5;
  cursor: pointer;

  &:hover {
    color: #3a84ff;
  }
}

/* 确认弹窗内容 */
.confirm-dialog-content {
  padding: 0 24px;

  .dialog-title-row {
    display: flex;
    align-items: center;
  }

  .tip-icon {
    position: absolute;
    top: 15px;
    left: 50%;
    width: 50px;
    height: 50px;
    margin-bottom: 16px;
    transform: translateX(-50%)
  }

  .dialog-title-text {
    width: 100%;
    margin-top: 65px;
    margin-bottom: 16px;
    font-size: 20px;
    font-weight: 400;
    color: #313238;
    text-align: center;
  }

  .warning-message {
    padding: 12px 16px;
    margin-bottom: 16px;
    line-height: 22px;
    background-color: #f5f7fa;
    border-radius: 2px;

    .warning-text {
      color: #e71818;
    }
  }

  .disable-warning {
    color: #63656e;
  }

  .confirm-input-label {
    margin-bottom: 8px;
    font-size: 14px;
    color: #63656e;

    .scene-name {
      font-weight: 600;
      color: #313238;
      cursor: pointer;
    }
  }
}
</style>

<style lang="postcss">
/* 更多操作菜单（popover 渲染到 body 下，需要全局样式） */
.more-action-menu {
  .more-action-item {
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    transition: background-color .2s;

    &:hover {
      color: #3a84ff;
      background-color: #f5f7fa;
    }

    &.is-disabled {
      color: #c4c6cc;
      cursor: not-allowed;

      &:hover {
        color: #c4c6cc;
        background-color: transparent;
      }
    }
  }
}

.tag-list {
  display: inline-flex;
  flex-wrap: nowrap;
  gap: 4px;
  align-items: center;
  overflow: hidden;

  .bk-tag {
    flex-shrink: 0;
  }
}

.tag-popover-content {
  max-width: 300px;
  font-size: 12px;
  line-height: 20px;
  word-break: break-all;
}
</style>
