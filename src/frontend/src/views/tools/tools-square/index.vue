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
  <div class="tools-square">
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
          :final="3"
          :labels="strategyLabelList"
          :render-style="renderStyle"
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
            :my-created="tagId === '-4'"
            :recent-used="tagId === '-5'"
            :tag-id="tagId"
            :tags-enums="tagsEnums"
            @change="fetchToolsTagsList"
            @open-tool="handleOpenTool" />
        </div>
        <tool-info-panel
          v-show="hasOpenedTools"
          :active-uid="activeToolUid"
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
  import { nextTick, onMounted, ref, watch } from 'vue';
  import { useRoute, useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import ToolInfo from '@model/tool/tool-info';

  import RenderLabel from '@views/strategy-manage/list/components/render-label.vue';

  import ContentCard from './square-content/concent-card.vue';
  import ToolInfoPanel from './square-content/tool-info-panel.vue';

  import useRequest from '@/hooks/use-request';
  import type { DrillDownParams } from '@/hooks/use-tool-tabs';
  import useToolTabs from '@/hooks/use-tool-tabs';
  import ellipsisIcon from '@/images/ellipsis.svg';
  import foldLeftIcon from '@/images/fold-left.svg';
  import foldRightIcon from '@/images/fold-right.svg';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }
  const renderLabelRef = ref();
  const ContentCardRef = ref<InstanceType<typeof ContentCard>>();
  const tagsEnums = ref<Array<TagItem>>([]);
  const tagId = ref('');
  const strategyLabelList = ref<Array<TagItem>>([]);
  const renderStyle = ref({
    backgroundColor: '#fff',
  });
  const isSidebarCollapsed = ref(false);
  const isReturningHome = ref(false);
  const route = useRoute();
  const router = useRouter();
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

  const routeUid = route.params.uid as string;
  const isDrillDownRoute = !!(routeUid && route.query.drillConfig);
  const isRefreshRestore = !!(routeUid && !route.query.drillConfig);
  const isProgrammaticReset = ref(false);

  if (isDrillDownRoute) {
    resetForDrillDown();
    const drillUid = routeUid;
    let drillConfig = null;
    let rowData = null;
    try {
      const drillConfigRaw = route.query.drillConfig as string;
      const rowDataRaw = route.query.rowData as string;
      if (drillConfigRaw) drillConfig = JSON.parse(decodeURIComponent(drillConfigRaw));
      if (rowDataRaw) rowData = JSON.parse(decodeURIComponent(rowDataRaw));
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

  const {
    run: fetchToolsTagsList,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    onSuccess: (data) => {
      const iconMap: Record<number, string> = {
        0: 'quanbu-xuanzhong',
        1: 'morentouxiang',
        2: 'shijian',
        3: 'weifenpei',
      };
      strategyLabelList.value = data
        .filter(item => item.tag_name?.trim())
        .map((item: any, index: number) => ({
          ...item,
          icon: iconMap[index] || 'tag',
        }));
      tagsEnums.value = strategyLabelList.value;
      safeResetLabels();
    },
  });

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
    openTool(tool, false);
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

  onMounted(() => {
    fetchToolsTagsList();
    if (hasOpenedTools.value && !isDrillDownRoute && !isRefreshRestore) {
      syncRouteToUrl(activeToolUid.value);
    }
  });
</script>

<style scoped lang="postcss">
.tools-square {
  position: absolute;
  display: flex;
  width: 100vw;
  height: 100%;
  background-color: #f5f7fa;
  inset: 0;

  .sidebar-wrapper {
    height: 100%;
    padding: 20px;
    overflow: hidden;
    background-color: #f5f7fa;
    transition: width .3s ease;

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
      height: calc(100% - 52px);

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
    overflow: auto;
    transition: margin-left .3s ease;

    &.has-shadow {
      box-shadow: -3px 0 6px 0 rgb(0 0 0 / 10%);
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
