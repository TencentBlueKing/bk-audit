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
    <!-- 正在使用中的工具提示条（置顶全宽） -->
    <div
      v-if="activeToolsInScene.length > 0 && !hasOpenedTools"
      class="tool-using-tip">
      <img
        class="tip-icon"
        :src="infoBlueSvg">
      <span class="tip-text">
        {{ t('你有') }} <strong class="tip-count">{{ activeToolsInScene.length }}</strong> {{ t('个工具正在使用中') }}
      </span>
      <span
        class="tip-link"
        @click="handleContinueUsingTool">
        {{ t('点击继续') }}
      </span>
    </div>
    <div class="tools-square-body">
      <!-- 左侧标签 -->
      <div
        class="sidebar-wrapper"
        :class="{ 'is-collapsed': isSidebarCollapsed }">
        <!-- 收缩状态 -->
        <div
          v-show="isSidebarCollapsed"
          class="sidebar-collapsed"
          @click="isSidebarCollapsed = false">
          <div class="collapsed-inner">
            <span class="collapsed-text">快捷筛选</span>
            <img
              class="collapsed-toggle-icon"
              :src="foldRightIcon">
          </div>
        </div>
        <!-- 展开状态 -->
        <div
          v-show="!isSidebarCollapsed"
          class="sidebar-expanded">
          <!-- 场景系统选择器 -->
          <div class="scene-selector-wrapper">
            <scene-system-selector
              v-model="selectedScene"
              :list-scope="['scene']"
              :popover-width="210"
              scene-permission="view_scene"
              system-permission="view_system"
              width="210px"
              @change="handleSceneChange" />
          </div>
          <div class="sidebar-header">
            <span class="sidebar-title">快捷筛选</span>
            <img
              class="sidebar-toggle-icon"
              :src="foldLeftIcon"
              @click="isSidebarCollapsed = true">
          </div>
          <render-label
            ref="renderLabelRef"
            active="-3"
            :final="4"
            :labels="strategyLabelList"
            :render-style="renderStyle"
            :total="0"
            :upgrade-total="0"
            @checked="handleChecked" />
          <!-- 内侧折叠图标，垂直居中靠右 -->
          <div
            class="sidebar-collapse-trigger"
            @click="isSidebarCollapsed = true">
            <img
              class="ellipsis-icon"
              :src="ellipsisIcon">
          </div>
        </div>
      </div>

      <!-- 右侧内容-->
      <div
        class="content-content"
        :class="{ 'has-shadow': hasOpenedTools }">
        <div class="content-card">
          <div
            v-show="!hasOpenedTools"
            class="content-card-wrapper">
            <content-card
              ref="ContentCardRef"
              :is-cross-scene="scopeParams.scope_type === 'cross_scene'"
              :my-created="tagId === '-4'"
              :recent-used="tagId === '-5'"
              :scene-name-map="sceneNameMap"
              :scope-params="scopeParams"
              :tag-id="tagId"
              :tags-enums="tagsEnums"
              @change="handleChange"
              @open-tool="handleOpenTool" />
          </div>
          <tool-info-panel
            v-show="hasOpenedTools"
            :active-uid="activeToolUid"
            :scope-params="scopeParams"
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
  </div>
</template>

