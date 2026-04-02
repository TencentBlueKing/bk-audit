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
        </span>
        <span class="favorite-count">{{ favoriteItems.length }}</span>
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
            v-if="hoveredFavoriteItemId === child.id"
            class="side-pentagram-close"
            type="close"
            @click.stop="handleToggleFavorite(child, false)" />
          <img
            v-if="hoveredFavoriteItemId !== child.id"
            class="side-pentagram-fill"
            src="@images/pentagram-fill.svg"
            @click.stop="handleToggleFavorite(child, false)">
        </audit-menu-item>
      </div>
    </div>
    <!-- 分组列表 -->
    <div
      v-for="group in sideRoutes"
      :key="group.id"
      class="side-group">
      <!-- 分组标题 -->
      <div
        class="side-group-header"
        @click="toggleGroup(group.id)">
        <audit-icon
          class="side-group-folder-icon"
          type="baobiao" />
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
          <!-- {{ child.name }} -->
          <tool-tip-text
            :data="child.name"
            :line="1"
            style="display: inline-block;max-width: 130px; vertical-align: middle;"
            theme="light" />
          <img
            v-if="child.is_favorite"
            v-show="hoveredItemId === child.id || child.id === route.params.id"
            class="side-pentagram-fill"
            src="@images/pentagram-fill.svg"
            @click.stop="handleToggleFavorite(child, false)">
          <img
            v-else
            v-show="hoveredItemId === child.id || child.id === route.params.id"
            class="side-pentagram"
            src="@images/pentagram.svg"
            @click.stop="handleToggleFavorite(child, true)">
        </audit-menu-item>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import PanelModelService from '@service/report-config';

  import useEventBus from '@hooks/use-event-bus';
  import useRequest from '@hooks/use-request';

  import AuditMenuItem from '@components/audit-menu/item.vue';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';

  interface MenuDataType {
    id: string;
    name: string;
    group_id?: number;
    priority_index?: number;
    is_favorite?: boolean;
  }

  interface SideRouteItem {
    id: number;
    name: string;
    priority_index: number;
    children: MenuDataType[];
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

  const clickFavorite = ref(false);
  // 鼠标悬停的菜单项ID
  const hoveredItemId = ref<string | null>(null);
  // 鼠标悬停的收藏菜单项ID
  const hoveredFavoriteItemId = ref<string | null>(null);

  // 侧边路由数组变量，与reportGroups类型相同
  const sideRoutes = ref<SideRouteItem[]>([]);

  // 展开的分组ID列表
  const expandedGroups = ref<number[]>([]);

  // 我的收藏分组是否展开
  const isFavoritesExpanded = ref(true);

  // 获取收藏的菜单项
  const favoriteItems = computed(() => props.menuData.filter(item => item.is_favorite));
  const handleMenuClick = (type: 'favorite' | 'group') => {
    console.log('Menu clicked:', type);
    clickFavorite.value = type === 'favorite';
    console.log(' clickFavorite',  clickFavorite.value);
  };
  // 切换分组展开/收起
  const toggleGroup = (groupId: number) => {
    const index = expandedGroups.value.indexOf(groupId);
    if (index > -1) {
      expandedGroups.value.splice(index, 1);
    } else {
      expandedGroups.value.push(groupId);
    }
  };

  // 切换我的收藏展开/收起
  const toggleFavoritesGroup = () => {
    isFavoritesExpanded.value = !isFavoritesExpanded.value;
  };

  // 收藏/取消收藏处理
  const {
    run: updateFavorite,
  } = useRequest(PanelModelService.updateFavorite, {
    defaultValue: {},
    onSuccess: () => {
      console.log('收藏/取消收藏成功，触发刷新菜单');
      emit('refresh-menu');
    },
  });

  const handleToggleFavorite = (item: MenuDataType, isFavorite: boolean) => {
    updateFavorite({
      panel_id: item.id,
      is_favorite: isFavorite,
    });
  };

  // 获取分组
  const groups = ref<Array<{ id: number; name: string; priority_index: number }>>([]);
  const {
    run: fetchGroups,
  } = useRequest(PanelModelService.fetchGroups, {
    defaultValue: [],
    onSuccess: (data: Array<{ id: number; name: string; priority_index: number }>) => {
      console.log('获取分组列表成功:', data);
      groups.value = data;
      console.log('menuData.>>', props.menuData);
      sideRoutes.value =  data.map(item => ({
        id: item.id,
        name: item.name,
        priority_index: item.priority_index,
        children: props.menuData
          .filter(menuItem => menuItem.group_id === item.id)
          .sort((a, b) => (b.priority_index ?? 0) - (a.priority_index ?? 0)),
      }))
        .sort((a, b) => b.priority_index - a.priority_index);
      // 默认展开所有分组
      expandedGroups.value = sideRoutes.value.map(g => g.id);
      console.log('sideRoutes.>>', sideRoutes.value);
    },
  });

  onMounted(() => {
    // 组件挂载时获取分组数据
    fetchGroups({
      page: 1,
      page_size: 10000,
    });
  });

  // 监听menuData变化，重新处理分组
  watch(() => props.menuData, (newMenuData) => {
    console.log('menuData 变化，重新处理分组:', newMenuData);
    if (newMenuData && newMenuData.length > 0) {
      fetchGroups({
        page: 1,
        page_size: 10000,
      });
    }
  });
</script>

<style lang="postcss" scoped>
  .statement-sidebar {
    width: 100%;
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
    margin-right: 8px;
    font-size: 12px;
    color: #b0bdd5;
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
</style>
