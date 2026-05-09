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
    ref="popoverRef"
    :arrow="false"
    :ext-cls="dark ? 'scene-system-selector-popover-dark' : ''"
    :is-show="isPopoverShow"
    placement="bottom-start"
    :theme="dark ? 'dark' : 'light'"
    trigger="click"
    :width="popoverWidth"
    @after-hidden="handlePopoverHidden"
    @after-show="handlePopoverShow">
    <div
      class="scene-system-selector"
      :class="{ 'is-active': isPopoverShow, 'is-dark': dark }"
      :style="{ width: typeof width === 'number' ? `${width}px` : width }">
      <div class="selector-content">
        <bk-tag
          v-if="selectedItem"
          class="type-tag"
          :class="[`type-${selectedItem.type}`]">
          {{ getTypeLabel(selectedItem.type) }}
        </bk-tag>
        <show-tooltips-text
          class="selector-text"
          :data="displayText" />
      </div>
      <audit-icon
        class="selector-arrow"
        :class="{ 'is-flip': isPopoverShow }"
        type="angle-line-down" />
    </div>
    <template #content>
      <div
        class="scene-system-dropdown"
        :class="{ 'is-dark': dark }">
        <!-- 审计场景分组 -->
        <div
          v-if="listScope.includes('scene') && (
            userRole.includes('scene_admin') || userRole.includes('scene_user') || userRole.includes('saas_admin')
          )"
          class="dropdown-group">
          <div class="group-title">
            {{ t('审计场景') }}
          </div>
          <div class="group-list">
            <div
              v-for="item in sceneList"
              :key="item.id"
              class="dropdown-item"
              :class="{ 'is-selected': isSelected(item) }"
              @click="handleSelect(item)">
              <bk-tag
                class="type-tag"
                :class="[`type-${item.type}`]">
                {{ getTypeLabel(item.type) }}
              </bk-tag>
              <show-tooltips-text
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }"
                :data="item.type !== 'aggregate' ? `${item.name}(${item.id})` : item.name" />
            </div>
          </div>
        </div>

        <!-- 接入系统分组 -->
        <div
          v-if="listScope.includes('system') &&( userRole.includes('system_admin') || userRole.includes('saas_admin'))"
          class="dropdown-group">
          <div class="group-title">
            {{ t('接入系统') }}
          </div>
          <div class="group-list">
            <div
              v-for="item in systemList"
              :key="item.id"
              class="dropdown-item"
              :class="{ 'is-selected': isSelected(item) }"
              @click="handleSelect(item)">
              <bk-tag
                class="type-tag"
                :class="[`type-${item.type}`]">
                {{ getTypeLabel(item.type) }}
              </bk-tag>
              <show-tooltips-text
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }"
                :data="item.type !== 'aggregate' ? `${item.name}(${item.id})` : item.name" />
            </div>
          </div>
        </div>
      </div>
    </template>
  </bk-popover>
</template>

