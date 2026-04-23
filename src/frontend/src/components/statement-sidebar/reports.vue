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
  <div class="statement-sidebar">
    <!-- 场景系统选择器 -->
    <div class="scene-selector-wrapper">
      <scene-system-selector
        ref="sceneSystemSelectorRef"
        v-model="selectedScene"
        dark
        :list-scope="['system', 'scene']"
        :popover-width="280"
        scene-permission="view_scene"
        system-permission="view_system"
        width="100%"
        @change="(val: any) => handleSceneChange(val as SceneItem)" />
    </div>

    <!-- 我的收藏分组 -->
    <div
      v-if="favoriteItems.length > 0"
      class="side-group">
      <div
        class="side-group-header"
        @click="toggleFavoritesGroup">
        <img
          class="side-pentagram-title"
          src="@images/pentagram.svg">
        <span class="side-group-name">
          {{ t('我的收藏') }}
          <span class="favorite-count">{{ favoriteItems.length }}</span>

        </span>
        <audit-icon
          class="side-group-arrow"
          :class="{ expanded: isFavoritesExpanded }"
          type="angle-line-down" />
      </div>
      <div
        v-show="isFavoritesExpanded"
        class="side-group-children"
        @click="handleMenuClick('favorite')">
        <audit-menu-item
          v-for="child in favoriteItems"
          :key="child.id"
          class="favorite-item"
          :class="[(child.id === route.params.id && !clickFavorite) ? 'active-weak' :
            ((child.id === route.params.id && clickFavorite) ? 'active' : '')]"
          :index="child.id"
          @mouseenter="hoveredFavoriteItemId = child.id"
          @mouseleave="hoveredFavoriteItemId = null">
          <span class="side-child-dot" />
          <tool-tip-text
            :data="child.name"
            :line="1"
            style="display: inline-block;max-width: 130px; vertical-align: middle;"
            theme="light" />

          <audit-icon
            v-if="!collapsed && hoveredFavoriteItemId === child.id"
            class="side-pentagram-close"
            type="close"
            @click.stop="handleToggleFavorite(child, false)" />
          <img
            v-if="!collapsed && hoveredFavoriteItemId !== child.id"
            class="side-pentagram-fill"
            src="@images/pentagram-fill.svg"
            @click.stop="handleToggleFavorite(child, false)">
        </audit-menu-item>
      </div>
    </div>
    <!-- 分组列表 -->
    <div
      v-for="side in allSideRoutes"
      :key="side.id">
      <div
        v-if="sceneChangeItem.type === 'aggregate'"
        class="side-scene-header">
        <bk-tag
          class="type-tag"
          :class="[`type-${side.type}`]">
          {{ side.type === 'scene' ? t('场景') : t('系统') }}
        </bk-tag>
        <span class="side-scene-name">
          <tool-tip-text
            :data="`${side.name}(${side.id})`"
            :line="1"
            style="display: inline-block;max-width: 130px; vertical-align: middle;"
            theme="light" />
        </span>
      </div>
      <div
        v-for="group in side.children"
        :key="group.id"
        class="side-group">
        <!-- 分组标题 -->
        <div
          class="side-group-header"
          @click="toggleGroup(group.id)">
          <img
            class="side-pentagram-title"
            src="@images/folder.svg">
          <span class="side-group-name">{{ group.name }}</span>
          <audit-icon
            class="side-group-arrow"
            :class="{ expanded: expandedGroups.includes(group.id) }"
            type="angle-line-down" />
        </div>
        <!-- 子表项 -->
        <div
          v-show="expandedGroups.includes(group.id)"
          class="side-group-children"
          @click="handleMenuClick('group')">
          <audit-menu-item
            v-for="child in group.children"
            :key="child.id"
            class="menu-item-with-favorite"
            :class="[(child.id === route.params.id && clickFavorite) ? 'active-weak' :
              ((child.id === route.params.id && !clickFavorite) ? 'active' : '')]"
            :index="child.id"
            @mouseenter="hoveredItemId = child.id"
            @mouseleave="hoveredItemId = null">
            <span class="side-child-dot" />
            <tool-tip-text
              :data="child.name"
              :line="1"
              style="display: inline-block;max-width: 130px; vertical-align: middle;"
              theme="light" />
            <img
              v-if="!collapsed && child.favorite_created_at"
              v-show="hoveredItemId === child.id || child.id === route.params.id"
              class="side-pentagram-fill"
              src="@images/pentagram-fill.svg"
              @click.stop="handleToggleFavorite(child, false)">
            <img
              v-else-if="!collapsed"
              v-show="hoveredItemId === child.id || child.id === route.params.id"
              class="side-pentagram"
              src="@images/pentagram.svg"
              @click.stop="handleToggleFavorite(child, true)">
          </audit-menu-item>
        </div>
      </div>
      <!-- 暂无数据 -->
      <div
        v-if="showEmpty"
        class="side-empty">
        {{ t('暂无数据') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import PanelModelService from '@service/report-config';

  import useEventBus from '@hooks/use-event-bus';
  import useRequest from '@hooks/use-request';

  import AuditMenuItem from '@components/audit-menu/item.vue';
  import SceneSystemSelector from '@components/scene-system-selector/index.vue';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  interface MenuDataType {
    id: string;
    name: string;
    group_ids: number[];
    priority_index?: number;
    favorite_created_at?: string | null;
  }

  interface SideRouteItem {
    id: number;
    name: string;
    priority_index: number;
    scene_id?: number;
    children: MenuDataType[];
  }

  interface SceneItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
  }

  interface Props {
    menuData: MenuDataType[];
  }

  const props = withDefaults(
    defineProps<Props>(),
    {
      menuData: () => [],
    },
  );

  const { emit } = useEventBus();
  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const sceneChangeItem = ref();
  const sceneSystemSelectorRef = ref();
  // 场景选择器
  const selectedScene = ref<SceneItem | null>();
  const sceneSystemSelectorList = ref<SceneSystemSelectorLists>({} as SceneSystemSelectorLists);
  // 场景切换
  const handleSceneChange = (val: SceneItem) => {
    sceneSystemSelectorList.value = sceneSystemSelectorRef.value.getLists();
    sceneChangeItem.value = val;

    emit('refresh-menu');
    fetchPanelPreference();
    fetchGroups({
      scope_id: getSceneSystemParams().scope_id,
      scope_type: getSceneSystemParams().scope_type,
      // 标记为场景切换，成功后自动选中第一项
      isSceneChange: true,
    });
  };

  // 场景切换后默认选中第一个子菜单项
  const navigateToFirstChild = () => {
    const firstScene = allSideRoutes.value[0];
    if (firstScene?.children?.length > 0) {
      const firstGroup = firstScene.children[0];
      if (firstGroup?.children?.length > 0) {
        const firstChild = firstGroup.children[0];
        router.replace({ params: { id: firstChild.id } });
      }
    }
  };

  // 侧边栏宽度阈值，小于此值认为是收起状态
  const COLLAPSED_WIDTH_THRESHOLD = 100;
  // 侧边栏宽度
  const sidebarWidth = ref(0);
  // 侧边栏是否收起（根据宽度判断）
  const collapsed = computed(() => sidebarWidth.value < COLLAPSED_WIDTH_THRESHOLD);

  // ResizeObserver 实例
  let resizeObserver: ResizeObserver | null = null;

  // 监听侧边栏宽度变化
  const initResizeObserver = () => {
    const sideElement = document.querySelector('.audit-navigation-side');
    if (sideElement) {
      resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          sidebarWidth.value = entry.contentRect.width;
        }
      });
      resizeObserver.observe(sideElement);
      // 初始化宽度
      sidebarWidth.value = sideElement.clientWidth;
    }
  };

  const clickFavorite = ref(false);
  // 鼠标悬停的菜单项ID
  const hoveredItemId = ref<string | null>(null);
  // 鼠标悬停的收藏菜单项ID
  const hoveredFavoriteItemId = ref<string | null>(null);

  // 侧边路由数组变量，与reportGroups类型相同
  const sideRoutes = ref<SideRouteItem[]>([]);

  // 是否显示暂无数据
  const showEmpty = computed(() => sideRoutes.value.length === 0 && favoriteItems.value.length === 0);

  // 展开的分组ID列表
  const expandedGroups = ref<number[]>([]);

  // 我的收藏分组是否展开
  const isFavoritesExpanded = ref(true);

  // 获取收藏的菜单项
  const favoriteItems = computed(() => props.menuData.filter(item => item.favorite_created_at !== null));
  const handleMenuClick = (type: 'favorite' | 'group') => {
    clickFavorite.value = type === 'favorite';
  };
  // 切换分组展开/收起
  const toggleGroup = (groupId: number) => {
    const index = expandedGroups.value.indexOf(groupId);
    if (index > -1) {
      expandedGroups.value.splice(index, 1);
    } else {
      expandedGroups.value.push(groupId);
    }
    // 保存用户偏好
    savePanelPreference();
  };

  // 切换我的收藏展开/收起
  const toggleFavoritesGroup = () => {
    isFavoritesExpanded.value = !isFavoritesExpanded.value;
    // 保存用户偏好
    savePanelPreference();
  };

  // 收藏/取消收藏处理
  const {
    run: updateFavorite,
  } = useRequest(PanelModelService.updateFavorite, {
    defaultValue: {},
    onSuccess: () => {
      emit('refresh-menu');
    },
  });

  const handleToggleFavorite = (item: MenuDataType, isFavorite: boolean) => {
    updateFavorite({
      panel_id: item.id,
      favorite: isFavorite,
    });
  };

  // 用户偏好配置
  interface PanelPreference {
    expandedGroupIds?: number[];
    isFavoritesExpanded?: boolean;
  }
  const userPreference = ref<PanelPreference>({});

  // 获取用户偏好
  const {
    run: fetchPanelPreference,
  } = useRequest(PanelModelService.fetchPanelPreference, {
    defaultValue: null,
    onSuccess: (data: { config: string } | null) => {
      if (data && data.config) {
        try {
          userPreference.value = JSON.parse(data.config);
        } catch (e) {
          userPreference.value = {};
        }
      } else {
        // 返回空对象，默认展开全部
        userPreference.value = {};
      }
      // 获取用户偏好后，再获取分组数据
      fetchGroups({
        scope_id: getSceneSystemParams().scope_id,
        scope_type: getSceneSystemParams().scope_type,
      });
    },
  });

  // 更新用户偏好
  const {
    run: updatePanelPreference,
  } = useRequest(PanelModelService.updatePanelPreference, {
    defaultValue: {},
  });

  // 保存用户偏好到服务器
  const savePanelPreference = () => {
    const preference: PanelPreference = {
      expandedGroupIds: expandedGroups.value,
      isFavoritesExpanded: isFavoritesExpanded.value,
    };
    updatePanelPreference({
      config: JSON.stringify(preference),
    });
  };
  // sceneSystemSelector 返回的列表数据结构
  interface SceneSystemSelectorLists {
    sceneList: SceneItem[];
    systemList: SceneItem[];
  }
  const allSideRoutes = ref<Array<{
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
    scene_id: string;
    children: SideRouteItem[];
  }>>([]);
  // 获取分组
  const groups = ref<Array<{ id: number; name: string; priority_index: number }>>([]);
  const {
    run: fetchGroups,
  } = useRequest(PanelModelService.fetchGroups, {
    defaultValue: [],
    onSuccess: (
      data: Array<{ id: number; name: string; priority_index: number; scene_id?: number }>,
      params?: Record<string, unknown>,
    ) => {
      groups.value = data;
      sideRoutes.value =  data.map(item => ({
        scene_id: item.scene_id,
        id: item.id,
        name: item.name,
        priority_index: item.priority_index,
        children: props.menuData
          .filter(menuItem => Array.isArray(menuItem.group_ids)
            && menuItem.group_ids.map(String).includes(String(item.id)))
          .sort((a, b) => (b.priority_index ?? 0) - (a.priority_index ?? 0)),
      }))
        .sort((a, b) => b.priority_index - a.priority_index)
        .filter(group => group.children.length > 0);

      if (sceneChangeItem.value.type === 'aggregate') {
        const selectType = sceneChangeItem.value.id === 'allSecen' ? sceneSystemSelectorList.value.sceneList.filter(i => i.id !== 'allSecen')
          : sceneSystemSelectorList.value.systemList.filter(i => i.id !== 'allSystem');
        allSideRoutes.value = selectType.map((scene: SceneItem) => {
          const children = sideRoutes.value.filter(side => side.scene_id === Number(scene.id));
          return {
            id: scene.id,
            name: scene.name,
            type: scene.type,
            scene_id: scene.id,
            children,
          } as { id: string; name: string; type: 'aggregate' | 'scene' | 'system'; scene_id: string; children: SideRouteItem[] };
        }).filter(i => i.children.length > 0);
      } else {
        allSideRoutes.value = [{
          scene_id: sceneChangeItem.value.id,
          id: sceneChangeItem.value.id,
          name: sceneChangeItem.value.name,
          type: sceneChangeItem.value.type,
          children: sideRoutes.value,
        } as { id: string; name: string; type: 'aggregate' | 'scene' | 'system'; scene_id: string; children: SideRouteItem[] }].filter(i => i.children.length > 0);
      }
      // 场景切换后默认选中第一个子菜单项
      if (params?.isSceneChange) {
        navigateToFirstChild();
      }

      // 根据用户偏好设置展开的分组
      // 注意：expandedGroupIds 为空数组表示用户主动全部收起，应保持收起状态
      // expandedGroupIds 为 undefined 表示没有用户偏好，应默认展开所有分组
      if (userPreference.value.expandedGroupIds !== undefined) {
        expandedGroups.value = userPreference.value.expandedGroupIds;
      } else {
        // 没有用户偏好，默认展开所有分组
        expandedGroups.value = sideRoutes.value.map(g => g.id);
      }
      // 恢复我的收藏展开状态
      if (userPreference.value.isFavoritesExpanded !== undefined) {
        isFavoritesExpanded.value = userPreference.value.isFavoritesExpanded;
      }
    },
  });

  onMounted(() => {
    // 初始化侧边栏宽度监听
    initResizeObserver();
    // 组件挂载时先获取用户偏好，再获取分组数据
    fetchPanelPreference();
  });

  onBeforeUnmount(() => {
    // 清理 ResizeObserver
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
  });

