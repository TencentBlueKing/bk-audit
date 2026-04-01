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
  <bk-popover
    ref="addPopoverRef"
    :arrow="false"
    ext-cls="add-tool-popover"
    placement="bottom"
    theme="light"
    trigger="click"
    :width="600"
    @after-show="handlePopoverShow">
    <div
      class="tab-add-btn"
      role="button"
      tabindex="0">
      <audit-icon type="add" />
    </div>
    <template #content>
      <div class="add-tool-panel">
        <!-- 搜索框 -->
        <div class="add-tool-search">
          <audit-icon
            class="search-icon"
            type="search1" />
          <input
            v-model="popoverSearchValue"
            class="search-input"
            placeholder="搜索"
            type="text">
        </div>
        <div class="add-tool-body">
          <!-- 左侧：按标签分组 -->
          <div class="add-tool-left">
            <template
              v-for="group in filteredGroupedTools"
              :key="group.tag_id">
              <div
                v-if="group.tools.length > 0"
                class="tool-group">
                <div
                  class="tool-group-title"
                  @click="toggleGroupCollapse(group.tag_id)">
                  <audit-icon
                    :class="{ 'is-collapsed': collapsedGroups[group.tag_id] }"
                    style="margin-right: 4px; font-size: 12px; color: #979ba5; transition: transform .2s;"
                    type="angle-fill-down" />
                  {{ group.tag_name }}
                </div>
                <template v-if="!collapsedGroups[group.tag_id]">
                  <div
                    v-for="tool in group.tools"
                    :key="tool.uid"
                    class="tool-group-item"
                    :class="{ 'is-added': isToolOpened(tool.uid) }"
                    @click="handleAddTool(tool)">
                    <audit-icon
                      class="tool-group-item-icon"
                      svg
                      :type="itemIcon(tool)" />
                    <span class="tool-group-item-name">{{ tool.name }}</span>
                    <audit-icon
                      v-if="isToolOpened(tool.uid)"
                      class="tool-group-item-check"
                      type="check-line" />
                  </div>
                </template>
              </div>
            </template>
            <bk-exception
              v-if="filteredGroupedTools.every(g => g.tools.length === 0)"
              class="no-data"
              scene="part"
              type="search-empty" />
          </div>
          <!-- 右侧：最近使用 / 我的收藏 -->
          <div class="add-tool-right">
            <div class="right-tab-header">
              <div
                class="right-tab-item"
                :class="{ active: rightActiveTab === 'recent' }"
                @click="rightActiveTab = 'recent'">
                <img
                  alt="clock"
                  class="right-tab-icon"
                  src="@images/clock.svg">
                最近使用
              </div>
              <div
                class="right-tab-item"
                :class="{ active: rightActiveTab === 'favorite' }"
                @click="rightActiveTab = 'favorite'">
                <img
                  alt="star"
                  class="right-tab-icon"
                  src="@images/star.svg">
                我的收藏
              </div>
            </div>
            <div class="right-tab-content">
              <template v-if="rightActiveTab === 'recent'">
                <div
                  v-for="tool in filteredRecentTools"
                  :key="tool.uid"
                  class="tool-group-item"
                  :class="{ 'is-added': isToolOpened(tool.uid) }"
                  @click="handleAddTool(tool)">
                  <audit-icon
                    class="tool-group-item-icon"
                    svg
                    :type="itemIcon(tool)" />
                  <span class="tool-group-item-name">{{ tool.name }}</span>
                  <audit-icon
                    v-if="isToolOpened(tool.uid)"
                    class="tool-group-item-check"
                    type="check-line" />
                </div>
                <bk-exception
                  v-if="filteredRecentTools.length === 0"
                  class="no-data"
                  scene="part"
                  type="empty" />
              </template>
              <template v-if="rightActiveTab === 'favorite'">
                <div
                  v-for="tool in filteredFavoriteTools"
                  :key="tool.uid"
                  class="tool-group-item"
                  :class="{ 'is-added': isToolOpened(tool.uid) }"
                  @click="handleAddTool(tool)">
                  <audit-icon
                    class="tool-group-item-icon"
                    svg
                    :type="itemIcon(tool)" />
                  <span class="tool-group-item-name">{{ tool.name }}</span>
                  <audit-icon
                    v-if="isToolOpened(tool.uid)"
                    class="tool-group-item-check"
                    type="check-line" />
                </div>
                <bk-exception
                  v-if="filteredFavoriteTools.length === 0"
                  class="no-data"
                  scene="part"
                  type="empty" />
              </template>
            </div>
          </div>
        </div>
      </div>
    </template>
  </bk-popover>
