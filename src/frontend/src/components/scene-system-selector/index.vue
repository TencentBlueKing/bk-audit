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
    trigger="manual"
    :width="popoverWidth || (typeof width === 'number' ? width : undefined)"
    @after-hidden="handlePopoverHidden"
    @after-show="handlePopoverShow">
    <div
      class="scene-system-selector"
      :class="{ 'is-active': isPopoverShow, 'is-dark': dark }"
      :style="{ width: typeof width === 'number' ? `${width}px` : width }"
      @click.stop="isPopoverShow = !isPopoverShow">
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
        :class="{ 'is-dark': dark }"
        @click.stop>
        <div class="group-search">
          <span class="search-prefix-wrap">
            <audit-icon
              class="search-prefix"
              type="search1" />
          </span>
          <bk-input
            v-model="sceneSearchKey"
            behavior="simplicity"
            :placeholder="t('请输入关键字搜索')"
            size="small" />
        </div>
        <!-- 审计场景分组 -->
        <div
          v-if="listScope.includes('scene') && (
            userRole.includes('scene_admin') || userRole.includes('scene_user') || userRole.includes('saas_admin')
          )"
          class="dropdown-group">
          <div
            v-show="filteredSceneList.length > 0"
            class="group-title">
            {{ t('审计场景') }}
          </div>

          <div class="group-list">
            <div
              v-for="item in filteredSceneList"
              :key="item.id"
              class="dropdown-item"
              :class="{
                'is-selected': isSelected(item),
                'is-locked': isSceneLocked(item),
              }"
              @click.stop="handleSelect(item)">
              <bk-tag
                class="type-tag"
                :class="[`type-${item.type}`]">
                {{ getTypeLabel(item.type) }}
              </bk-tag>
              <show-tooltips-text
                v-if="!isSceneLocked(item)"
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }"
                :data="getItemDisplayName(item)"
                placement="right" />
              <show-tooltips-text
                v-else
                v-cursor
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }"
                :data="getItemDisplayName(item)"
                placement="right" />
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
              v-for="item in filteredSystemList"
              :key="item.id"
              class="dropdown-item"
              :class="{ 'is-selected': isSelected(item) }"
              @click.stop="handleSelect(item)">
              <bk-tag
                class="type-tag"
                :class="[`type-${item.type}`]">
                {{ getTypeLabel(item.type) }}
              </bk-tag>
              <show-tooltips-text
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }"
                :data="item.type !== 'aggregate' ? `${item.name}(${item.id})` : item.name"
                placement="right" />
            </div>
          </div>
        </div>
      </div>
    </template>
  </bk-popover>
</template>