<script setup lang='ts'>
  import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import SceneManageService from '@service/scene-manage';
  import ToolManageService from '@service/tool-manage';

  import ToolInfo from '@model/tool/tool-info';

  import SceneSystemSelector from '@components/scene-system-selector/index.vue';

  import RenderLabel from '@views/strategy-manage/list/components/render-label.vue';

  import ContentCard from './square-content/concent-card.vue';
  import ToolInfoPanel from './square-content/tool-info-panel.vue';

  import useEventBus from '@/hooks/use-event-bus';
  import useRequest from '@/hooks/use-request';
  import type { DrillDownParams } from '@/hooks/use-tool-tabs';
  import useToolTabs from '@/hooks/use-tool-tabs';
  import ellipsisIcon from '@/images/ellipsis.svg';
  import favoriteIcon from '@/images/favorite.svg';
  import foldLeftIcon from '@/images/fold-left.svg';
  import foldRightIcon from '@/images/fold-right.svg';
  import infoBlueSvg from '@/images/info-blue.svg';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

  interface SceneItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
  }

  const renderLabelRef = ref();
  const ContentCardRef = ref<InstanceType<typeof ContentCard>>();

  // 场景ID → 场景名称映射
  const sceneNameMap = ref<Record<number, string>>({});
  const {
    run: fetchSceneAll,
  } = useRequest(SceneManageService.fetchSceneAll, {
    defaultValue: [],
    onSuccess: (data: Array<{ scene_id: number; name: string }>) => {
      const map: Record<number, string> = {};
      data.forEach((item) => {
        map[item.scene_id] = item.name;
      });
      sceneNameMap.value = map;
    },
  });
  // 初始化获取场景列表
  fetchSceneAll();
  const tagsEnums = ref<Array<TagItem>>([]);
  const tagId = ref('');
  const strategyLabelList = ref<Array<TagItem>>([]);
  const renderStyle = ref({
    backgroundColor: '#fff',
  });
  const isSidebarCollapsed = ref(false);
  const isSidebarAnimating = ref(false);
  let sidebarAnimateTimer: ReturnType<typeof setTimeout> | null = null;
  const isReturningHome = ref(false);
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
    const lastTool = openedTools.value[openedTools.value.length - 1];
    if (lastTool) {
      switchTab(lastTool.uid);
      handleOpenTool(lastTool);
    }
  };

  const routeUid = route.params.uid as string;
  const isDrillDownRoute = !!(routeUid && (route.query.drillKey || route.query.drillConfig));
  const isRefreshRestore = !!(routeUid && !route.query.drillKey && !route.query.drillConfig);
  const isProgrammaticReset = ref(false);

  // 从其他页面回到工具广场时，恢复之前打开的工具 tab 状态
  // 条件：URL 无 uid 参数（非下钻/刷新恢复），但内存中有打开的工具
  if (!routeUid && openedTools.value.length > 0) {
    if (activeToolUid.value) {
      // activeToolUid 有值说明离开前在工具详情，恢复 URL 到对应的工具详情路由
      router.replace({ name: 'toolDetail', params: { uid: activeToolUid.value } });
    }
    // activeToolUid 为空说明离开前在工具列表（首页），保持在工具列表页面，不自动打开工具详情
  }

  // 场景切换
  const getSceneKey = (item: SceneItem | null) => (item ? `${item.type}:${item.id}` : '');
  const handleSceneChange = async (value: SceneItem | null) => {
    const newKey = getSceneKey(value);
    const isActualChange = lastSceneKey.value !== null && lastSceneKey.value !== newKey;
    selectedScene.value = value;
    lastSceneKey.value = newKey;

    if (isActualChange) {
      // 用户主动切换场景 → 清空所有已打开的工具 tab，实现场景隔离
      clearAll();
      try {
        sessionStorage.removeItem('tool_tabs_search_list_map');
        sessionStorage.removeItem('tool_tabs_game_detail_map');
      } catch {
        // 静默处理
      }
      isSidebarCollapsed.value = false;
      syncRouteToUrl();
    }
    // 无论是初始化还是切换，都重新拉取标签和工具列表
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
        name: routeUid,
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
    renderLabelRef.value?.resetAll([]);
    nextTick(() => {
      isProgrammaticReset.value = false;
    });
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
      const iconMap: Record<number, string> = {
        0: 'quanbu-xuanzhong',
        1: 'morentouxiang',
        2: 'shijian',
        4: 'weifenpei',
      };
      // index 3 为"我的收藏"，使用图片图标
      const imgIconMap: Record<number, string> = {
        3: favoriteIcon,
      };
      // 前5项为固定分类，不参与排序；后续为动态标签
      const fixedTags = data.slice(0, FIXED_TAG_COUNT);
      const dynamicTags = data.slice(FIXED_TAG_COUNT);
      strategyLabelList.value = [
        ...fixedTags.map((item: any, index: number) => ({
          ...item,
          strategy_count: item.tool_count ?? 0,
          icon: iconMap[index] || 'tag',
          ...(imgIconMap[index] ? { imgIcon: imgIconMap[index], icon: undefined } : {}),
        })),
        ...dynamicTags.map((item: any) => ({
          ...item,
          strategy_count: item.tool_count ?? 0,
          icon: 'tag',
        })),
      ];
      tagsEnums.value = strategyLabelList.value;
      // 始终清空 all，避免 render-label 顶部出现空白行
      renderLabelRef.value?.resetAll([]);
      // 初始化阶段（tagId 为空）：通过 resetAll 触发 handleChecked 来加载工具列表
      // 场景切换阶段（tagId 已有值）：只更新标签数据，工具列表已在 handleSceneChange 中触发
      if (!tagId.value) {
        safeResetLabels();
      }
    },
  });

  // 刷新标签列表（带 scope 参数）
  const refreshTagsList = () => {
    fetchToolsTagsList({ ...scopeParams.value, status: 'published' });
  };

  const syncRouteToUrl = (uid?: string) => {
    if (uid && (route.name !== 'toolDetail' || route.params.uid !== uid)) {
      router.replace({ name: 'toolDetail', params: { uid } });
    } else if (!uid && route.name !== 'toolsSquare') {
      router.replace({ name: 'toolsSquare' });
    }
  };

  const handleOpenTool = (tool: ToolInfo) => {
    openTool(tool);
    isSidebarCollapsed.value = true;
    syncRouteToUrl(tool.uid);
  };

  const handleAddToolFromPopover = (tool: ToolInfo) => {
    openTool(tool);
    isSidebarCollapsed.value = true;
    syncRouteToUrl(tool.uid);
  };

  const handleGoHomePage = async () => {
    isReturningHome.value = true;
    tagId.value = '-3';
    goHome();
    syncRouteToUrl();
    await nextTick();
    renderLabelRef.value?.setLabel('-3');
    ContentCardRef.value?.getToolsList(tagId.value);
    isReturningHome.value = false;
  };

  const handleCloseToolPanel = async () => {
    clearAll();
    isSidebarCollapsed.value = false;
    syncRouteToUrl();
    await nextTick();
    ContentCardRef.value?.getToolsList(tagId.value);
  };

  const handleCloseTab = async (uid: string) => {
    closeTab(uid);
    if (!hasOpenedTools.value) {
      syncRouteToUrl();
      await nextTick();
      ContentCardRef.value?.getToolsList(tagId.value);
    } else {
      syncRouteToUrl(activeToolUid.value);
    }
  };

  watch(hasOpenedTools, (val) => {
    isSidebarCollapsed.value = val;
  }, { immediate: true });

  watch(isSidebarCollapsed, (val) => {
    isSidebarAnimating.value = true;
    if (sidebarAnimateTimer) clearTimeout(sidebarAnimateTimer);
    sidebarAnimateTimer = setTimeout(() => {
      isSidebarAnimating.value = false;
      window.dispatchEvent(new Event('resize'));
    }, 320);

    if (val || isReturningHome.value) return;
    nextTick(() => {
      safeResetLabels();
      if (hasOpenedTools.value) {
        renderLabelRef.value?.setLabel('');
      } else {
        renderLabelRef.value?.setLabel((!tagId.value || tagId.value === '-3') ? '-3' : tagId.value);
      }
    });
  });

  // 切换 tab 时同步 URL
  const handleSwitchTab = (uid: string) => {
    switchTab(uid);
    syncRouteToUrl(uid);
  };

  // 监听场景切换事件
  const { on: onEvent, off } = useEventBus();

  // 刷新所有数据（场景切换时调用）
  const refreshAllData = () => {
    refreshTagsList();
    if (hasOpenedTools.value) return;
    ContentCardRef.value?.getToolsList(tagId.value);
  };

  onMounted(() => {
    // 监听场景切换事件
    onEvent('scene:change', () => {
      refreshAllData();
    });
    if (hasOpenedTools.value && !isDrillDownRoute && !isRefreshRestore) {
      syncRouteToUrl(activeToolUid.value);
    }
  });

  onUnmounted(() => {
    off('scene:change');
    if (sidebarAnimateTimer) clearTimeout(sidebarAnimateTimer);
  });