</script>

<style lang="postcss" scoped>
  .statement-sidebar {
    width: 100%;
  }

  .scene-selector-wrapper {
    width: 90%;
    margin: 10px auto 16px;
  }

  .side-group {
    margin-bottom: 2px;
  }

  .side-group-header {
    display: flex;
    align-items: center;
    height: 40px;
    padding: 0 18px;
    font-size: 14px;
    color: #acb9d1;
    cursor: pointer;

    &:hover {
      background: #253047;
    }
  }

  .side-pentagram {
    position: absolute;
    top: 50%;
    right: 10px;
    width: 16px;
    height: 16px;
    cursor: pointer;
    transform: translateY(-50%);
  }

  .side-pentagram-title {
    width: 14px;
    height: 14px;
    margin-right: 10px;
  }

  .side-pentagram-close {
    position: absolute;
    top: 50%;
    right: -10px;
    width: 16px;
    height: 16px;
    cursor: pointer;
    transform: translateY(-50%);
  }

  .side-pentagram-fill {
    position: absolute;
    top: 50%;
    right: 10px;
    width: 16px;
    height: 16px;
    cursor: pointer;
    transform: translateY(-50%);
    transition: all .2s ease;
  }

  .favorite-count {
    position: relative;
    display: inline-block;
    padding: 0 8px;
    margin-left: 8px;
    font-size: 12px;
    color: #c4c6cc;
    background-color: #474c5a;
    border-radius: 50%;
  }

  .side-group-folder-icon {
    margin-right: 10px;
    font-size: 16px;
    color: #b0bdd5;
  }

  .side-group-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .side-group-arrow {
    font-size: 12px;
    color: #acb9d1;
    transition: transform .2s ease;

    &.expanded {
      transform: rotate(0deg);
    }

    &:not(.expanded) {
      transform: rotate(-90deg);
    }
  }

  .side-group-children {
    :deep(.audit-menu-item) {
      position: relative;
      padding-left: 36px;
    }
  }

  .favorite-item {
    :deep(.audit-menu-item-content) {
      display: flex;
      align-items: center;
      width: 100%;
    }
  }

  .menu-item-with-favorite {
    :deep(.audit-menu-item-content) {
      display: flex;
      align-items: center;
      width: 100%;
    }
  }

  .side-child-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    margin-right: 12px;
    background: #505562;
    border-radius: 50%;
    flex-shrink: 0;
  }

  :deep(.audit-menu-item.active) {
    .side-child-dot {
      background: #fff;
    }
  }

  .side-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80px;
    font-size: 12px;
    color: #63656e;
  }

  .side-scene-header {
    display: flex;
    padding: 10px 18px;
    font-size: 13px;
    border-top: 2px solid #39404e;
    align-items: center;
  }

  .side-scene-name {
    overflow: hidden;
    color: #d3d9e4;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .type-tag {
    flex-shrink: 0;
    height: 22px;
    padding: 0 8px;
    margin-right: 8px;
    font-size: 12px;
    line-height: 20px;
    color: #fff;
    border: none;
    border-radius: 2px;

    &.type-aggregate {
      background-color: #ba69f4;
    }

    &.type-scene {
      background-color: #699df4;
    }

    &.type-system {
      background-color: #f8b64f;
    }
  }
</style>