<script setup lang="ts">
  import {
    computed,
    onMounted,
    onUnmounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import sceneManageService from '@service/scene-manage';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  import useRequest from '@/hooks/use-request';

  interface SelectorItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
  }

  interface Props {
    modelValue?: SelectorItem | null;
    width?: number | string;
    popoverWidth?: number;
    dark?: boolean;
    listScope?:  string[],
    systemPermission: 'edit_system' | 'view_system';
    scenePermission: 'manage_scene' | 'view_scene';
    isAllSystem?: boolean; // 是否展示全部接入系统
    isAllSecen?: boolean; // 是否展示全部审计场景
  }

  interface Emits {
    (e: 'update:modelValue', value: SelectorItem | null): void;
    (e: 'change', value: SelectorItem | null): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: null,
    width: 320,
    popoverWidth: 400,
    dark: false,
    listScope: () => ['scene', 'system'],
    isAllSecen: true,
    isAllSystem: true,
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();

  const userRole = JSON.parse(sessionStorage.getItem('userRole') || '["scene_admin"]') as string[];

  // ⚡ 立即缓存初始路由参数（同步），防止后续被 replaceSearchParams 覆写后丢失
  const initialRouteSceneId = route.query.scene_id as string;
  const initialRouteScopeId = route.query.scope_id as string;

  const popoverRef = ref();
  const isPopoverShow = ref(false);
  const selectedItem = ref<SelectorItem | null>(props.modelValue);

  //  审计场景列表
  const sceneList = ref<SelectorItem[]>([]);

  // 接入系统列表
  const systemList = ref<SelectorItem[]>([]);

  // 显示文本
  const displayText = computed(() => {
    if (!selectedItem.value) {
      return t('请选择');
    }
    const { name, id, type } = selectedItem.value;
    return (id && type !== 'aggregate') ? `${name}(${id})` : name;
  });

  // 获取类型标签文本
  const getTypeLabel = (type: string) => {
    const labelMap: Record<string, string> = {
      aggregate: t('聚合'),
      scene: t('场景'),
      system: t('系统'),
    };
    return labelMap[type] || type;
  };

  // 判断是否选中
  const isSelected = (item: SelectorItem) => {
    if (!selectedItem.value) return false;
    return selectedItem.value.id === item.id && selectedItem.value.type === item.type;
  };

  const STORAGE_KEY = 'scene-system-selector:selected';

  // 标记是否已执行过默认选中逻辑
  let hasInitializedSelection = false;

  /** 根据角色确定可用列表范围 */
  const getRoleScope = () => ({
    hasSceneAccess: userRole.includes('scene_admin') || userRole.includes('scene_user') || userRole.includes('saas_admin'),
    hasSystemAccess: userRole.includes('system_admin') || userRole.includes('saas_admin'),
  });

  /**
   * 基于角色的默认选中逻辑：
   * 1. 角色决定可见列表：scene_admin/scene_user→场景; system_admin→系统; saas_admin→两者
   * 2. URL有ID时在对应列表中匹配，找不到则默认选第一个非聚合项
   * 3. URL无ID时直接选对应列表第一个非聚合项
   */
  const trySelectFromRoute = () => {
    if (hasInitializedSelection || selectedItem.value) return;

    const { hasSceneAccess, hasSystemAccess } = getRoleScope();
    // 基于当前页面的 listScope 决定实际可用的匹配范围
    const showScene = props.listScope.includes('scene') && hasSceneAccess;
    const showSystem = props.listScope.includes('system') && hasSystemAccess;
    // URL 精确匹配需包含 aggregate 项（allSystem/allSecen 也是合法选择）
    const sceneItemsForMatch = showScene ? sceneList.value : [];
    const systemItemsForMatch = showSystem ? systemList.value : [];
    // 兜底选中只选具体项（不默认选聚合项）
    const sceneItems = sceneItemsForMatch.filter(item => item.type !== 'aggregate');
    const systemItems = systemItemsForMatch.filter(item => item.type !== 'aggregate');
    const urlMatchId = initialRouteSceneId || initialRouteScopeId;

    // 检查当前页面所需列表是否已加载完毕（仅检查 listScope 范围内的）
    if (showScene && sceneItems.length === 0) return;
    if (showSystem && systemItems.length === 0) return;

    let targetItem: SelectorItem | null = null;

    // ── 阶段2：URL中有ID时尝试精确匹配（包括聚合项 allSystem/allSecen）──
    if (urlMatchId) {
      if (showScene && !showSystem) {
        targetItem = sceneItemsForMatch.find(item => item.id === urlMatchId) || null;
      } else if (!showScene && showSystem) {
        targetItem = systemItemsForMatch.find(item => item.id === urlMatchId) || null;
      } else if (showScene && showSystem) {
        targetItem = sceneItemsForMatch.find(item => item.id === urlMatchId)
          || systemItemsForMatch.find(item => item.id === urlMatchId)
          || null;
      }
      if (!targetItem) {
        // URL中有scene_id但用户无权访问该场景 → 跳转到权限申请页
        console.log('未找到对应场景', { urlMatchId, role: userRole });
        router.replace({
          name: 'permissionsPage',
          query: { scene_id: urlMatchId },
        });
        return;
      }
    }

    // ── 阶段2.5：恢复用户上次的选择（跨页面记忆，需在当前页面可见范围内）──
    if (!targetItem) {
      try {
        const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
        if (saved && saved.id) {
          // 只在当前页面实际展示的列表中恢复（包括聚合项）
          const availableItems = [
            ...sceneItemsForMatch,
            ...systemItemsForMatch,
          ];
          targetItem = availableItems.find(item => item.id === saved.id && item.type === saved.type) || null;
        }
      } catch { /* ignore */ }
    }

    // ── 阶段3：URL无ID / 匹配失败 / 上次选择不可用时的兜底逻辑 ──
    if (!targetItem) {
      // 优先选第一个非聚合场景；场景列表为空时退而求其次选系统
      if (sceneItems.length > 0) {
        [targetItem] = sceneItems;
      } else if (systemItems.length > 0) {
        [targetItem] = systemItems;
      }
      // 仍找不到任何可选项 → 跳转到权限申请页
      if (!targetItem) {
        console.log('无可选场景或系统');
        router.replace({
          name: 'permissionsPage',
          query: urlMatchId ? { scene_id: urlMatchId } : {},
        });
        return;
      }
    }

    // 设置选中项
    hasInitializedSelection = true;
    selectedItem.value = targetItem;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(targetItem));
    emits('update:modelValue', targetItem);
    emits('change', targetItem);
    syncSceneIdToRoute(targetItem);
  };

  // 选择项目
  const handleSelect = (item: SelectorItem) => {
    selectedItem.value = item;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(item));
    emits('update:modelValue', item);
    emits('change', item);
    isPopoverShow.value = false;
    // 同步 scene_id 到路由参数
    syncSceneIdToRoute(item);
  };

  // 同步场景参数到路由 query 参数
  const syncSceneIdToRoute = (item: SelectorItem | null) => {
    const currentQuery = { ...route.query };
    if (!item || !item.id) {
      // 清空所有场景相关参数
      const newQuery = { ...currentQuery };
      delete newQuery.scene_id;
      delete newQuery.scope_id;
      delete newQuery.scope_type;
      router.replace({ query: newQuery });
      return;
    }
    if (item.type === 'scene') {
      // 具体场景 → scene_id=具体ID
      if (currentQuery.scene_id !== item.id || currentQuery.scope_id !== item.id) {
        router.replace({
          query: { ...currentQuery, scene_id: item.id, scope_id: item.id, scope_type: 'scene' },
        });
      }
    } else if (item.type === 'system') {
      // 具体系统 → scene_id=具体ID
      if (currentQuery.scene_id !== item.id || currentQuery.scope_id !== item.id) {
        router.replace({
          query: { ...currentQuery, scene_id: item.id, scope_id: item.id, scope_type: 'system' },
        });
      }
    } else if (item.type === 'aggregate') {
      // 聚合项
      if (item.id === 'allSecen') {
        if (currentQuery.scene_id !== 'allSecen' || currentQuery.scope_type !== 'cross_scene') {
          router.replace({
            query: { ...currentQuery, scene_id: 'allSecen', scope_id: '', scope_type: 'cross_scene' },
          });
        }
      } else if (item.id === 'allSystem') {
        if (currentQuery.scene_id !== 'allSystem' || currentQuery.scope_type !== 'cross_system') {
          router.replace({
            query: { ...currentQuery, scene_id: 'allSystem', scope_id: '', scope_type: 'cross_system' },
          });
        }
      }
    }
  };

  // 弹出层显示
  const handlePopoverShow = () => {
    isPopoverShow.value = true;
  };

  // 弹出层隐藏
  const handlePopoverHidden = () => {
    isPopoverShow.value = false;
  };

  // 获取系统列表
  const {
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    onSuccess: (data: any[]) => {
      const list = data
        .filter(item => item.permission && item.permission[props.systemPermission] === true)
        .map(item => ({
          id: item.system_id,
          name: item.name,
          type: 'system' as const,
        }));
      systemList.value = props.isAllSystem ? [{ id: 'allSystem', name: t('我的所有系统'), type: 'aggregate' }, ...list] : list;
      // 尝试从路由参数选中（system 类型需要系统列表就绪）
      trySelectFromRoute();
    },
  });
  // 获取场景列表
  const {
    run: fetchSceneAll,
  } = useRequest(sceneManageService.fetchSceneAll, {
    defaultValue: [],
    onSuccess: (data: any[]) => {
      const list = data
        .filter(item => item.permission && item.permission[props.scenePermission] === true)
        .map(item => ({
          id: String(item.scene_id),
          name: item.name,
          type: 'scene' as const,
        }));
      sceneList.value = props.isAllSecen ? [{ id: 'allSecen', name: t('我的所有场景'), type: 'aggregate' }, ...list] : list;
      // 尝试从路由参数选中（场景列表已就绪）
      trySelectFromRoute();
    },
  });
  // 监听外部值变化
  watch(() => props.modelValue, (newVal) => {
    selectedItem.value = newVal;
    // 外部设置选中项时也同步 URL
    if (newVal) {
      syncSceneIdToRoute(newVal);
    }
  });

  // ⚡ 持续守护：确保 URL 中始终包含正确的场景参数
  // （防止其他组件的路由跳转丢失 query 参数）
  watch(selectedItem, (newVal) => {
    if (!newVal || !newVal.id) return;
    const checkAndFixUrl = () => {
      const q = route.query;
      const needsFix = (
        (q.scene_id !== newVal.id)
        || (newVal.type === 'aggregate' && newVal.id === 'allSecen' && q.scope_type !== 'cross_scene')
        || (newVal.type === 'aggregate' && newVal.id === 'allSystem' && q.scope_type !== 'cross_system')
      );
      if (needsFix) {
        syncSceneIdToRoute(newVal);
      }
    };
    setTimeout(checkAndFixUrl, 100);
  });

  // ⚡ 路由级守护：当路由变化但丢失场景参数时自动恢复
  // （覆盖 router.replace/push 等操作丢失 query 的情况）
  watch(() => route.query, () => {
    const item = selectedItem.value;
    if (!item || !item.id) return;
    const q = route.query;
    const needsFix = (
      (q.scene_id !== item.id)
      || (item.type === 'aggregate' && item.id === 'allSecen' && q.scope_type !== 'cross_scene')
      || (item.type === 'aggregate' && item.id === 'allSystem' && q.scope_type !== 'cross_system')
    );
    if (needsFix) {
      setTimeout(() => syncSceneIdToRoute(item), 50);
    }
  });

  // 获取数据的方法（按角色按需请求）
  const fetchData = () => {
    const { hasSceneAccess, hasSystemAccess } = getRoleScope();
    setTimeout(() => {
      if (hasSystemAccess) {
        fetchSystemWithAction({
          action_ids: 'view_system,edit_system',
          audit_status__in: 'accessed',
          namespace: 'default',
          order_type: 'asc',
          sort_keys: 'name',
          with_favorite: false,
          with_system_status: false,
        });
      }
      if (hasSceneAccess) {
        fetchSceneAll({
          status: 'enabled',
        });
      }
    }, 0);
  };

  // 获取场景和系统列表的方法（暴露给子组件/外部调用）
  const getLists = () => ({
    sceneList: sceneList.value,
    systemList: systemList.value,
  });

  // 暴露方法和属性给父组件/子组件
  defineExpose({
    getLists,
    sceneList,
    systemList,
  });

  onMounted(() => {
    fetchData();
  });

  onUnmounted(() => {
    // 清理路由监听器（如果需要的话）
    // 通常不需要手动清理，因为router.afterEach返回的函数会在组件卸载时自动清理
  });