</template>

<script setup lang="ts">
  import { computed, nextTick, ref } from 'vue';

  import ToolManageService from '@service/tool-manage';

  import ToolInfo from '@model/tool/tool-info';

  import useRequest from '@/hooks/use-request';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

  interface Props {
    toolList: ToolInfo[];
    tagsEnums: TagItem[];
  }

  const props = defineProps<Props>();
  const emit = defineEmits<{
    addTool: [tool: ToolInfo];
  }>();

  const addPopoverRef = ref();
  const popoverSearchValue = ref('');
  const rightActiveTab = ref<'recent' | 'favorite'>('recent');
  const collapsedGroups = ref<Record<string, boolean>>({});

  // 已打开工具的 uid 集合
  const openedUidSet = computed(() => new Set(props.toolList.map(t => t.uid)));
  const isToolOpened = (uid: string) => openedUidSet.value.has(uid);

  // 切换分组折叠/展开
  const toggleGroupCollapse = (tagId: string) => {
    collapsedGroups.value[tagId] = !collapsedGroups.value[tagId];
  };

  const itemIcon = (item: { tool_type?: string }) => {
    switch (item.tool_type) {
    case 'data_search':
      return 'sqlxiao';
    case 'bk_vision':
      return 'bkvisonxiao';
    case 'api':
      return 'apixiao';
    default:
      return 'apixiao';
    }
  };

  // 获取所有工具（用于左侧分组）
  const allToolsList = ref<ToolInfo[]>([]);
  const {
    run: fetchAllToolsList,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: {} as any,
    onSuccess: (data: any) => {
      allToolsList.value = data.results || [];
    },
  });

  // 获取最近使用的工具
  const recentToolsList = ref<ToolInfo[]>([]);
  const {
    run: fetchRecentTools,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: {} as any,
    onSuccess: (data: any) => {
      recentToolsList.value = data.results || [];
    },
  });

  // 获取我的收藏的工具
  const favoriteToolsList = ref<ToolInfo[]>([]);
  const {
    run: fetchFavoriteTools,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: {} as any,
    onSuccess: (data: any) => {
      favoriteToolsList.value = (data.results || []).filter((t: ToolInfo) => t.favorite);
    },
  });

  // Popover 展开时加载数据
  const handlePopoverShow = () => {
    popoverSearchValue.value = '';
    rightActiveTab.value = 'recent';
    fetchAllToolsList({ page: 1, page_size: 200 });
    fetchRecentTools({ page: 1, page_size: 50, recent_used: true } as any);
    fetchFavoriteTools({ page: 1, page_size: 200 });
  };

  // 左侧分组标签（排除固定标签）
  const toolTagGroups = computed(() => props.tagsEnums.filter(tag => !tag.tag_id.startsWith('-') && tag.tag_id !== 'all'));

  // 按标签分组的工具列表（已过滤搜索关键词）
  const filteredGroupedTools = computed(() => {
    const keyword = popoverSearchValue.value.trim().toLowerCase();
    return toolTagGroups.value.map(tag => ({
      ...tag,
      tools: allToolsList.value.filter((tool) => {
        if (keyword && !tool.name.toLowerCase().includes(keyword)) return false;
        return tool.tags?.includes(tag.tag_id);
      }),
    }));
  });

  // 右侧最近使用
  const filteredRecentTools = computed(() => {
    const keyword = popoverSearchValue.value.trim().toLowerCase();
    return recentToolsList.value.filter((tool) => {
      if (keyword && !tool.name.toLowerCase().includes(keyword)) return false;
      return true;
    });
  });

  // 右侧我的收藏
  const filteredFavoriteTools = computed(() => {
    const keyword = popoverSearchValue.value.trim().toLowerCase();
    return favoriteToolsList.value.filter((tool) => {
      if (keyword && !tool.name.toLowerCase().includes(keyword)) return false;
      return true;
    });
  });

  // 点击添加工具
  const handleAddTool = (tool: ToolInfo) => {
    if (isToolOpened(tool.uid)) return;
    emit('addTool', tool);
    nextTick(() => {
      addPopoverRef.value?.popperInstance?.update?.();
    });
  };