<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
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

  import useEventBus from '@hooks/use-event-bus';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  import useRequest from '@/hooks/use-request';
  import {
    buildSceneContextQueryFromSelection,
    clearRecentSceneSwitch,
    getQueryFromLocation,
    isRecentManualSceneSwitch,
    markSceneSelectorSwitched,
    SCENE_SELECTOR_STORAGE_KEY,
    setActiveSceneSelection,
    syncSceneContextToUrl,
  } from '@/utils/assist/scene-system-params';

  interface SelectorItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
    permission?: {
      manage_scene?: boolean;
      view_scene?: boolean;
      [key: string]: boolean | undefined;
    };
  }

  interface Props {
    modelValue?: SelectorItem | null;
    width?: number | string;
    popoverWidth?: number;
    dark?: boolean;
    listScope?:  string[],
    systemPermission: 'edit_system' | 'view_system' | 'edit_system,view_system';
    scenePermission: 'manage_scene' | 'view_scene' | 'manage_scene,view_scene';
    isAllSystem?: boolean; // 是否展示全部接入系统
    isAllSecen?: boolean; // 是否展示全部审计场景
    viewSceneBlock?: boolean; // 只有查看权限的场景是否上锁
  }

  interface Emits {
    (e: 'update:modelValue', value: SelectorItem | null): void;
    (e: 'change', value: SelectorItem | null): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: null,
    width: 320,
    popoverWidth: undefined as number | undefined,
    dark: false,
    listScope: () => ['scene', 'system'],
    isAllSecen: true,
    isAllSystem: true,
    viewSceneBlock: false,
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const { emit: sceneEmit, on: onSceneEvent, off: offSceneEvent } = useEventBus();

  const userRole = JSON.parse(sessionStorage.getItem('userRole') || '["scene_admin"]') as string[];

  // ⚡ 立即缓存初始路由参数（同步），防止后续被 replaceSearchParams 覆写后丢失
  const initialRouteSceneId = route.query.scene_id as string;
  const initialRouteScopeId = route.query.scope_id as string;

  const popoverRef = ref();
  const isPopoverShow = ref(false);
  const selectedItem = ref<SelectorItem | null>(props.modelValue);

  //  审计场景列表
  const sceneList = ref<SelectorItem[]>([]);

  // 场景搜索关键词
  const sceneSearchKey = ref('');

  // 过滤后的场景列表（支持按名称和ID搜索）
  const filteredSceneList = computed(() => {
    const keyword = sceneSearchKey.value.trim().toLowerCase();
    if (!keyword) return sceneList.value;
    return sceneList.value.filter(item => item.name.toLowerCase().includes(keyword)
      || item.id.toLowerCase().includes(keyword));
  });

  // 过滤后的系统列表（支持按名称和ID搜索）
  const filteredSystemList = computed(() => {
    const keyword = sceneSearchKey.value.trim().toLowerCase();
    if (!keyword) return systemList.value;
    return systemList.value.filter(item => item.name.toLowerCase().includes(keyword)
      || item.id.toLowerCase().includes(keyword));
  });

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

  const getItemDisplayName = (item: SelectorItem) => (
    item.type !== 'aggregate' ? `${item.name}(${item.id})` : item.name
  );

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

  // viewSceneBlock 开启时，仅查看权限（无管理权限）的场景禁止选择
  const isSceneLocked = (item: SelectorItem) => (
    props.viewSceneBlock
    && item.type === 'scene'
    && item.permission?.manage_scene === false
  );

  const checkPermission = (permission: Record<string, any> | undefined, permKey: string) => {
    if (!permission) return false;
    return permKey.split(',').some(key => permission[key.trim()] === true);
  };

  // 刚去掉管理员时 IAM 可能尚未同步，先本地覆盖再拉列表
  const lostManageSceneIds = new Set<string>();

  const STORAGE_KEY = SCENE_SELECTOR_STORAGE_KEY;

  /** 当前页是否属于场景配置模块（跳转申请页时默认选管理者） */
  const isSceneConfigRoute = () => (
    route.path.startsWith('/scene-config')
    || route.matched.some(record => record.meta?.navName === 'sceneConfiguration')
  );

  const buildPermissionsPageQuery = (sceneId?: string) => {
    const query: Record<string, string> = {
      role: isSceneConfigRoute() ? 'manager' : 'user',
    };
    if (sceneId) {
      query.scene_id = sceneId;
    }
    return query;
  };

  // 标记是否已执行过默认选中逻辑
  let hasInitializedSelection = false;

  /** 根据角色确定可用列表范围 */
  const getRoleScope = () => ({
    hasSceneAccess: userRole.includes('scene_admin') || userRole.includes('scene_user') || userRole.includes('saas_admin'),
    hasSystemAccess: userRole.includes('system_admin') || userRole.includes('saas_admin'),
  });

  // 从地址栏读取实时 query（列表页会用 history.replaceState 写条件，route.query 可能过期）
  const getCurrentQueryFromLocation = () => {
    const params = new URLSearchParams(window.location.search);
    const query: Record<string, string | string[]> = {};
    Array.from(new Set(params.keys())).forEach((key) => {
      const values = params.getAll(key);
      query[key] = values.length <= 1 ? (values[0] ?? '') : values;
    });
    return query;
  };

  const getLiveRouteQuery = () => ({
    ...route.query,
    ...getCurrentQueryFromLocation(),
  });

  const buildSceneQuery = buildSceneContextQueryFromSelection;

  const getSavedSelection = (): SelectorItem | null => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    } catch {
      return null;
    }
  };

  // 用户手动切换场景后，短暂忽略 route 守护，避免 stale URL 把选中项打回旧场景
  let suppressRouteResyncUntil = 0;
  const markUserSelection = () => {
    markSceneSelectorSwitched();
    suppressRouteResyncUntil = Date.now() + 800;
  };
  const shouldSuppressRouteResync = () => Date.now() < suppressRouteResyncUntil;

  /** 从当前路由或首屏缓存中读取场景 ID（深链优先） */
  const getUrlMatchId = () => {
    const q = getLiveRouteQuery();
    const liveId = (q.scene_id || q.scope_id) as string | undefined;
    if (liveId) return liveId;
    // 仅首屏未初始化前，用首屏缓存抵御列表 replaceSearchParams 冲掉参数
    if (!hasInitializedSelection) {
      return initialRouteSceneId || initialRouteScopeId || '';
    }
    return '';
  };

  /**
   * 在可见列表中按 ID 查找选中项
   */
  const findItemById = (
    matchId: string,
    sceneItemsForMatch: SelectorItem[],
    systemItemsForMatch: SelectorItem[],
    showScene: boolean,
    showSystem: boolean,
  ): SelectorItem | null => {
    if (!matchId) return null;
    if (showScene && !showSystem) {
      return sceneItemsForMatch.find(item => item.id === matchId) || null;
    }
    if (!showScene && showSystem) {
      return systemItemsForMatch.find(item => item.id === matchId) || null;
    }
    if (showScene && showSystem) {
      return sceneItemsForMatch.find(item => item.id === matchId)
        || systemItemsForMatch.find(item => item.id === matchId)
        || null;
    }
    return null;
  };

  /**
   * 应用选中项：同步 URL + localStorage，并通知外部
   */
  const applySelectedItem = (targetItem: SelectorItem, options?: { emitChange?: boolean }) => {
    const emitChange = options?.emitChange !== false;
    const isSame = selectedItem.value?.id === targetItem.id && selectedItem.value?.type === targetItem.type;
    setActiveSceneSelection(targetItem);
    hasInitializedSelection = true;
    selectedItem.value = targetItem;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(targetItem));
    syncSceneIdToRoute(targetItem);
    if (!isSame) {
      emits('update:modelValue', targetItem);
      if (emitChange) {
        emits('change', targetItem);
      }
    }
  };

  /**
   * 基于角色的默认选中逻辑：
   * 1. 角色决定可见列表：scene_admin/scene_user→场景; system_admin→系统; saas_admin→两者
   * 2. URL有ID时优先匹配（深链临时切换），并回写 localStorage
   * 3. URL无ID时恢复 localStorage / 兜底选第一项
   * 4. URL 指向无管理权限场景 → 跳转权限申请页（不自动改选第一个可管理场景）
   */
  const trySelectFromRoute = () => {
    const { hasSceneAccess, hasSystemAccess } = getRoleScope();
    // 基于当前页面的 listScope 决定实际可用的匹配范围
    const showScene = props.listScope.includes('scene') && hasSceneAccess;
    const showSystem = props.listScope.includes('system') && hasSystemAccess;
    // URL 精确匹配需包含 aggregate 项（allSystem/allSecen 也是合法选择）
    const sceneItemsForMatch = showScene ? sceneList.value : [];
    const systemItemsForMatch = showSystem ? systemList.value : [];
    // 兜底选中只选具体项（不默认选聚合项）；上锁场景不可作为默认项
    const sceneItems = sceneItemsForMatch.filter(item => item.type !== 'aggregate');
    const unlockedSceneItems = sceneItems.filter(item => !isSceneLocked(item));
    const systemItems = systemItemsForMatch.filter(item => item.type !== 'aggregate');
    const urlMatchId = getUrlMatchId();

    // 检查当前页面所需列表是否已加载完毕（仅检查 listScope 范围内的）
    if (showScene && sceneItems.length === 0) return;
    if (showSystem && systemItems.length === 0) return;

    // 用户刚切换场景：当前选中与 URL 不一致 → 以用户选择为准并回写 URL
    // 若当前选中项已失去管理权限（上锁），仍按 URL / 兜底逻辑重选
    if (
      hasInitializedSelection
      && selectedItem.value
      && urlMatchId
      && urlMatchId !== selectedItem.value.id
      && (shouldSuppressRouteResync() || isRecentManualSceneSwitch())
      && !isSceneLocked(selectedItem.value)
    ) {
      syncSceneIdToRoute(selectedItem.value);
      return;
    }

    if (shouldSuppressRouteResync()) {
      return;
    }

    // 已初始化且当前选中与 URL 一致 → 无需重复处理（上锁场景除外，需重新兜底）
    if (
      hasInitializedSelection
      && selectedItem.value
      && (!urlMatchId || selectedItem.value.id === urlMatchId)
      && !isSceneLocked(selectedItem.value)
    ) {
      return;
    }

    let targetItem: SelectorItem | null = null;

    // ── 阶段2：URL中有ID时尝试精确匹配（包括聚合项 allSystem/allSecen）──
    if (urlMatchId) {
      const matchedItem = findItemById(
        urlMatchId,
        sceneItemsForMatch,
        systemItemsForMatch,
        showScene,
        showSystem,
      );
      if (matchedItem && !isSceneLocked(matchedItem)) {
        targetItem = matchedItem;
      } else if (matchedItem && isSceneLocked(matchedItem)) {
        // URL 指向仅使用权限场景：应用内进入时兜底第一个可管理场景（外链由路由守卫跳转申请页）
        if (unlockedSceneItems.length > 0) {
          [targetItem] = unlockedSceneItems;
        } else {
          router.replace({
            name: 'userLandingPage',
            query: { scene_id: urlMatchId },
          });
          return;
        }
      } else {
        // URL 指向无权限场景 → 权限申请页
        router.replace({
          name: 'permissionsPage',
          query: buildPermissionsPageQuery(urlMatchId),
        });
        return;
      }
    }

    // ── 阶段2.5：恢复用户上次的选择（跨页面记忆，需在当前页面可见范围内）──
    if (!targetItem) {
      const saved = getSavedSelection();
      if (saved && saved.id) {
        // 只在当前页面实际展示的列表中恢复（包括聚合项）
        const availableItems = [
          ...sceneItemsForMatch,
          ...systemItemsForMatch,
        ];
        const savedItem = availableItems.find(item => item.id === saved.id && item.type === saved.type) || null;
        // 锁定场景 / 已不在列表中：不可恢复，走兜底第一个有权限场景
        targetItem = savedItem && !isSceneLocked(savedItem) ? savedItem : null;
      }
    }

    // ── 阶段3：URL无ID / 匹配失败 / 上次选择不可用时的兜底逻辑 ──
    if (!targetItem) {
      // 优先选第一个可管理的非聚合场景；场景列表为空时退而求其次选系统
      if (unlockedSceneItems.length > 0) {
        [targetItem] = unlockedSceneItems;
      } else if (systemItems.length > 0) {
        [targetItem] = systemItems;
      }
      // 仍找不到任何可选项（用户当前页面完全无可选资源）
      if (!targetItem) {
        const hasLockedScene = sceneItems.some(item => isSceneLocked(item));
        router.replace({
          // 仅有使用权限场景 → 引导页；完全无权限 → 权限申请页
          name: props.viewSceneBlock && hasLockedScene ? 'userLandingPage' : 'permissionsPage',
          query: props.viewSceneBlock && hasLockedScene ? {} : buildPermissionsPageQuery(),
        });
        return;
      }
    }

    applySelectedItem(targetItem);
  };

  // 选择项目
  const handleSelect = (item: SelectorItem) => {
    setActiveSceneSelection(item);
    markUserSelection();
    if (isSceneLocked(item)) {
      isPopoverShow.value = false;
      router.push({
        name: 'userLandingPage',
        query: {
          scene_id: item.id,
        },
      });
      return;
    }
    if ((!window.changeConfirm || window.changeConfirm === 'popover') && route.meta.changeSceneIsBackedList) {
      InfoBox({
        title: t('确认离开当前页？'),
        subTitle: t('离开将会导致未保存信息丢失'),
        cancelText: t('取消'),
        confirmText: t('确定'),
        headerAlign: 'center',
        contentAlign: 'center',
        footerAlign: 'center',
        class: 'change-confirm-info-box',
        onConfirm() {
          hasInitializedSelection = true;
          selectedItem.value = item;
          localStorage.setItem(STORAGE_KEY, JSON.stringify(item));
          syncSceneIdToRoute(item);
          isPopoverShow.value = false;
          emits('update:modelValue', item);
          emits('change', item);
          router.push({
            name: route.meta.ListPageName as string || 'strategyList',
            query: buildSceneQuery(item),
          });
        },
        onClose() {
        },
      });
    } else {
      hasInitializedSelection = true;
      selectedItem.value = item;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(item));
      // 先同步改地址栏，再通知列表刷新，避免列表按旧 scene_id 请求并把旧 ID 写回 URL
      syncSceneIdToRoute(item);
      emits('update:modelValue', item);
      emits('change', item);
      isPopoverShow.value = false;
    }
  };

  // 同步场景参数到地址栏（以 replaceState 为准，再让 vue-router 对齐地址栏，避免 route.query 旧值覆盖）
  const syncSceneIdToRoute = (item: SelectorItem | null) => {
    const nextQuery = buildSceneQuery(item);
    syncSceneContextToUrl(nextQuery);
    router.replace({ query: getQueryFromLocation() }).catch(() => {});
  };

  // 弹出层显示
  const handlePopoverShow = () => {
    isPopoverShow.value = true;
    sceneSearchKey.value = '';
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
        .filter(item => checkPermission(item.permission, props.systemPermission))
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
        .map((item) => {
          const sceneId = String(item.scene_id);
          const permission = { ...(item.permission || {}) };
          if (lostManageSceneIds.has(sceneId)) {
            permission.manage_scene = false;
            if (item.permission?.manage_scene === false) {
              lostManageSceneIds.delete(sceneId);
            }
          }
          return {
            id: sceneId,
            name: item.name,
            type: 'scene' as const,
            permission,
          };
        })
        .filter(item => checkPermission(item.permission, props.scenePermission));
      sceneList.value = props.isAllSecen ? [{ id: 'allSecen', name: t('我的所有场景'), type: 'aggregate' }, ...list] : list;
      // 存储纯场景列表（不含聚合项）供 layout.vue 聚合模式使用
      localStorage.setItem('scene-system-selector:sceneList', JSON.stringify(list));
      sceneEmit('scene-list-ready', list);
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
  // 若 URL 已明确指向其他场景，不回写（优先走 URL 临时切换）
  watch(selectedItem, (newVal) => {
    if (!newVal || !newVal.id) return;
    const q = getLiveRouteQuery();
    const needsFix = (
      q.scene_id !== newVal.id
      || (newVal.type === 'scene' && q.scope_id !== newVal.id)
      || (newVal.type === 'system' && q.scope_id !== newVal.id)
      || (newVal.type === 'aggregate' && newVal.id === 'allSecen' && q.scope_type !== 'cross_scene')
      || (newVal.type === 'aggregate' && newVal.id === 'allSystem' && q.scope_type !== 'cross_system')
    );
    if (needsFix) {
      syncSceneIdToRoute(newVal);
    }
  });

  // ⚡ 路由级守护：
  // - URL 有场景参数且与当前选中不一致 → 按 URL 临时切换（并回写 localStorage）
  // - URL 丢失场景参数 → 用当前选中项补回 query
  watch(() => route.query, () => {
    if (shouldSuppressRouteResync()) {
      return;
    }
    const liveQuery = getLiveRouteQuery();
    const urlMatchId = (liveQuery.scene_id || liveQuery.scope_id) as string | undefined;
    const item = selectedItem.value;

    if (urlMatchId && item?.id && urlMatchId !== item.id) {
      // 用户刚手动切换，URL 尚未跟上 → 回写 URL，不按旧 URL 改回选中项
      // 当前选中项已上锁时，允许按新 URL 重选
      if (isRecentManualSceneSwitch() && !isSceneLocked(item)) {
        syncSceneIdToRoute(item);
        return;
      }
      if (sceneList.value.length > 0 || systemList.value.length > 0) {
        trySelectFromRoute();
      }
      return;
    }

    if (urlMatchId) {
      if (item?.id === urlMatchId && item && !isSceneLocked(item)) return;
      // 列表未就绪时交由 trySelectFromRoute；已就绪则立即按 URL 切换
      if (sceneList.value.length > 0 || systemList.value.length > 0) {
        trySelectFromRoute();
      }
      return;
    }

    if (!item || !item.id) return;
    setTimeout(() => syncSceneIdToRoute(item), 50);
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

  const handleLostManage = (sceneId: unknown) => {
    const id = String(sceneId || '');
    if (!id) return;
    clearRecentSceneSwitch();
    suppressRouteResyncUntil = 0;
    lostManageSceneIds.add(id);
    sceneList.value = sceneList.value
      .map(item => (item.id === id
        ? { ...item, permission: { ...item.permission, manage_scene: false } }
        : item))
      .filter(item => item.type === 'aggregate' || checkPermission(item.permission, props.scenePermission));
    const plainList = sceneList.value.filter(item => item.type !== 'aggregate');
    localStorage.setItem('scene-system-selector:sceneList', JSON.stringify(plainList));
    sceneEmit('scene-list-ready', plainList);
    // 本地先标记失去管理权限，立即重选第一个仍可管理的场景
    trySelectFromRoute();
    fetchSceneAll({
      status: 'enabled',
    });
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

  // 点击外部区域关闭 popover
  const handleClickOutside = (e: Event) => {
    if (!isPopoverShow.value) return;
    // 检查是否点击在选择器触发区域内（如果是，由 @click.stop 处理切换，不在这里关闭）
    const triggerEl = popoverRef.value?.$el || popoverRef.value;
    if (triggerEl && triggerEl.contains(e.target as Node)) return;
    // 检查是否点击在 popover 弹出层内容区域内（teleport 到 body 的部分）
    const popoverContent = (e.target as HTMLElement)?.closest?.('.bk-popover.bk-pop2-content');
    if (popoverContent) return;
    isPopoverShow.value = false;
  };

  onMounted(() => {
    fetchData();
    onSceneEvent('scene-selector-lost-manage', handleLostManage);
    document.addEventListener('click', handleClickOutside, true);
  });

  onUnmounted(() => {
    offSceneEvent('scene-selector-lost-manage', handleLostManage);
    document.removeEventListener('click', handleClickOutside, true);
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
  font-size: 12px;

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

    .group-search {
      background: #1a2233;
    }

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
            background-color: #242d3f;
          }

          &.is-selected {
            background-color: rgba(58, 132, 255, .2);

            .item-name,
            .item-name.is-highlight {
              color: #fff;
            }
          }

          &.is-locked,
          &.is-locked.is-selected,
          &.is-locked:hover {
            cursor: not-allowed;
            background-color: transparent;

            .item-name,
            .item-name.is-highlight {
              color: #5a5f71;
            }

            .type-tag {
              opacity: 1;

              &.type-aggregate {
                color: rgb(255 255 255 / 45%);
                background-color: rgb(186 105 244 / 25%);
              }

              &.type-scene {
                color: rgb(255 255 255 / 45%);
                background-color: rgb(105 157 244 / 25%);
              }

              &.type-system {
                color: rgb(255 255 255 / 45%);
                background-color: rgb(248 182 79 / 25%);
              }
            }
          }

          .item-name {
            color: #979ba5;

            &.is-highlight {
              color: #dcdee5;
            }
          }

          .item-id {
            color: #63656e;
          }
        }
      }
    }
  }

  .group-search {
    position: sticky;
    top: 0;
    z-index: 1;
    display: flex;
    padding: 0 12px 8px;
    background: #fff;
    align-items: center;
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
        position: relative;
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
          height: 26px;
          padding: 0 8px;
          margin-right: 16px;
          font-size: 12px;
          line-height: 24px;
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
          flex: 1;
          min-width: 0;
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

        &.is-locked,
        &.is-locked.is-selected,
        &.is-locked:hover {
          cursor: not-allowed;
          background-color: transparent;

          .item-name,
          .item-name.is-highlight {
            color: #c4c6cc;
          }

          .type-tag {
            opacity: .4;
          }
        }
      }
    }
  }
}