</script>

<style lang="postcss" scoped>
.scene-system-selector {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  padding: 0 10px;
  cursor: pointer;
  background: #f0f1f5;
  border-radius: 2px;
  transition: all .3s;

  &:hover {
    border-color: #3a84ff;
  }

  &.is-active {
    border-color: #3a84ff;
  }

  /* 深色主题 */
  &.is-dark {
    background: #2e3847;
    border: 1px solid #3c4558;

    &:hover {
      border-color: #4d5565;
    }

    &.is-active {
      border-color: #699df4;
    }

    .selector-content {
      .selector-text {
        color: #c4c6cc;
      }
    }

    .selector-arrow {
      color: #63656e;
    }
  }

  .selector-content {
    display: flex;
    flex: 1;
    align-items: center;
    overflow: hidden;

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

    .selector-text {
      flex: 1;
      overflow: hidden;
      font-size: 14px;
      color: #313238;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .selector-arrow {
    flex-shrink: 0;
    margin-left: 8px;
    font-size: 16px;
    color: #979ba5;
    transition: transform .3s;

    &.is-flip {
      transform: rotate(180deg);
    }
  }
}

.scene-system-dropdown {
  max-height: 400px;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #c4c6cc;
    border-radius: 2px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #979ba5;
  }

  /* 深色主题 */
  &.is-dark {
    background: #1a2233;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: #2e3847;
      border-radius: 2px;
    }

    &::-webkit-scrollbar-thumb:hover {
      background: #3c4558;
    }

    .dropdown-group {
      .group-title {
        color: #63656e;
      }

      .group-list {
        .dropdown-item {
          &:hover {
            background-color: #253047;
          }

          &.is-selected {
            background-color: #2a3a54;

            .item-name.is-highlight {
              color: #699df4;
            }
          }

          .item-name {
            color: #979ba5;

            &.is-highlight {
              color: #c4c6cc;
            }
          }

          .item-id {
            color: #63656e;
          }
        }
      }
    }
  }

  .dropdown-group {
    &:not(:last-child) {
      margin-bottom: 8px;
    }

    .group-title {
      padding: 8px 12px;
      font-size: 12px;
      color: #979ba5;
    }

    .group-list {
      .dropdown-item {
        display: flex;
        align-items: center;
        height: 36px;
        padding: 0 12px;
        cursor: pointer;
        transition: background-color .2s;

        &:hover {
          background-color: #f5f7fa;
        }

        &.is-selected {
          background-color: #e1ecff;

          .item-name.is-highlight {
            color: #3a84ff;
          }
        }

        .type-tag {
          flex-shrink: 0;
          height: 22px;
          padding: 0 6px;
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

        .item-name {
          font-size: 12px;
          color: #63656e;

          &.is-highlight {
            color: #313238;
          }
        }

        .item-id {
          margin-left: 4px;
          font-size: 12px;
          color: #979ba5;
        }
      }
    }
  }
}
</style>

<style lang="postcss">
/* 深色主题弹出层样式 */
.scene-system-selector-popover-dark.bk-popover.bk-pop2-content {
  background: #1a2233 !important;
  border: none !important;
  box-shadow: 0 3px 9px 0 rgb(0 0 0 / 50%) !important;
}
</style>