</script>

<style scoped lang="postcss">
.tab-add-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  margin-left: 4px;
  font-size: 16px;
  color: #979ba5;
  cursor: pointer;
  border-radius: 50%;
  transition: all .15s;
  flex: 0 0 auto;
}

.tab-add-btn:hover {
  color: #63656e;
  background: #f0f1f5;
}

.tab-add-btn:active {
  color: #3a84ff;
  background: #e1ecff;
}

.add-tool-panel {
  display: flex;
  flex-direction: column;
  height: 400px;
}

.add-tool-search {
  display: flex;
  padding-left: 10px;
  border-bottom: 1px solid #dcdee5;
  align-items: center;
  gap: 6px;
}

.search-icon {
  font-size: 20px;
  color: #979ba5;
  flex: 0 0 auto;
}

.search-input {
  height: 28px;
  min-width: 0;
  font-size: 14px;
  line-height: 28px;
  color: #63656e;
  background: transparent;
  border: none;
  outline: none;
  flex: 1;
}

.search-input::placeholder {
  color: #c4c6cc;
}

.add-tool-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.add-tool-left {
  min-width: 0;
  padding: 4px 0;
  overflow-y: auto;
  border-right: 1px solid #dcdee5;
  flex: 1;
  scrollbar-width: thin;
  scrollbar-color: #dcdee5 transparent;
}

.add-tool-left::-webkit-scrollbar {
  width: 4px;
}

.add-tool-left::-webkit-scrollbar-track {
  background: transparent;
}

.add-tool-left::-webkit-scrollbar-thumb {
  background: #dcdee5;
  border-radius: 999px;
}

.add-tool-left::-webkit-scrollbar-thumb:hover {
  background: #c4c6cc;
}

.add-tool-right {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.tool-group {
  margin-bottom: 4px;
}

.tool-group-title {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 700;
  line-height: 20px;
  color: #979ba5;
  cursor: pointer;
  user-select: none;
}

.tool-group-title:hover {
  background: #f5f7fa;
}

.tool-group-title .is-collapsed {
  transform: rotate(-90deg);
}

.tool-group-item {
  display: flex;
  align-items: center;
  padding: 6px 12px 6px 20px;
  cursor: pointer;
  transition: background .15s;
  gap: 8px;
}

.tool-group-item:hover {
  background: #f0f5ff;
}

.tool-group-item.is-added {
  cursor: not-allowed;
  opacity: 50%;
}

.tool-group-item-icon {
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
}

.tool-group-item-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-size: 12px;
  line-height: 20px;
  color: #4d4f56;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-group-item-check {
  font-size: 16px;
  color: #3a84ff;
  flex: 0 0 auto;
}

.right-tab-header {
  display: flex;
  padding: 0 12px;
  border-bottom: 1px solid #dcdee5;
  justify-content: space-around;
}

.right-tab-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 20px;
  color: #63656e;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all .15s;
}

.right-tab-icon {
  display: block;
  width: 14px;
  height: 14px;
  margin-right: 4px;
  flex: 0 0 auto;
}

.right-tab-item:hover {
  color: #3a84ff;
}

.right-tab-item.active {
  font-weight: 500;
  color: #3a84ff;
  border-bottom-color: #3a84ff;
}

.right-tab-content {
  padding: 4px 0;
  overflow-y: auto;
  flex: 1;
  scrollbar-width: thin;
  scrollbar-color: #dcdee5 transparent;
}

.right-tab-content::-webkit-scrollbar {
  width: 4px;
}

.right-tab-content::-webkit-scrollbar-track {
  background: transparent;
}

.right-tab-content::-webkit-scrollbar-thumb {
  background: #dcdee5;
  border-radius: 999px;
}

.right-tab-content::-webkit-scrollbar-thumb:hover {
  background: #c4c6cc;
}

.no-data {
  padding: 40px 0;
}
</style>