.search-prefix-wrap {
  display: inline-block;
  align-items: center;
  justify-content: center;
  margin-top: 1px;

  .search-prefix {
    font-size: 14px;
    line-height: 1;
    color: #979ba5;
  }
}

</style>

<style lang="postcss">
/* 深色主题弹出层样式 */
.scene-system-selector-popover-dark.bk-popover.bk-pop2-content {
  background: #1a2232 !important;
  box-shadow: 0 3px 9px 0 rgb(0 0 0 / 50%) !important;

  /* 搜索框：深色主题，仅保留底部边框 */
  .group-search .bk-input {
    border: none !important;

    .bk-form-control,
    .bk-form-control *,
    .bk-form-control[style],
    .bk-form-content,
    input[type='text'],
    input[type='text'][style] {
      background-color: #1a2232 !important;
      background-image: none !important;
      border: none !important;
      border-bottom: 1px solid #4f5566 !important;
      outline: none !important;
      box-shadow: none !important;
      caret-color: #c4c6cc;
    }

    input {
      color: #979ba5;

      &::placeholder {
        color: #63656e;
      }
    }

    .input-icon-left,
    [class*='icon'],
    .bk-icon,
    /* 自定义 prefix 插槽中的图标：去除白底、对齐 */
    .input-prefix,
    .input-prefix *,
    .audit-icon {
      display: flex;
      color: #63656e;
      background: transparent !important;
      align-items: center;
      justify-content: center;
    }

    /* 去除前缀区域白底（组件内部 .bk-input--prefix 设置了 #fff !important） */
    .input-prefix,
    [class*='prefix'],
    .bk-input--prefix,
    .bk-input--prefix *,
    .input-left-icon,
    .input-left-icon * {
      background: transparent !important;
      background-color: transparent !important;
      background-image: none !important;
    }

    /* 自定义 prefix 包装：彻底覆盖白底 */

    &:hover {
      .input-prefix,
      .input-prefix *,
      .audit-icon,
      .bk-icon,
      .input-icon-left,
      [class*='icon'],
      [class*='prefix'],
      .input-left-icon,
      .bk-input--prefix,
      .bk-input--prefix *,
      .search-prefix-wrap,
      .search-prefix-wrap * {
        color: #63656e;
        background-color: #1a2232 !important;
        border-radius: 0;
      }
    }

    /* 聚焦状态：保持样式不变 */
    .group-search .bk-input.is-focused:not(.is-readonly):is-simplicity,
    .group-search .bk-input.is-focus,
    .group-search .bk-input.is-focused,
    .group-search .bk-input:focus-within,
    .group-search .bk-input:focus,
    .group-search .is-focus .bk-input {
      .bk-form-control,
      .bk-form-control *,
      .bk-form-control[style],
      .bk-form-content,
      input[type='text'],
      input[type='text'][style],
      input[type='text']:focus,
      input[type='text']:active {
        background-color: transparent !important;
        background-image: none !important;
        border: none !important;
        border-bottom: 1px solid #4f5566 !important;
        outline: none !important;
        box-shadow: none !important;
      }

      input {
        color: #979ba5;
      }
    }
  }
}
</style>
