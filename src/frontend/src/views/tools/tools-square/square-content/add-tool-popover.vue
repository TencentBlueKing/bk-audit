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
            :placeholder="t('请输入关键字搜索')"
            type="text">
        </div>
        <div class="add-tool-body">
          <!-- 左侧：按场景/系统分组（跨场景/跨系统模式）或平铺列表 -->
          <div class="add-tool-left">
            <template v-if="isGroupedMode">
              <template
                v-for="group in filteredGroupedTools"
                :key="group.groupKey">
                <div
                  v-if="group.tools.length > 0"
                  class="tool-group">
                  <div
                    class="tool-group-title"
                    @click="toggleGroupCollapse(group.groupKey)">
                    <audit-icon
                      :class="{ 'is-collapsed': collapsedGroups.has(group.groupKey) }"
                      style="margin-right: 4px; font-size: 12px; color: #979ba5; transition: transform .2s;"
                      type="angle-fill-down" />
                    {{ group.groupName }}({{ group.groupId }})
                  </div>
                  <template v-if="!collapsedGroups.has(group.groupKey)">
                    <div
                      v-for="tool in group.tools"
                      :key="tool.uid"
                      v-bk-tooltips="{
                        content: '该工具已打开',
                        disabled: !isToolOpened(tool.uid),
                        delay: [300, 0],
                        placement: 'right'
                      }"
                      class="tool-group-item"
                      :class="{ 'is-added': isToolOpened(tool.uid) }"
                      @click="handleAddTool(tool, group.groupKey)">
                      <img
                        v-if="tool.tool_type === 'smart_page'"
                        alt="smart_page"
                        class="tool-group-item-icon"
                        :src="userProfileIcon">
                      <audit-icon
                        v-else
                        class="tool-group-item-icon"
                        svg
                        :type="itemIcon(tool)" />
                      <span class="tool-group-item-name">{{ tool.name }}</span>
                      <span
                        v-if="isToolOpened(tool.uid)"
                        class="tool-opened-status">
                        <audit-icon
                          svg
                          type="normal" />
                      </span>
                    </div>
                  </template>
                </div>
              </template>
              <bk-exception
                v-if="filteredGroupedTools.every(g => g.tools.length === 0)"
                class="no-data"
                scene="part"
                type="search-empty" />
            </template>
            <template v-else>
              <div
                v-for="tool in filteredFlatTools"
                :key="tool.uid"
                v-bk-tooltips="{
                  content: '该工具已打开',
                  disabled: !isToolOpened(tool.uid),
                  delay: [300, 0],
                  placement: 'right'
                }"
                class="tool-group-item"
                :class="{ 'is-added': isToolOpened(tool.uid) }"
                @click="handleAddTool(tool)">
                <img
                  v-if="tool.tool_type === 'smart_page'"
                  alt="smart_page"
                  class="tool-group-item-icon"
                  :src="userProfileIcon">
                <audit-icon
                  v-else
                  class="tool-group-item-icon"
                  svg
                  :type="itemIcon(tool)" />
                <span class="tool-group-item-name">{{ tool.name }}</span>
                <span
                  v-if="isToolOpened(tool.uid)"
                  class="tool-opened-status">
                  <audit-icon
                    svg
                    type="normal" />
                </span>
              </div>
              <bk-exception
                v-if="filteredFlatTools.length === 0"
                class="no-data"
                scene="part"
                type="search-empty" />
            </template>
          </div>
          <!-- 右侧：最近使用 / 我的收藏 -->
          <div class="add-tool-right">
            <div class="right-tab-header">
              <div
                class="right-tab-item"
                :class="{ active: rightActiveTab === 'recent' }"
                @click="rightActiveTab = 'recent'">
                <i class="right-tab-icon right-tab-icon-clock" />
                {{ t('最近使用') }}
              </div>
              <div
                class="right-tab-item"
                :class="{ active: rightActiveTab === 'favorite' }"
                @click="rightActiveTab = 'favorite'">
                <i class="right-tab-icon right-tab-icon-star" />
                {{ t('我的收藏') }}
              </div>
            </div>
            <div class="right-tab-content">
              <template v-if="rightActiveTab === 'recent'">
                <template v-if="isGroupedMode">
                  <template
                    v-for="group in filteredRecentGrouped"
                    :key="group.groupKey">
                    <div
                      v-if="group.tools.length > 0"
                      class="tool-group">
                      <div
                        class="tool-group-title"
                        @click="toggleRightGroupCollapse(group.groupKey)">
                        <audit-icon
                          :class="{ 'is-collapsed': collapsedRightGroups.has(group.groupKey) }"
                          style="margin-right: 4px; font-size: 12px; color: #979ba5; transition: transform .2s;"
                          type="angle-fill-down" />
                        {{ group.groupName }}({{ group.groupId }})
                      </div>
                      <template v-if="!collapsedRightGroups.has(group.groupKey)">
                        <div
                          v-for="tool in group.tools"
                          :key="tool.uid"
                          v-bk-tooltips="{
                            content: '该工具已打开',
                            disabled: !isToolOpened(tool.uid),
                            delay: [300, 0],
                            placement: 'right'
                          }"
                          class="tool-group-item"
                          :class="{ 'is-added': isToolOpened(tool.uid) }"
                          @click="handleAddTool(tool, group.groupKey)">
                          <img
                            v-if="tool.tool_type === 'smart_page'"
                            alt="smart_page"
                            class="tool-group-item-icon"
                            :src="userProfileIcon">
                          <audit-icon
                            v-else
                            class="tool-group-item-icon"
                            svg
                            :type="itemIcon(tool)" />
                          <span class="tool-group-item-name">{{ tool.name }}</span>
                          <span
                            v-if="isToolOpened(tool.uid)"
                            class="tool-opened-status">
                            <audit-icon
                              svg
                              type="normal" />
                          </span>
                        </div>
                      </template>
                    </div>
                  </template>
                </template>
                <template v-else>
                  <div
                    v-for="tool in filteredRecentTools"
                    :key="tool.uid"
                    v-bk-tooltips="{
                      content: '该工具已打开',
                      disabled: !isToolOpened(tool.uid),
                      delay: [300, 0],
                      placement: 'right'
                    }"
                    class="tool-group-item"
                    :class="{ 'is-added': isToolOpened(tool.uid) }"
                    @click="handleAddTool(tool)">
                    <img
                      v-if="tool.tool_type === 'smart_page'"
                      alt="smart_page"
                      class="tool-group-item-icon"
                      :src="userProfileIcon">
                    <audit-icon
                      v-else
                      class="tool-group-item-icon"
                      svg
                      :type="itemIcon(tool)" />
                    <span class="tool-group-item-name">{{ tool.name }}</span>
                    <span
                      v-if="isToolOpened(tool.uid)"
                      class="tool-opened-status">
                      <audit-icon
                        svg
                        type="normal" />
                    </span>
                  </div>
                </template>
                <bk-exception
                  v-if="isGroupedMode
                    ? filteredRecentGrouped.every(g => g.tools.length === 0)
                    : filteredRecentTools.length === 0"
                  class="no-data"
                  scene="part"
                  type="empty" />
              </template>
              <template v-if="rightActiveTab === 'favorite'">
                <template v-if="isGroupedMode">
                  <template
                    v-for="group in filteredFavoriteGrouped"
                    :key="group.groupKey">
                    <div
                      v-if="group.tools.length > 0"
                      class="tool-group">
                      <div
                        class="tool-group-title"
                        @click="toggleRightGroupCollapse(group.groupKey)">
                        <audit-icon
                          :class="{ 'is-collapsed': collapsedRightGroups.has(group.groupKey) }"
                          style="margin-right: 4px; font-size: 12px; color: #979ba5; transition: transform .2s;"
                          type="angle-fill-down" />
                        {{ group.groupName }}({{ group.groupId }})
                      </div>
                      <template v-if="!collapsedRightGroups.has(group.groupKey)">
                        <div
                          v-for="tool in group.tools"
                          :key="tool.uid"
                          v-bk-tooltips="{
                            content: '该工具已打开',
                            disabled: !isToolOpened(tool.uid),
                            delay: [300, 0],
                            placement: 'right'
                          }"
                          class="tool-group-item"
                          :class="{ 'is-added': isToolOpened(tool.uid) }"
                          @click="handleAddTool(tool, group.groupKey)">
                          <img
                            v-if="tool.tool_type === 'smart_page'"
                            alt="smart_page"
                            class="tool-group-item-icon"
                            :src="userProfileIcon">
                          <audit-icon
                            v-else
                            class="tool-group-item-icon"
                            svg
                            :type="itemIcon(tool)" />
                          <span class="tool-group-item-name">{{ tool.name }}</span>
                          <span
                            v-if="isToolOpened(tool.uid)"
                            class="tool-opened-status">
                            <audit-icon
                              svg
                              type="normal" />
                          </span>
                        </div>
                      </template>
                    </div>
                  </template>
                </template>
                <template v-else>
                  <div
                    v-for="tool in filteredFavoriteTools"
                    :key="tool.uid"
                    v-bk-tooltips="{
                      content: '该工具已打开',
                      disabled: !isToolOpened(tool.uid),
                      delay: [300, 0],
                      placement: 'right'
                    }"
                    class="tool-group-item"
                    :class="{ 'is-added': isToolOpened(tool.uid) }"
                    @click="handleAddTool(tool)">
                    <img
                      v-if="tool.tool_type === 'smart_page'"
                      alt="smart_page"
                      class="tool-group-item-icon"
                      :src="userProfileIcon">
                    <audit-icon
                      v-else
                      class="tool-group-item-icon"
                      svg
                      :type="itemIcon(tool)" />
                    <span class="tool-group-item-name">{{ tool.name }}</span>
                    <span
                      v-if="isToolOpened(tool.uid)"
                      class="tool-opened-status">
                      <audit-icon
                        svg
                        type="normal" />
                    </span>
                  </div>
                </template>
                <bk-exception
                  v-if="isGroupedMode
                    ? filteredFavoriteGrouped.every(g => g.tools.length === 0)
                    : filteredFavoriteTools.length === 0"
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
  import { useI18n } from 'vue-i18n';

  import type { ToolDetailOverrideContext } from '@/utils/assist/scene-system-params';


  import useRequest from '@/hooks/use-request';
  import userProfileIcon from '@/images/user.svg';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

  interface Props {
    toolList: ToolInfo[];
    // eslint-disable-next-line vue/no-unused-properties
    tagsEnums: TagItem[];
    scopeParams?: {
      scope_type?: string;
      scope_id?: string;
    };
    sceneNameMap?: Record<number, string>;
    systemNameMap?: Record<string, string>;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<{
    addTool: [tool: ToolInfo, overrideContext?: ToolDetailOverrideContext];
    switchTool: [tool: ToolInfo];
  }>();

  const { t } = useI18n();
  const addPopoverRef = ref();
  const popoverSearchValue = ref('');
  const rightActiveTab = ref<'recent' | 'favorite'>('recent');
  const collapsedGroups = ref<Set<string>>(new Set());
  const collapsedRightGroups = ref<Set<string>>(new Set());

  const UNCATEGORIZED_KEY = '__uncategorized__';

  // 是否为跨场景/跨系统模式
  const isCrossScene = computed(() => props.scopeParams?.scope_type === 'cross_scene');
  const isCrossSystem = computed(() => props.scopeParams?.scope_type === 'cross_system');
  const isGroupedMode = computed(() => isCrossScene.value || isCrossSystem.value);

  // 已打开工具的 uid 集合
  const openedUidSet = computed(() => new Set(props.toolList.map(t => t.uid)));
  const isToolOpened = (uid: string) => openedUidSet.value.has(uid);

  // 切换分组折叠/展开
  const toggleGroupCollapse = (groupKey: string) => {
    if (collapsedGroups.value.has(groupKey)) {
      collapsedGroups.value.delete(groupKey);
    } else {
      collapsedGroups.value.add(groupKey);
    }
  };

  const toggleRightGroupCollapse = (groupKey: string) => {
    if (collapsedRightGroups.value.has(groupKey)) {
      collapsedRightGroups.value.delete(groupKey);
    } else {
      collapsedRightGroups.value.add(groupKey);
    }
  };

  const itemIcon = (item: { tool_type?: string }) => {
    switch (item.tool_type) {
    case 'data_search':
      return 'sqlxiao';
    case 'bk_vision':
      return 'bkvisonxiao';
    case 'api':
      return 'apixiao';
    case 'smart_page':
      return 'user';
    default:
      return 'apixiao';
    }
  };

  // 获取所有工具（用于左侧分组）
  const allToolsList = ref<ToolInfo[]>([]);
  const {
    run: fetchAllToolsList,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: [] as ToolInfo[],
    onSuccess: (data: ToolInfo[]) => {
      allToolsList.value = data || [];
    },
  });

  // 获取最近使用的工具
  const recentToolsList = ref<ToolInfo[]>([]);
  const {
    run: fetchRecentTools,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: [] as ToolInfo[],
    onSuccess: (data: ToolInfo[]) => {
      recentToolsList.value = data || [];
    },
  });

  // 获取我的收藏的工具
  const favoriteToolsList = ref<ToolInfo[]>([]);
  const {
    run: fetchFavoriteTools,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: [] as ToolInfo[],
    onSuccess: (data: ToolInfo[]) => {
      favoriteToolsList.value = (data || []).filter((t: ToolInfo) => t.favorite);
    },
  });

  // Popover 展开时加载数据
  const handlePopoverShow = () => {
    popoverSearchValue.value = '';
    rightActiveTab.value = 'recent';
    const scope = props.scopeParams || {};
    fetchAllToolsList({ status: 'published', ...scope });
    fetchRecentTools({ recent_used: true, status: 'published', ...scope } as any);
    fetchFavoriteTools({ status: 'published', ...scope });
  };

  // 左侧分组标签（排除固定标签）
  // const toolTagGroups = computed(() =>
  //   props.tagsEnums.filter(tag => !tag.tag_id.startsWith('-') && tag.tag_id !== 'all'));

  interface ToolGroup {
    groupKey: string;
    groupName: string;
    groupId: string | number;
    tools: ToolInfo[];
  }

  const buildSceneGroups = (tools: ToolInfo[]): ToolGroup[] => {
    const groupMap = new Map<string, ToolInfo[]>();
    const sceneOrder: string[] = [];
    tools.forEach((tool) => {
      const sceneIds = tool.visibility?.scene_ids || [];
      if (sceneIds.length === 0) {
        if (!groupMap.has('0')) {
          groupMap.set('0', []);
          sceneOrder.push('0');
        }
        groupMap.get('0')!.push(tool);
      } else {
        sceneIds.forEach((sid: number) => {
          const key = String(sid);
          if (!groupMap.has(key)) {
            groupMap.set(key, []);
            sceneOrder.push(key);
          }
          groupMap.get(key)!.push(tool);
        });
      }
    });
    const nameMap = props.sceneNameMap || {};
    return sceneOrder.map((key) => {
      const sid = Number(key);
      return {
        groupKey: key,
        groupId: sid,
        groupName: sid === 0 ? t('未分类') : (nameMap[sid] || `场景 ${sid}`),
        tools: groupMap.get(key) || [],
      };
    }).sort((a, b) => Number(b.groupKey) - Number(a.groupKey));
  };

  const buildSystemGroups = (tools: ToolInfo[]): ToolGroup[] => {
    const groupMap = new Map<string, ToolInfo[]>();
    const systemOrder: string[] = [];
    tools.forEach((tool) => {
      const systemIds = (tool.visibility?.system_ids || []).map(id => String(id));
      if (systemIds.length === 0) {
        if (!groupMap.has(UNCATEGORIZED_KEY)) {
          groupMap.set(UNCATEGORIZED_KEY, []);
          systemOrder.push(UNCATEGORIZED_KEY);
        }
        groupMap.get(UNCATEGORIZED_KEY)!.push(tool);
      } else {
        systemIds.forEach((sid) => {
          if (!groupMap.has(sid)) {
            groupMap.set(sid, []);
            systemOrder.push(sid);
          }
          groupMap.get(sid)!.push(tool);
        });
      }
    });
    const nameMap = props.systemNameMap || {};
    return systemOrder.map(key => ({
      groupKey: key,
      groupId: key === UNCATEGORIZED_KEY ? '-' : key,
      groupName: key === UNCATEGORIZED_KEY ? t('未分类') : (nameMap[key] || `系统 ${key}`),
      tools: groupMap.get(key) || [],
    }));
  };

  const buildGroups = (tools: ToolInfo[]): ToolGroup[] => {
    if (isCrossScene.value) {
      return buildSceneGroups(tools);
    }
    if (isCrossSystem.value) {
      return buildSystemGroups(tools);
    }
    return [];
  };

  // 跨场景/跨系统模式：按场景或系统分组（左侧）
  const filteredGroupedTools = computed(() => {
    const keyword = popoverSearchValue.value.trim().toLowerCase();
    const filtered = allToolsList.value.filter((tool) => {
      if (keyword && !tool.name.toLowerCase().includes(keyword)) return false;
      return true;
    });
    return buildGroups(filtered);
  });

  // 非跨场景模式：平铺列表（左侧）
  const filteredFlatTools = computed(() => {
    const keyword = popoverSearchValue.value.trim().toLowerCase();
    return allToolsList.value.filter((tool) => {
      if (keyword && !tool.name.toLowerCase().includes(keyword)) return false;
      return true;
    });
  });

  // 按标签分组的工具列表 - 已废弃，改为按场景分组

  // 右侧最近使用
  const filteredRecentTools = computed(() => {
    const keyword = popoverSearchValue.value.trim().toLowerCase();
    return recentToolsList.value.filter((tool) => {
      if (keyword && !tool.name.toLowerCase().includes(keyword)) return false;
      return true;
    });
  });

  // 右侧最近使用（按场景/系统分组）
  const filteredRecentGrouped = computed(() => buildGroups(filteredRecentTools.value));

  // 右侧我的收藏
  const filteredFavoriteTools = computed(() => {
    const keyword = popoverSearchValue.value.trim().toLowerCase();
    return favoriteToolsList.value.filter((tool) => {
      if (keyword && !tool.name.toLowerCase().includes(keyword)) return false;
      return true;
    });
  });

  // 右侧我的收藏（按场景/系统分组）
  const filteredFavoriteGrouped = computed(() => buildGroups(filteredFavoriteTools.value));

  const buildOverrideContext = (groupKey?: string): ToolDetailOverrideContext | undefined => {
    if (!groupKey || groupKey === '0' || groupKey === UNCATEGORIZED_KEY) {
      return undefined;
    }
    if (isCrossScene.value) {
      const sceneId = Number(groupKey);
      if (!Number.isNaN(sceneId) && sceneId > 0) {
        return { scene_id: sceneId };
      }
    }
    if (isCrossSystem.value) {
      return { system_id: groupKey };
    }
    return undefined;
  };

  const handleAddTool = (tool: ToolInfo, groupKey?: string) => {
    if (isToolOpened(tool.uid)) {
      emit('switchTool', tool);
    } else {
      emit('addTool', tool, buildOverrideContext(groupKey));
    }
    // 关闭 popover
    nextTick(() => {
      addPopoverRef.value?.hide?.();
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
  color: #3a84ff;
}

.tool-group-item.is-added .tool-group-item-name {
  color: #3a84ff;
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

.tool-opened-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-left: 4px;
  font-size: 14px;
  flex: 0 0 14px;
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
  background-color: #63656e;
  transition: background-color .15s;
  flex: 0 0 auto;
}

.right-tab-icon-clock {
  mask: url('@images/clock.svg') no-repeat center / contain;
}

.right-tab-icon-star {
  mask: url('@images/star.svg') no-repeat center / contain;
}

.right-tab-item:hover {
  color: #3a84ff;
}

.right-tab-item:hover .right-tab-icon {
  background-color: #3a84ff;
}

.right-tab-item.active {
  font-weight: 500;
  color: #3a84ff;
  border-bottom-color: #3a84ff;
}

.right-tab-item.active .right-tab-icon {
  background-color: #3a84ff;
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
