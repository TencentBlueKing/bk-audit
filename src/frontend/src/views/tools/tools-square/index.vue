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
  <div
    class="tools-square"
    :class="{ 'is-animating': isSidebarAnimating }">
    <div
      v-show="!hasOpenedTools"
      class="square-page">
      <div class="page-title-row">
        <h1 class="page-title">
          {{ t('工具广场') }}
        </h1>
        <scene-system-selector
          v-model="selectedScene"
          class="page-scene-selector"
          :list-scope="['scene','system']"
          :popover-width="208"
          scene-permission="view_scene"
          system-permission="view_system"
          width="208px"
          @change="handleSceneChange" />
      </div>
      <div class="page-toolbar">
        <div
          class="capsule-tabs"
          role="tablist">
          <button
            v-for="tab in capsuleTabs"
            :key="tab.tag_id"
            :aria-selected="isCapsuleActive(tab.tag_id)"
            class="capsule-tab"
            :class="{ 'is-active': isCapsuleActive(tab.tag_id) }"
            role="tab"
            type="button"
            @click="handleChecked(tab.tag_id)">
            <span>{{ t(tab.tag_name) }}</span>
            <span
              v-if="tab.countReady"
              class="capsule-count">{{ tab.tool_count }}</span>
            <span
              v-else
              class="capsule-count is-skeleton"
              aria-hidden="true" />
          </button>
        </div>
        <bk-select
          class="tag-filter"
          :clearable="true"
          :filterable="true"
          :model-value="labelFilterValue"
          :placeholder="t('标签：选择标签进行筛选')"
          @clear="handleLabelFilterClear"
          @update:model-value="handleLabelFilterChange">
          <bk-option
            v-for="item in labelFilterOptions"
            :id="item.tag_id"
            :key="item.tag_id"
            :name="item.tag_name" />
        </bk-select>
        <div
          id="tools-square-search-anchor"
          class="search-anchor" />
      </div>
      <bk-alert
        v-if="activeToolsInScene.length > 0"
        class="using-alert"
        :show-icon="true"
        theme="warning">
        <template #title>
          <span class="using-alert-title">
            <span>{{ t('你有') }} {{ activeToolsInScene.length }} {{ t('个工具正在使用中') }}</span>
            <button
              class="using-alert-link"
              type="button"
              @click="handleContinueUsingTool">
              {{ t('继续操作') }}
            </button>
          </span>
        </template>
      </bk-alert>
      <div class="square-list">
        <content-card
          ref="ContentCardRef"
          :accessible-scene-ids="accessibleSceneIds"
          :is-cross-scene="scopeParams.scope_type === 'cross_scene'"
          :is-cross-system="scopeParams.scope_type === 'cross_system'"
          :my-created="tagId === '-4'"
          :recent-used="tagId === '-5'"
          :scene-name-map="sceneNameMap"
          :scope-params="scopeParams"
          :single-scope-group="singleScopeGroup"
          :system-name-map="systemNameMap"
          :tag-id="tagId"
          :tags-enums="tagsEnums"
          @change="handleChange"
          @open-tool="handleOpenTool" />
      </div>
    </div>
    <div
      v-show="hasOpenedTools"
      class="content-content has-shadow">
      <div class="content-card">
        <tool-info-panel
            ref="toolInfoPanelRef"
            :accessible-scene-ids="accessibleSceneIds"
            :active-uid="activeToolUid"
            :scene-name-map="sceneNameMap"
            :scope-params="scopeParams"
            :system-name-map="systemNameMap"
            :tags-enums="tagsEnums"
            :tool-list="openedTools"
            @add-tool="handleAddToolFromPopover"
            @close="handleCloseToolPanel"
            @close-tab="handleCloseTab"
            @go-home="handleGoHomePage"
            @switch-tab="handleSwitchTab" />
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { computed, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import SceneManageService from '@service/scene-manage';
  import ToolManageService from '@service/tool-manage';

  import ToolInfo from '@model/tool/tool-info';

  import SceneSystemSelector from '@components/scene-system-selector/index.vue';

  import ContentCard from './square-content/concent-card.vue';
  import ToolInfoPanel from './square-content/tool-info-panel.vue';

  import useEventBus from '@/hooks/use-event-bus';
  import useRequest from '@/hooks/use-request';
  import type { DrillDownParams } from '@/hooks/use-tool-tabs';
  import useToolTabs from '@/hooks/use-tool-tabs';
  import type { ToolDetailOverrideContext } from '@/utils/assist/scene-system-params';
  import {
    buildGameDetailTabLabel,
    getRouteQueryValue,
    getRouteScopeQuery,
  } from '@/views/tools/tools-square/utils/tool-url-params';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    strategy_count: number;
    icon: string;
  }

  interface SceneItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
  }

  const ContentCardRef = ref<InstanceType<typeof ContentCard>>();
  const toolInfoPanelRef = ref<InstanceType<typeof ToolInfoPanel>>();

  // 场景ID → 场景名称映射
  const sceneNameMap = ref<Record<number, string>>({});
  const accessibleSceneIds = ref<number[] | null>(null);
  const {
    run: fetchSceneAll,
  } = useRequest(SceneManageService.fetchSceneAll, {
    defaultValue: [],
    onSuccess: (data: Array<{
      scene_id: number;
      name: string;
      status: 'enabled' | 'disabled';
      permission: Record<string, boolean>;
    }>) => {
      const map: Record<number, string> = {};
      data.forEach((item) => {
        map[item.scene_id] = item.name;
      });
      sceneNameMap.value = map;
      accessibleSceneIds.value = data
        .filter(item => item.status === 'enabled' && item.permission?.view_scene === true)
        .map(item => item.scene_id);
    },
  });
  // 系统ID → 系统名称映射
  const systemNameMap = ref<Record<string, string>>({});
  const {
    run: fetchSystemList,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    onSuccess: (data: any[]) => {
      const map: Record<string, string> = {};
      (data || []).forEach((item) => {
        map[String(item.system_id)] = item.name;
        if (item.id !== undefined && item.id !== null) {
          map[String(item.id)] = item.name;
        }
      });
      systemNameMap.value = map;
    },
  });
  // 初始化获取场景/系统列表
  fetchSceneAll();
  fetchSystemList({ audit_status__in: 'accessed', namespace: 'default' });
  const tagsEnums = ref<Array<TagItem>>([]);
  const tagId = ref(sessionStorage.getItem('tools_square_selected_tag') || '');
  // 监听 tagId 变化，保存到 sessionStorage（用于记忆选中的tab）
  watch(tagId, (newVal) => {
    if (newVal) {
      sessionStorage.setItem('tools_square_selected_tag', newVal);
    } else {
      sessionStorage.removeItem('tools_square_selected_tag');
    }
  });
  const strategyLabelList = ref<Array<TagItem>>([]);
  const capsuleTagIds = ['-3', '-5', '-6', '-4'];
  const capsuleTabFallbacks = [
    { tag_id: '-3', tag_name: '全部工具' },
    { tag_id: '-5', tag_name: '最近使用' },
    { tag_id: '-6', tag_name: '我的收藏' },
    { tag_id: '-4', tag_name: '我创建的' },
  ];
  const capsuleTabs = computed(() => capsuleTabFallbacks.map((fallback) => {
    const loaded = strategyLabelList.value.find(item => item.tag_id === fallback.tag_id);
    if (loaded) {
      return {
        tag_id: loaded.tag_id,
        tag_name: loaded.tag_name,
        tool_count: loaded.tool_count,
        countReady: true,
      };
    }
    return {
      tag_id: fallback.tag_id,
      tag_name: fallback.tag_name,
      tool_count: 0,
      countReady: false,
    };
  }));
  const isCapsuleActive = (id: string) => tagId.value === id || (!tagId.value && id === '-3');
  const labelFilterOptions = computed(() => strategyLabelList.value
    .filter(item => !capsuleTagIds.includes(item.tag_id)));
  const labelFilterValue = computed(() => (
    labelFilterOptions.value.some(item => item.tag_id === tagId.value) ? tagId.value : ''
  ));
  const isSidebarCollapsed = ref(false);
  const isSidebarAnimating = ref(false);
  let sidebarAnimateTimer: ReturnType<typeof setTimeout> | null = null;
  const isReturningHome = ref(false);
  // 从详情回到广场：跳过侧栏展开触发的列表重载，并在动画结束后还原滚动
  const isRestoringListScroll = ref(false);
  let restoreListScrollTimer: ReturnType<typeof setTimeout> | null = null;

  const restoreListScrollAfterReturn = () => {
    if (restoreListScrollTimer) clearTimeout(restoreListScrollTimer);
    const tryRestore = () => {
      ContentCardRef.value?.restoreScrollPosition?.();
    };
    nextTick(() => {
      tryRestore();
      requestAnimationFrame(tryRestore);
    });
    // 侧栏展开动画约 320ms，结束后再还原一次，避免布局变化把滚动冲掉
    restoreListScrollTimer = setTimeout(() => {
      tryRestore();
      isRestoringListScroll.value = false;
      restoreListScrollTimer = null;
    }, 360);
  };
  const isInitialSceneSetup = ref(false);
  const route = useRoute();
  const router = useRouter();
  const { t } = useI18n();

  // 场景选择器
  const selectedScene = ref<SceneItem | null>();
  // 记录上一次场景的唯一标识，用于区分"初始化选中"和"用户主动切换场景"
  const lastSceneKey = ref<string | null>(null);

  // 将选择器值转换为 scope 参数
  const scopeParams = computed(() => {
    const item = selectedScene.value;
    // 未选择场景时，默认使用跨场景类型（scope_type 为后端必填字段）
    if (!item) return { scope_type: 'cross_scene' };
    if (item.type === 'aggregate') {
      return {
        scope_type: item.id === 'allSecen' ? 'cross_scene' : 'cross_system',
      };
    }
    return {
      scope_type: item.type, // 'scene' | 'system'
      scope_id: item.id,
    };
  });

  const singleScopeGroup = computed(() => {
    const item = selectedScene.value;
    if (!item || item.type === 'aggregate') return null;
    return {
      groupKey: String(item.id),
      groupName: item.name,
      groupId: item.id,
    };
  });

  const {
    openedTools,
    activeToolUid,
    hasOpenedTools,
    openTool,
    closeTab,
    switchTab,
    goHome,
    clearAll,
    setDrillDownParams,
    resetForDrillDown,
    saveSceneState,
    restoreSceneState,
  } = useToolTabs();

  // 当前场景下所有工具的 uid 集合
  const sceneToolUids = ref<Set<string>>(new Set());

  // 获取当前场景下的全量工具 uid
  const {
    run: fetchSceneAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    onSuccess: (data: any[]) => {
      sceneToolUids.value = new Set(data.map(item => item.uid));
    },
  });

  // 监听场景切换，刷新当前场景下的全量工具 uid
  watch(() => scopeParams.value, () => {
    fetchSceneAllTools({ ...scopeParams.value, status: 'published' });
  }, { immediate: true, deep: true });

  // 当前场景下正在使用的工具（openedTools 与场景全量工具的交集）
  const activeToolsInScene = computed(() => openedTools.value.filter(tool => sceneToolUids.value.has(tool.uid)));

  // 点击继续使用工具
  const handleContinueUsingTool = () => {
    ContentCardRef.value?.saveScrollPosition();
    const lastTool = openedTools.value[openedTools.value.length - 1];
    if (lastTool) {
      switchTab(lastTool.uid);
      isSidebarCollapsed.value = true;
      syncToolRouteToUrl(lastTool.uid);
    }
  };

  const routeUid = route.params.uid as string;
  const isDrillDownRoute = !!(routeUid && (route.query.drillKey || route.query.drillConfig));
  const isRefreshRestore = !!(routeUid && !route.query.drillKey && !route.query.drillConfig);
  const isProgrammaticReset = ref(false);

  const getFirstQueryValue = getRouteQueryValue;

  const getGameDetailTabName = () => {
    const query = route.query as Record<string, unknown>;
    return buildGameDetailTabLabel({
      ctx: getFirstQueryValue(query.wecom) || getFirstQueryValue(query.ctx),
      gameid: getFirstQueryValue(query.game_id),
      name: '',
    }, { resolving: true });
  };

  // 打开广场地址时停在列表。已打开的工具不自动进入工作台，留在「正在使用」提示里。

  // 场景切换
  const getSceneKey = (item: SceneItem | null) => (item ? `${item.type}:${item.id}` : '');
  const handleSceneChange = async (value: SceneItem | null) => {
    const newKey = getSceneKey(value);
    const isFirstSceneSetup = lastSceneKey.value === null;
    const isActualChange = lastSceneKey.value !== null && lastSceneKey.value !== newKey;

    if (isActualChange) {
      // 用户主动切换场景 → 保存当前场景的工具状态，再恢复目标场景的工具状态
      saveSceneState(lastSceneKey.value!);
      try {
        sessionStorage.removeItem('tool_tabs_search_list_map');
      } catch {
        // 静默处理
      }
    }

    selectedScene.value = value;
    lastSceneKey.value = newKey;
    isInitialSceneSetup.value = isFirstSceneSetup;

    if (isActualChange) {
      restoreSceneState(newKey);
      isSidebarCollapsed.value = hasOpenedTools.value;
      if (activeToolUid.value) {
        syncToolRouteToUrl(activeToolUid.value);
      } else {
        syncRouteToUrl();
      }
    }
    // 无论是初始化还是切换，都重新拉取标签和工具列表
    // 切换场景时，重置选中的标签为"全部工具"，并清空列表搜索条件
    if (isActualChange) {
      tagId.value = '-3';
      ContentCardRef.value?.clearSearch();
    }
    refreshTagsList();
    ContentCardRef.value?.getToolsList(tagId.value);
  };

  if (isDrillDownRoute) {
    resetForDrillDown();
    const drillUid = routeUid;
    let drillConfig = null;
    let rowData = null;
    try {
      const drillKey = route.query.drillKey as string;
      if (drillKey) {
        const storedRaw = sessionStorage.getItem(drillKey);
        if (storedRaw) {
          const storedData = JSON.parse(storedRaw);
          drillConfig = storedData.drillConfig;
          rowData = storedData.rowData;
          sessionStorage.removeItem(drillKey);
        }
      } else {
        // 兼容旧的 URL 参数方式
        const drillConfigRaw = route.query.drillConfig as string;
        const rowDataRaw = route.query.rowData as string;
        if (drillConfigRaw) drillConfig = JSON.parse(decodeURIComponent(drillConfigRaw));
        if (rowDataRaw) rowData = JSON.parse(decodeURIComponent(rowDataRaw));
      }
    } catch {
      // 解析失败时忽略
    }
    if (drillConfig && rowData) {
      const drillParams: DrillDownParams = {
        drillConfig,
        rowData,
      };
      setDrillDownParams(drillUid, drillParams);
    }
    const tempTool = new ToolInfo({
      uid: drillUid,
      name: drillUid,
    } as ToolInfo);
    openTool(tempTool);
  } else if (isRefreshRestore) {
    const alreadyInList = openedTools.value.some(t => t.uid === routeUid);
    if (!alreadyInList) {
      const tempTool = new ToolInfo({
        uid: routeUid,
        name: routeUid.startsWith('game_detail_') ? getGameDetailTabName() : routeUid,
      } as ToolInfo);
      openTool(tempTool);
    } else if (activeToolUid.value !== routeUid) {
      switchTab(routeUid);
    }
  }

  // 安全地重置左侧标签栏（防止 resetAll 触发的 checked 事件关闭工具详情）
  const safeResetLabels = () => {
    if (hasOpenedTools.value) {
      isProgrammaticReset.value = true;
    }
    if (!tagId.value || tagId.value === '-3') {
      handleChecked('-3');
    }
    nextTick(() => {
      isProgrammaticReset.value = false;
    });
  };

  const handleLabelFilterChange = (value: string | number | null) => {
    const next = value === undefined || value === null || value === '' ? '' : String(value);
    if (next === labelFilterValue.value) return;
    handleChecked(next || '-3');
  };

  const handleLabelFilterClear = () => {
    if (!capsuleTagIds.includes(tagId.value)) {
      handleChecked('-3');
    }
  };

  const handleChecked = async (name: string) => {
    tagId.value = name;
    if (isProgrammaticReset.value) {
      ContentCardRef.value?.getToolsList(name);
      return;
    }
    if (hasOpenedTools.value) {
      goHome();
      syncRouteToUrl();
      await nextTick();
    }
    ContentCardRef.value?.getToolsList(name);
  };

  const handleChange = () => {
    refreshTagsList();
  };

  // 固定分类数量（全部工具、我创建的、最近使用、我的收藏、无标签）
  const FIXED_TAG_COUNT = 5;

  const {
    run: fetchToolsTagsList,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    onSuccess: (data) => {
      const fixedTagOrder = ['-3', '-5', '-6', '-4', '-2'];
      const iconMap: Record<string, string> = {
        '-3': 'quanbu-xuanzhong',
        '-4': 'morentouxiang',
        '-5': 'shijian',
        '-6': 'wodeguanzhu',
        '-2': 'weifenpei',
      };
      // 前5项为固定分类，按目标顺序重排；后续为动态标签
      const fixedTags = data
        .slice(0, FIXED_TAG_COUNT)
        .sort((a, b) => fixedTagOrder.indexOf(a.tag_id) - fixedTagOrder.indexOf(b.tag_id));
      const dynamicTags = data.slice(FIXED_TAG_COUNT);
      const toLabelItem = (
        item: { tag_id: string; tag_name: string; tool_count: number },
        icon: string,
      ): TagItem => ({
        tag_id: String(item.tag_id),
        tag_name: item.tag_name,
        tool_count: item.tool_count ?? 0,
        strategy_count: item.tool_count ?? 0,
        icon,
      });
      strategyLabelList.value = [
        ...fixedTags.map(item => toLabelItem(item, iconMap[item.tag_id] || 'tag')),
        ...dynamicTags.map(item => toLabelItem(item, 'tag')),
      ];
      tagsEnums.value = strategyLabelList.value;
      // 工具已打开时，仅更新标签数据，不重置标签选中状态（侧边栏已收起，避免触发 goHome）
      if (hasOpenedTools.value) return;
      // 初始化阶段才按当前标签拉列表；从详情返回时只更新数量，避免滚动回到顶部
      if (isInitialSceneSetup.value || lastSceneKey.value === null || !tagId.value) {
        if ((isInitialSceneSetup.value || lastSceneKey.value === null) && tagId.value) {
          ContentCardRef.value?.getToolsList(tagId.value);
        } else {
          safeResetLabels();
        }
        isInitialSceneSetup.value = false;
      }
    },
  });

  // 刷新标签列表（带 scope 参数）
  const refreshTagsList = () => {
    fetchToolsTagsList({ ...scopeParams.value, status: 'published' });
  };

  /** 当前是否在工具广场相关路由（keep-alive 失活时 route 已是其他页） */
  const isToolsRouteActive = () => route.name === 'toolsSquare' || route.name === 'toolDetail';

  const syncToolRouteToUrl = (uid: string) => {
    // 失活实例仍可能因全局 scene query 变更触发场景同步，禁止抢导航
    if (!isToolsRouteActive()) return;
    nextTick(() => {
      toolInfoPanelRef.value?.syncRouteForTool(uid);
    });
  };

  function syncRouteToUrl(uid?: string, options?: { scopeOnly?: boolean }) {
    // 仅在工具广场/详情页同步路由；否则会把 AI 助手等页面强行 replace 回工具广场
    if (!isToolsRouteActive()) return;
    const scopeQuery = getRouteScopeQuery(route.query as Record<string, unknown>);
    if (uid) {
      if (uid.startsWith('game_detail_')) {
        syncToolRouteToUrl(uid);
        return;
      }
      if (options?.scopeOnly) {
        router.replace({ name: 'toolDetail', params: { uid }, query: scopeQuery });
        return;
      }
      syncToolRouteToUrl(uid);
      return;
    }
    if (route.name !== 'toolsSquare') {
      router.replace({ name: 'toolsSquare', query: scopeQuery });
    }
  }

  const handleOpenTool = (tool: ToolInfo, overrideContext?: ToolDetailOverrideContext) => {
    ContentCardRef.value?.saveScrollPosition();
    openTool(tool, { overrideContext });
    isSidebarCollapsed.value = true;
    syncRouteToUrl(tool.uid, { scopeOnly: true });
    refreshTagsList();
  };

  const handleAddToolFromPopover = (tool: ToolInfo, overrideContext?: ToolDetailOverrideContext) => {
    ContentCardRef.value?.saveScrollPosition();
    openTool(tool, { overrideContext });
    isSidebarCollapsed.value = true;
    syncRouteToUrl(tool.uid, { scopeOnly: true });
    refreshTagsList();
  };

  const handleGoHomePage = async () => {
    isReturningHome.value = true;
    isRestoringListScroll.value = true;
    ContentCardRef.value?.saveScrollPosition();
    goHome();
    syncRouteToUrl();
    await nextTick();
    if (tagId.value === '-5') {
      ContentCardRef.value?.getToolsList(tagId.value || '-3', true);
    } else {
      restoreListScrollAfterReturn();
    }
    isReturningHome.value = false;
  };

  const handleCloseToolPanel = async () => {
    isRestoringListScroll.value = true;
    ContentCardRef.value?.saveScrollPosition();
    clearAll();
    isSidebarCollapsed.value = false;
    syncRouteToUrl();
    await nextTick();
    if (tagId.value === '-5') {
      ContentCardRef.value?.getToolsList(tagId.value, true);
      isRestoringListScroll.value = false;
    } else {
      restoreListScrollAfterReturn();
    }
  };

  const handleCloseTab = async (uid: string) => {
    closeTab(uid);
    if (!hasOpenedTools.value) {
      isRestoringListScroll.value = true;
      ContentCardRef.value?.saveScrollPosition();
      syncRouteToUrl();
      await nextTick();
      if (tagId.value === '-5') {
        ContentCardRef.value?.getToolsList(tagId.value, true);
        isRestoringListScroll.value = false;
      } else {
        restoreListScrollAfterReturn();
      }
    }
  };

  watch(hasOpenedTools, (val) => {
    isSidebarCollapsed.value = val;
    if (!val && !isRestoringListScroll.value) {
      // 工具全部关闭，回到广场时刷新标签数量（如最近使用计数）
      refreshTagsList();
    }
  }, { immediate: true });

  watch(isSidebarCollapsed, (val) => {
    isSidebarAnimating.value = true;
    if (sidebarAnimateTimer) clearTimeout(sidebarAnimateTimer);
    sidebarAnimateTimer = setTimeout(() => {
      isSidebarAnimating.value = false;
      window.dispatchEvent(new Event('resize'));
    }, 320);

    // 从详情返回时不要 resetAll/checked 重拉列表，否则滚动会回到顶部
    if (val || isReturningHome.value || isRestoringListScroll.value) return;
    nextTick(() => {
      safeResetLabels();
    });
  });

  // 切换 tab 时同步 URL（业务参数由 tool-info-panel 根据 activeUid 恢复）
  const handleSwitchTab = (uid: string) => {
    switchTab(uid);
  };

  // 监听场景切换事件
  const { on: onEvent, off } = useEventBus();

  // 刷新所有数据（场景切换时调用）
  const refreshAllData = () => {
    refreshTagsList();
    if (hasOpenedTools.value) return;
    ContentCardRef.value?.getToolsList(tagId.value);
  };

  const handleTopNavGoHome = () => {
    if (!hasOpenedTools.value) return;
    void handleGoHomePage();
  };

  onMounted(() => {
    // 监听场景切换事件
    onEvent('scene:change', () => {
      refreshAllData();
    });
    onEvent('tools-square:go-home', handleTopNavGoHome);
    if (!routeUid && hasOpenedTools.value) {
      goHome();
    }
  });

  // 进详情前缓存滚动；从详情返回后还原（同实例 keep-alive 下作为兜底）
  onDeactivated(() => {
    ContentCardRef.value?.saveScrollPosition();
  });

  onActivated(() => {
    if (hasOpenedTools.value) return;
    isRestoringListScroll.value = true;
    nextTick(() => {
      if (tagId.value === '-5') {
        ContentCardRef.value?.getToolsList(tagId.value, true);
        isRestoringListScroll.value = false;
        return;
      }
      restoreListScrollAfterReturn();
    });
  });

  onUnmounted(() => {
    off('scene:change');
    off('tools-square:go-home', handleTopNavGoHome);
    if (sidebarAnimateTimer) clearTimeout(sidebarAnimateTimer);
    if (restoreListScrollTimer) clearTimeout(restoreListScrollTimer);
  });