</script>

<style scoped lang="postcss">
.tools-square {
  position: absolute;
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100%;
  background-color: #f5f7fa;
  inset: 0;

  .tool-using-tip {
    position: relative;
    z-index: 2;
    display: flex;
    width: calc(100% - 2px);
    height: 40px;
    padding: 0 12px;
    margin: 0 1px;
    font-size: 12px;
    line-height: 36px;
    color: #4d4f56;
    background: #f0f5ff;
    border: 1px solid #cddffe;
    border-top: none;
    box-shadow: 0 2px 4px 0 #e1e8f4;
    align-items: center;
    flex-shrink: 0;

    .tip-icon {
      display: inline-block;
      width: 14px;
      height: 14px;
      margin-right: 6px;
      flex-shrink: 0;
    }

    .tip-text {
      margin-right: 8px;
    }

    .tip-link {
      color: #5897ff;
      cursor: pointer;

      &:hover {
        color: #1768ef;
      }
    }
  }

  .tools-square-body {
    display: flex;
    width: 100%;
    flex: 1;
    min-height: 0;
  }

  .sidebar-wrapper {
    height: 100%;
    padding: 20px;
    overflow: hidden;
    background-color: #f5f7fa;
    transition: width .3s ease;
    will-change: width;
    contain: layout style;

    /* position: relative; */
    flex-shrink: 0;

    &.is-collapsed {
      width: 100px;
    }

    &:not(.is-collapsed) {
      width: 282px;
    }
  }

  .sidebar-collapsed {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    height: 100%;
    padding-top: 16px;
    cursor: pointer;
    border-radius: 8px;
    opacity: 100%;
    transition: opacity .2s ease .1s;

    .collapsed-inner {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 52px;
      padding: 20px 0;
      background-color: #fff;
      border-radius: 4px;
      gap: 2px;
      box-shadow: 0 0 10px 0 rgb(0 0 0 / 10%);
    }

    .collapsed-text {
      font-size: 14px;
      line-height: 1.8;
      letter-spacing: 10px;
      color: #313238;
      writing-mode: vertical-rl;
    }

    .collapsed-toggle-icon {
      width: 16px;
      height: 16px;
    }
  }

  .sidebar-expanded {
    position: relative;
    width: 240px;
    height: 100%;
    background-color: #fff;
    border-radius: 4px;
    opacity: 100%;
    box-shadow: 0  2px 4px  0 rgb(25 25 41 / 5%);
    transition: opacity .2s ease .1s;

    .scene-selector-wrapper {
      padding: 16px 16px 0;
    }

    .sidebar-header {
      position: relative;
      display: flex;
      height: 52px;
      padding: 0 16px 0 26px;
      align-items: center;
      justify-content: space-between;

      &::after {
        position: absolute;
        right: 16px;
        bottom: 0;
        left: 16px;
        border-bottom: 1px solid #eaebf0;
        content: '';
      }

      .sidebar-title {
        font-size: 14px;
        font-weight: 500;
        color: #313238;
      }

      .sidebar-toggle-icon {
        width: 16px;
        height: 16px;
        cursor: pointer;
      }
    }

    :deep(.render-label-box) {
      height: calc(100% - 52px - 48px);

      .render-label {
        padding: 0;

        .label-item {
          padding: 0 26px;

          &.final {
            position: relative;
            border-bottom: none;

            &::after {
              position: absolute;
              right: 16px;
              bottom: 0;
              left: 16px;
              border-bottom: 1px solid #eaebf0;
              content: '';
            }
          }
        }

      }

      .operation-box {
        display: none;
      }
    }

    .sidebar-collapse-trigger {
      position: absolute;
      top: 50%;
      right: 0;
      z-index: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 100%;
      cursor: pointer;
      transform: translateY(-50%);

      &:hover {
        color: #3a84ff;
      }

      .ellipsis-icon {
        width: 14px;
        height: 18px;
      }
    }
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
