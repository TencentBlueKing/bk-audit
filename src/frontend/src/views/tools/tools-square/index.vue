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
        <!-- 场景系统选择器 -->
        <div class="scene-selector-wrapper">
          <scene-system-selector
            v-model="selectedScene"
            :popover-width="250"
            width="100%"
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
        <content-card
          v-if="!hasOpenedTools"
          ref="ContentCardRef"
          :my-created="tagId === '-4'"
          :recent-used="tagId === '-5'"
          :tag-id="tagId"
          :tags-enums="tagsEnums"
          @change="handleChange"
          @open-tool="handleOpenTool" />
        <tool-info-panel
          v-else
          :active-uid="activeToolUid"
          :tags-enums="tagsEnums"
          :tool-list="openedTools"
          @add-tool="handleAddToolFromPopover"
          @close="handleCloseToolPanel"
          @close-tab="handleCloseTab"
          @go-home="handleGoHomePage"
          @switch-tab="switchTab" />
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { nextTick, onMounted, ref, watch } from 'vue';

  import ToolManageService from '@service/tool-manage';

  import ToolInfo from '@model/tool/tool-info';

  import SceneSystemSelector from '@components/scene-system-selector/index.vue';

  import RenderLabel from '@views/strategy-manage/list/components/render-label.vue';

  import ContentCard from './square-content/concent-card.vue';
  import ToolInfoPanel from './square-content/tool-info-panel.vue';

  import useRequest from '@/hooks/use-request';
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

  interface SceneItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
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

  // 场景选择器
  const selectedScene = ref<SceneItem | null>({
    id: '100001',
    name: '主机安全审计',
    type: 'scene',
  });

  // 场景切换
  const handleSceneChange = (value: SceneItem | null) => {
    console.log('场景切换:', value);
    // TODO: 根据选择的场景/系统重新加载工具列表
  };

  const {
    openedTools,
    activeToolUid,
    hasOpenedTools,
    openTool,
    closeTab,
    switchTab,
    goHome,
    clearAll,
  } = useToolTabs();

  // 选中左侧label
  const handleChecked = async (name: string) => {
    tagId.value = name;
    if (hasOpenedTools.value) {
      goHome();
      await nextTick();
    }
    ContentCardRef.value?.getToolsList(name);
  };

  const handleChange = () => {
    fetchToolsTagsList();
  };

  const {
    run: fetchToolsTagsList,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    onSuccess: (data) => {
      const strategyList = data
        .filter(item => item.tag_name && item.tag_name.trim() !== '')
        .map(item => ({ ...item, icon: '' }));
      const iconMap: Record<number, string> = {
        0: 'quanbu-xuanzhong',
        1: 'morentouxiang',
        2: 'shijian',
        3: 'weifenpei',
      };
      strategyLabelList.value = strategyList.map((item: any, index: number) => ({
        ...item,
        icon: iconMap[index] || 'tag',
      }));

      tagsEnums.value = strategyLabelList.value;
      renderLabelRef.value?.resetAll([]);
    },
  });

  const handleOpenTool = (tool: ToolInfo) => {
    openTool(tool);
    isSidebarCollapsed.value = true;
  };

  const handleAddToolFromPopover = (tool: ToolInfo) => {
    openTool(tool, false);
  };

  const handleGoHomePage = async () => {
    isReturningHome.value = true;
    tagId.value = '-3';
    goHome();
    await nextTick();
    await nextTick();
    renderLabelRef.value?.setLabel('-3');
    ContentCardRef.value?.getToolsList(tagId.value);
    isReturningHome.value = false;
  };

  // 关闭整个工具详情面板（点击 ×）
  const handleCloseToolPanel = async () => {
    clearAll();
    isSidebarCollapsed.value = false;
    await nextTick();
    ContentCardRef.value?.getToolsList(tagId.value);
  };

  // 关闭单个 tab
  const handleCloseTab = async (uid: string) => {
    closeTab(uid);
    if (!hasOpenedTools.value) {
      await nextTick();
      ContentCardRef.value?.getToolsList(tagId.value);
    }
  };

  watch(hasOpenedTools, (val) => {
    if (val) {
      isSidebarCollapsed.value = true;
    } else {
      isSidebarCollapsed.value = false;
    }
  }, { immediate: true });

  watch(isSidebarCollapsed, (val) => {
    if (!val) {
      if (isReturningHome.value) return;
      nextTick(() => {
        renderLabelRef.value?.resetAll([]);
        if (hasOpenedTools.value) {
          renderLabelRef.value?.setLabel('');
        } else {
          const restoreLabel = (!tagId.value || tagId.value === '-3') ? '-3' : tagId.value;
          renderLabelRef.value?.setLabel(restoreLabel);
        }
      });
    }
  });

  onMounted(() => {
    fetchToolsTagsList();
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
    overflow: auto;
    transition: margin-left .3s ease;

    &.has-shadow {
      box-shadow: -3px 0 6px 0 rgb(0 0 0 / 10%);
    }

    .content-card {
      width: 100%;
      height: 100%;
    }

  }
}
</style>