</script>

<style scoped lang="postcss">
.tools-square {
  position: absolute;
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--bk-theme-surface-page);
  inset: 0;

  .square-page {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 0;
    padding: var(--bk-theme-page-padding);
    gap: var(--bk-theme-page-gap);
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--bk-theme-space-16);
  }

  .page-title {
    margin: 0;
    padding: 0;
    font-size: var(--bk-theme-font-size-xl);
    font-weight: var(--bk-theme-font-weight-bold);
    line-height: var(--bk-theme-line-height-xl);
    color: var(--bk-theme-text-strong);
  }

  .page-scene-selector {
    width: 208px;
    box-shadow: var(--bk-theme-overlay-shadow);
  }

  .page-toolbar {
    display: flex;
    align-items: center;
    gap: var(--bk-theme-space-12);
  }

  .capsule-tabs {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    height: var(--bk-theme-space-32);
    padding: var(--bk-theme-space-2);
    background: var(--bk-theme-collapse-bg);
    border-radius: var(--bk-theme-tab-pill-radius);
  }

  .capsule-tab {
    position: relative;
    display: flex;
    align-items: center;
    height: 28px;
    padding: 0 var(--bk-theme-space-16);
    font-size: var(--bk-theme-font-size-base);
    line-height: var(--bk-theme-line-height-base);
    color: var(--bk-theme-text-default);
    cursor: pointer;
    background: transparent;
    border: 0;
    border-radius: var(--bk-theme-tab-pill-radius);
    gap: var(--bk-theme-space-4);

    &:not(.is-active)::after {
      position: absolute;
      top: var(--bk-theme-space-6);
      right: 0;
      width: 1px;
      height: var(--bk-theme-space-16);
      background: var(--bk-theme-border-strong);
      content: '';
    }

    &:last-child::after,
    &.is-active::after,
    &:has(+ .is-active)::after {
      display: none;
    }

    &.is-active {
      color: var(--bk-theme-color-brand-2);
      background: var(--bk-theme-surface-default);
      box-shadow: var(--bk-theme-overlay-shadow);
    }
  }

  .capsule-count {
    display: inline-flex;
    align-items: center;
    height: 18px;
    padding: 0 var(--bk-theme-space-6);
    font-size: var(--bk-theme-font-size-sm);
    line-height: var(--bk-theme-line-height-sm);
    color: var(--bk-theme-text-default);
    background: var(--bk-theme-surface-default);
    border-radius: var(--bk-theme-tab-pill-radius);
  }

  .capsule-tab.is-active .capsule-count {
    color: var(--bk-theme-color-brand-1);
    background: var(--bk-theme-fill-info);
  }

  .capsule-count.is-skeleton,
  .capsule-tab.is-active .capsule-count.is-skeleton {
    width: var(--bk-theme-space-16);
    height: var(--bk-theme-space-16);
    padding: 0;
    background: var(--bk-theme-border-strong);
  }

  .tag-filter {
    flex-shrink: 0;
    width: 200px;
  }

  .search-anchor {
    flex: 1;
    min-width: 0;

    :deep(.card-search),
    :deep(.search-input) {
      width: 100%;
    }

    :deep(.bk-search-select-container) {
      min-height: var(--bk-theme-space-32);
      background-color: var(--bk-theme-surface-default);
      border-color: var(--bk-theme-control-border-color);
      border-radius: var(--bk-theme-control-radius);
    }

    :deep(.bk-search-select-container.is-focus) {
      background-color: var(--bk-theme-surface-default);
    }
  }

  .using-alert {
    flex-shrink: 0;
  }

  .using-alert-title {
    display: inline-flex;
    align-items: center;
    gap: var(--bk-theme-space-8);
  }

  .using-alert-link {
    padding: 0;
    font-size: inherit;
    line-height: inherit;
    color: var(--bk-theme-color-brand-2);
    cursor: pointer;
    background: transparent;
    border: 0;
  }

  .square-list {
    flex: 1;
    min-height: 0;
  }

  .content-content {
    width: 100%;
    height: 100%;
    min-width: 0;
    margin-top: 0;
    overflow: hidden;
    contain: layout style;
    transition: margin-left .3s ease;

    &.has-shadow {
      box-shadow: -3px 0 6px 0 rgb(0 0 0 / 10%);
    }

    .tools-square.is-animating & {
      pointer-events: none;

      .content-card {
        will-change: contents;
      }
    }

    .content-card {
      width: 100%;
      height: 100%;

      .content-card-wrapper {
        width: 100%;
        height: 100%;
      }
    }

  }
}
</style>
