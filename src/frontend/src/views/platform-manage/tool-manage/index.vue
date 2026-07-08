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
  <skeleton-loading
    fullscreen
    :loading="isLoading"
    name="storageList">
    <div class="report-config">
      <!-- 头部操作区 -->
      <div class="report-config-header">
        <div class="header-left">
          <bk-button
            class="mr8"
            theme="primary"
            @click="handleCreateReport">
            <audit-icon
              class="mr8"
              type="add" />
            {{ t('新建工具') }}
          </bk-button>
        </div>
        <div class="header-right tool-manage-search-area">
          <bk-radio-group
            v-model="statusFilter"
            class="status-filter mr16"
            type="capsule"
            @change="handleStatusFilterChange">
            <bk-radio-button label="all">
              {{ t('全部') }}
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.all }}
              </bk-tag>
            </bk-radio-button>
            <bk-radio-button label="published">
              <audit-icon
                class="mr4"
                svg
                type="normal" />
              {{ t('已上架') }}
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.published }}
              </bk-tag>
            </bk-radio-button>
            <bk-radio-button label="unpublished">
              <audit-icon
                class="mr4"
                svg
                type="unknown" />
              {{ t('未上架') }}
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.unpublished }}
              </bk-tag>
            </bk-radio-button>
          </bk-radio-group>

          <bk-search-select
            v-model="searchValue"
            class="search-input"
            clearable
            :data="searchSelectData"
            :defaut-using-item="{ inputHtml: t('请选择') }"
            :get-menu-list="getMenuList"
            :placeholder="t('搜索工具名称、工具说明、工具类型、可见范围、更新人')"
            unique-select
            value-split-code=","
            @update:model-value="handleSearchValueUpdate" />
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="report-config-content">
        <tool-list-table
          ref="toolListRef"
          :scene-name-map="sceneNameMap"
          :scene-options="visibilitySceneOptions"
          :search-params="searchModel"
          :strategy-list="strategyList"
          :system-name-map="systemNameMap"
          :system-options="visibilitySystemOptions"
          @clear-search="handleClearSearch"
          @delete="handleDelete"
          @edit="handleEdit"
          @edit-visibility="handleEditVisibility"
          @preview="handlePreview"
          @request-success="handleRequestSuccess"
          @toggle-status="handleToggleStatus" />
      </div>
    </div>
  </skeleton-loading>

  <!-- 工具预览抽屉 -->
  <tool-preview-drawer
    ref="previewDrawerRef"
    v-model:is-show="isPreviewShow"
    :all-tools-data="allToolsData"
    :tags-enums="tagsEnums" />

  <!-- 确认操作弹窗（删除/上架/下架） -->
  <confirm-action-dialog
    ref="confirmDialogRef"
    :action-type="confirmActionType"
    :target="confirmTarget"
    @success="handleActionSuccess" />

  <!-- 修改可见范围弹窗 -->
  <edit-visibility-dialog
    v-model:is-show="isEditVisibilityShow"
    :tags-enums="tagsEnums"
    :target="editVisibilityTarget"
    @success="handleVisibilityEditSuccess" />
</template>

<script setup lang='ts'>
  import { watch, onMounted, onUnmounted, reactive, ref, computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';
  import tippy, { type Instance } from 'tippy.js';

  import StrategyManageService from '@service/strategy-manage';
  import ToolManageService from '@service/tool-manage';
  import MetaManageService from '@service/meta-manage';
  import SceneManageService from '@service/scene-manage';

  import ToolInfo from '@model/tool/tool-info';

  import useEventBus from '@hooks/use-event-bus';
  import useRequest from '@hooks/use-request';

  import ConfirmActionDialog from './components/confirm-action-dialog.vue';
  import EditVisibilityDialog from './components/edit-visibility-dialog.vue';
  import ToolListTable from './components/tool-list-table.vue';
  import ToolPreviewDrawer from './components/tool-preview-drawer.vue';
  import { buildVisibilitySearchParams } from './create-tool/submit-payload';

  type ActionType = 'delete' | 'enable' | 'disable';

  interface SearchKey {
    id: string;
    name: string;
    values: Array<{ id: string; name: string }>;
  }

  interface SearchSelectItem {
    id: string;
    name: string;
    placeholder?: string;
    multiple?: boolean;
    async?: boolean;
    children?: Array<{ id: string; name: string; disabled?: boolean }>;
  }

  interface TagItem {
    tag_id: string;
    tag_name: string;
  }

  interface ToolItem {
    id?: string;
    uid: string;
    name: string;
    status: 'published' | '' | 'unpublished';
    tool_type?: string;
    version?: number;
    tags?: string[];
    visibility?: {
      binding_type: string;
      visibility_type: string;
      scene_ids: Array<number | string>;
      system_ids: Array<number | string>;
    };
    updated_at?: string;
    created_at?: string;
    description?: string;
    area?: string;
    strategies?: number[];
  }

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const isLoading = ref(true);
  const searchValue = ref<SearchKey[]>([]);

  const visibilitySceneOptions = ref<Array<{ id: number; name: string }>>([]);
  const visibilitySystemOptions = ref<Array<{ id: number; system_id?: string; name: string }>>([]);

  const sceneNameMap = computed(() => {
    const map: Record<string, string> = {};
    visibilitySceneOptions.value.forEach((scene) => {
      map[String(scene.id)] = scene.name;
    });
    return map;
  });

  const systemNameMap = computed(() => {
    const map: Record<string, string> = {};
    visibilitySystemOptions.value.forEach((system) => {
      map[String(system.id)] = system.name;
      if (system.system_id) {
        map[String(system.system_id)] = system.name;
      }
    });
    return map;
  });

  const getVisibilityOptionName = (id: string): string => {
    if (id === 'all_visible') return t('全部可见');
    if (id === 'all_scenes') return t('全部场景');
    if (id === 'all_systems') return t('全部系统');
    if (id.startsWith('scene_')) {
      const rawId = id.replace('scene_', '');
      return sceneNameMap.value[rawId]
        || visibilitySceneOptions.value.find(scene => String(scene.id) === rawId)?.name
        || rawId;
    }
    if (id.startsWith('system_')) {
      const rawId = id.replace('system_', '');
      return systemNameMap.value[rawId]
        || visibilitySystemOptions.value.find(system => String(system.id) === rawId || system.system_id === rawId)?.name
        || rawId;
    }
    return id;
  };

  const normalizeVisibilitySelectedIds = (selectedIds: string[]): string[] => {
    if (selectedIds.includes('all_visible')) {
      return ['all_visible'];
    }

    let ids = [...selectedIds].filter(id => !id.startsWith('__group_'));

    if (ids.includes('all_scenes')) {
      ids = ids.filter(id => !id.startsWith('scene_'));
    }

    if (ids.includes('all_systems')) {
      ids = ids.filter(id => !id.startsWith('system_'));
    }

    return ids;
  };

  const buildVisibilityChildren = () => [
    { id: 'all_visible', name: t('全部可见') },
    { id: '__group_scene__', name: t('场景列表'), disabled: true },
    { id: 'all_scenes', name: t('全部场景') },
    ...visibilitySceneOptions.value.map(scene => ({
      id: `scene_${scene.id}`,
      name: scene.name,
    })),
    { id: '__group_system__', name: t('系统列表'), disabled: true },
    { id: 'all_systems', name: t('全部系统') },
    ...visibilitySystemOptions.value.map(system => ({
      id: `system_${system.id}`,
      name: system.name,
    })),
  ];

  const filterVisibilityChildren = (keyword: string) => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    if (!normalizedKeyword) {
      return buildVisibilityChildren();
    }

    const result: Array<{ id: string; name: string; disabled?: boolean }> = [];
    const matchName = (name: string) => name.toLowerCase()
      .includes(normalizedKeyword);

    if (matchName(t('全部可见'))) {
      result.push({ id: 'all_visible', name: t('全部可见') });
    }

    const matchingScenes = visibilitySceneOptions.value.filter(scene => matchName(scene.name));
    const showAllScenes = matchName(t('全部场景'));

    if (showAllScenes || matchingScenes.length > 0) {
      result.push({ id: '__group_scene__', name: t('场景列表'), disabled: true });
      if (showAllScenes) {
        result.push({ id: 'all_scenes', name: t('全部场景') });
      }
      matchingScenes.forEach((scene) => {
        result.push({ id: `scene_${scene.id}`, name: scene.name });
      });
    }

    const matchingSystems = visibilitySystemOptions.value.filter(system => matchName(system.name));
    const showAllSystems = matchName(t('全部系统'));

    if (showAllSystems || matchingSystems.length > 0) {
      result.push({ id: '__group_system__', name: t('系统列表'), disabled: true });
      if (showAllSystems) {
        result.push({ id: 'all_systems', name: t('全部系统') });
      }
      matchingSystems.forEach((system) => {
        result.push({ id: `system_${system.id}`, name: system.name });
      });
    }

    return result;
  };

  const buildSearchSelectData = (): SearchSelectItem[] => [
    {
      name: '工具名称',
      id: 'name',
      placeholder: '请输入工具名称',
    },
    {
      name: '工具说明',
      id: 'description',
      placeholder: '请输入工具说明',
    },
    {
      name: '工具类型',
      id: 'tool_type',
      placeholder: '请选择工具类型',
      multiple: false,
      children: [
        { id: 'data_search', name: '数据查询' },
        { id: 'api', name: 'API' },
        { id: 'bk_vision', name: 'BK-Vision' },
      ],
    },
    {
      name: t('可见范围'),
      id: 'visibility',
      placeholder: t('请输入场景或系统名称'),
      multiple: true,
      async: true,
      children: buildVisibilityChildren(),
    },
    {
      name: '更新人',
      id: 'updated_by',
      placeholder: '请输入更新人',
      async: true,
    },
  ];

  const searchSelectData = ref<SearchSelectItem[]>(buildSearchSelectData());
  const menuItemTooltipMap = new WeakMap<HTMLElement, Instance>();

  const visibilityOptionLabelMap = computed(() => {
    const map: Record<string, string> = {};
    buildVisibilityChildren().forEach((item) => {
      if (!item.id.startsWith('__group_')) {
        map[item.id] = item.name;
      }
    });
    searchSelectData.value
      .find(item => item.id === 'tool_type')
      ?.children
      ?.forEach((child) => {
        map[child.id] = child.name;
      });
    return map;
  });

  const getMenuItemFullText = (itemEl: HTMLElement) => {
    const mapped = visibilityOptionLabelMap.value[itemEl.id];
    if (mapped) return mapped;
    return itemEl.textContent?.replace(/\s+/g, ' ').trim() || '';
  };

  const shouldShowOverflowTooltip = (el: HTMLElement, fullText: string) => {
    if (el.scrollWidth > el.clientWidth + 1) {
      return true;
    }

    const checkboxWidth = el.querySelector('.is-selected')?.getBoundingClientRect().width ?? 0;
    const availableWidth = el.clientWidth - checkboxWidth - 16;
    if (availableWidth <= 0) {
      return fullText.length > 15;
    }

    const { font } = window.getComputedStyle(el);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      return fullText.length > 15;
    }
    ctx.font = font;
    return ctx.measureText(fullText).width > availableWidth;
  };

  const syncTooltipTypography = (instance: Instance) => {
    const ref = instance.reference as HTMLElement;
    const { fontSize, lineHeight, fontFamily, fontWeight } = window.getComputedStyle(ref);
    const content = instance.popper.querySelector('.tippy-content') as HTMLElement | null;
    if (!content) return;

    content.style.fontSize = fontSize;
    content.style.lineHeight = lineHeight;
    content.style.fontFamily = fontFamily;
    content.style.fontWeight = fontWeight;
  };

  const bindOverflowTooltip = (targetEl: HTMLElement, fullText: string) => {
    if (!fullText || !shouldShowOverflowTooltip(targetEl, fullText)) return;

    let tooltip = menuItemTooltipMap.get(targetEl);
    if (!tooltip) {
      tooltip = tippy(targetEl, {
        content: fullText,
        theme: 'tool-manage-search-tooltip',
        placement: 'top',
        arrow: true,
        appendTo: () => document.body,
        delay: [200, 0],
        zIndex: 99999,
        onMount: syncTooltipTypography,
        onShow: syncTooltipTypography,
      });
      menuItemTooltipMap.set(targetEl, tooltip);
      return;
    }

    tooltip.setContent(fullText);
  };

  const handleSearchMenuMouseOver = (event: MouseEvent) => {
    const target = event.target as HTMLElement;

    const menuItemEl = target.closest('.bk-search-select-popover .menu-content .menu-item') as HTMLElement | null;
    if (menuItemEl?.querySelector('.is-selected')) {
      bindOverflowTooltip(menuItemEl, getMenuItemFullText(menuItemEl));
      return;
    }

    const valueEl = target.closest('.tool-manage-search-area [data-type="value"]') as HTMLElement | null;
    if (!valueEl) return;

    const optionId = valueEl.dataset.id;
    const fullText = (optionId && visibilityOptionLabelMap.value[optionId])
      || valueEl.dataset.key
      || valueEl.textContent?.replace(/\s+/g, ' ').trim()
      || '';
    bindOverflowTooltip(valueEl, fullText);
  };

  watch([visibilitySceneOptions, visibilitySystemOptions], () => {
    searchSelectData.value = buildSearchSelectData();
  });

  const toolListRef = ref();
  const previewDrawerRef = ref();
  const searchModel = ref<Record<string, any>>({});
  const tagsEnums = ref<Array<TagItem>>([]);
  const strategyList = ref<Array<{ label: string; value: number }>>([]);
  const allToolsData = ref<Array<ToolInfo>>([]);

  const statusFilter = ref('all');
  const statusCounts = reactive({
    all: 0,
    published: 0,
    unpublished: 0,
  });

  const confirmActionType = ref<ActionType>('delete');
  const confirmTarget = ref<ToolItem | null>(null);
  const isPreviewShow = ref(false);
  const isEditVisibilityShow = ref(false);
  const editVisibilityTarget = ref<ToolItem | null>(null);

  const handleCreateReport = () => {
    router.push({ name: 'platformToolCreate', query: {
      scene_id: route.query.scene_id,
      scope_id: route.query.scope_id,
      scope_type: route.query.scope_type,
    } });
  };

  const handleEdit = (row: ToolItem) => {
    router.push({
      name: 'platformToolEdit',
      params: { id: row.uid },
      query: {
        scene_id: route.query.scene_id,
        scope_id: route.query.scope_id,
        scope_type: route.query.scope_type,
      },
    });
  };

  const handlePreview = (row: ToolItem) => {
    isPreviewShow.value = true;
    previewDrawerRef.value?.open(row.uid);
  };

  const handleDelete = (row: ToolItem) => {
    confirmTarget.value = row;
    confirmDialogRef.value?.showDeleteInfoBox(row);
  };

  const confirmDialogRef = ref();
  const handleToggleStatus = (row: ToolItem) => {
    confirmTarget.value = row;
    const actionType = row.status === 'published' ? 'disable' : 'enable';
    confirmActionType.value = actionType;
    confirmDialogRef.value?.showToggleStatusInfoBox(row, actionType);
  };

  const handleActionSuccess = () => {
    confirmTarget.value = null;
    refreshList();
    fetchStatusCounts();
  };

  const handleEditVisibility = (row: ToolItem) => {
    editVisibilityTarget.value = row;
    isEditVisibilityShow.value = true;
  };

  const handleVisibilityEditSuccess = () => {
    editVisibilityTarget.value = null;
    refreshList();
  };

  const refreshList = (searchParams?: Record<string, any>) => {
    const params: Record<string, any> = {
      ...searchParams,
      sort: ['-created_at'],
    };
    if (statusFilter.value !== 'all') {
      params.status = [statusFilter.value];
    } else {
      params.status = undefined;
    }
    toolListRef.value?.fetchData(params);
  };

  const buildVisibilitySearchFields = (selectedIds: string[]) => {
    const payload = buildVisibilitySearchParams(selectedIds);
    if (!payload) return {};

    return {
      visibility_type: payload.visibility_type,
      scene_ids: payload.scene_ids.length ? payload.scene_ids : undefined,
      system_ids: payload.system_ids.length ? payload.system_ids : undefined,
    };
  };

  const handleSearchValueUpdate = (keyword: SearchKey[]) => {
    const visibilityItem = keyword.find(item => item.id === 'visibility');

    if (visibilityItem?.values?.length) {
      const normalizedIds = normalizeVisibilitySelectedIds(visibilityItem.values.map(value => value.id));
      visibilityItem.values = normalizedIds.map(id => ({
        id,
        name: getVisibilityOptionName(id),
      }));
    }

    searchValue.value = keyword;
    handleSearch(keyword);
  };

  const handleSearch = (keyword: SearchKey[]) => {
    const search: Record<string, any> = {
      name: undefined,
      description: '',
      tool_type: undefined,
      visibility_type: undefined,
      scene_ids: undefined,
      system_ids: undefined,
      updated_by: '',
    };

    keyword.forEach((item) => {
      if (!item.values?.length) return;

      if (item.id === 'visibility') {
        Object.assign(search, buildVisibilitySearchFields(item.values.map(v => v.id)));
        return;
      }

      const value = item.values.map(v => v.id).join(',');
      if (item.id === 'name') {
        search.name = value;
      } else if (item.id === 'description') {
        search.description = value;
      } else if (item.id === 'tool_type') {
        search.tool_type = value.split(',').map(v => v.trim());
      } else if (item.id === 'updated_by') {
        search.updated_by = value;
      }
    });

    refreshList(search);
  };

  const handleStatusFilterChange = () => {
    handleSearch(searchValue.value);
  };

  const handleClearSearch = () => {
    searchValue.value = [];
    statusFilter.value = 'all';
    toolListRef.value?.fetchData({ sort: ['-created_at'] });
  };

  const handleRequestSuccess = () => {
    isLoading.value = false;
  };

  const fetchStatusCounts = () => {
    const allPromise = ToolManageService.fetchToolsList({});
    const publishedPromise = ToolManageService.fetchToolsList({ status: ['published'] });
    const unpublishedPromise = ToolManageService.fetchToolsList({ status: ['unpublished'] });
    // eslint-disable-next-line max-len
    Promise.all([allPromise, publishedPromise, unpublishedPromise]).then(([allList, publishedList, unpublishedList]) => {
      statusCounts.all = allList.length;
      statusCounts.published = publishedList.length;
      statusCounts.unpublished = unpublishedList.length;
    });
  };

  useRequest(MetaManageService.fetchTags, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      tagsEnums.value = data.map((tag: { tag_id: string; tag_name: string }) => ({
        tag_id: tag.tag_id,
        tag_name: tag.tag_name,
      }));
    },
  });

  const loadVisibilityOptions = async () => {
    try {
      const scenes = await SceneManageService.fetchSceneAll({ status: 'enabled' });
      visibilitySceneOptions.value = (scenes || []).map((s: { scene_id: number; name: string }) => ({
        id: s.scene_id,
        name: s.name,
      }));
    } catch {
      visibilitySceneOptions.value = [];
    }
    try {
      const systems = await MetaManageService.fetchSystemWithAction({
        audit_status__in: 'accessed',
        namespace: 'default',
      });
      visibilitySystemOptions.value = (systems || []).map((s: any) => ({
        id: s.id,
        system_id: s.system_id,
        name: s.name,
      }));
    } catch {
      visibilitySystemOptions.value = [];
    }
    searchSelectData.value = buildSearchSelectData();
  };

  const {
    run: fetchUserList,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: { page: 1, page_size: 30 },
    defaultValue: { count: 0, results: [] } as { count: number; results: any[] },
  });

  const getMenuList = async (item: any, keyword: string) => {
    if (!item) return searchSelectData.value;
    const searchItem = searchSelectData.value.find(s => s.id === item?.id);
    if (!searchItem) return [];

    if (item.id === 'updated_by') {
      if (keyword) {
        const userList = await fetchUserList({ fuzzy_lookups: keyword });
        searchItem.children = userList.results.map((u: any) => ({
          id: u.username,
          name: `${u.username}(${u.display_name})`,
        }));
      } else {
        searchItem.children = [];
      }
      return searchItem.children;
    }

    if (item.id === 'visibility') {
      // 仅按展示名称过滤，避免内部 id / system_id 误匹配无关选项
      searchItem.children = filterVisibilityChildren(keyword);
      return searchItem.children;
    }

    return searchItem.children || [];
  };

  const {
    run: fetchStrategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    defaultValue: [],
    onSuccess: (data) => {
      strategyList.value = data;
    },
  });

  const {
    run: fetchAllToolsData,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: [],
    onSuccess: (data) => {
      allToolsData.value = data;
    },
  });

  const { on: onEvent, off } = useEventBus();

  const refreshAllData = () => {
    fetchAllToolsData();
    fetchUserList();
    refreshList();
    fetchStatusCounts();
  };

  onMounted(() => {
    fetchStrategyList();
    fetchAllToolsData();
    fetchUserList();
    fetchStatusCounts();
    loadVisibilityOptions();
    onEvent('scene:change', () => {
      refreshAllData();
    });
    document.addEventListener('mouseover', handleSearchMenuMouseOver, true);
  });

  onUnmounted(() => {
    document.removeEventListener('mouseover', handleSearchMenuMouseOver, true);
    off('scene:change');
  });
</script>

<style lang="postcss" scoped>
  .report-config {
    position: relative;
    min-height: 85vh;
    padding: 24px;
    background-color: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);
  }

  .report-config-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .header-left {
    display: flex;
    align-items: center;
  }

  .header-right {
    display: flex;
    align-items: center;
  }

  .mr4 {
    margin-right: 4px;
  }

  .mr8 {
    margin-right: 8px;
  }

  .mr16 {
    margin-right: 16px;
  }

  .status-filter {
    :deep(.bk-radio-button) {
      .bk-radio-button-label {
        display: flex;
        align-items: center;
        padding: 0 12px;
      }
    }

    :deep(.bk-radio-button:not(.is-checked)) {
      .status-count {
        color: #979ba5;
        background-color: #fff !important;
        border-color: #fff !important;
      }
    }
  }

  .status-count {
    height: 18px;
    min-width: 18px;
    padding: 0 4px;
    margin-left: 4px;
    font-size: 12px;
    line-height: 18px;
    pointer-events: none;
  }

  .search-input {
    width: 600px;
  }

  .report-config-content {
    min-height: 400px;

    :deep(.audit-tdesign-list) {
      border: none;
    }
  }
</style>

<!-- 下拉层挂到 body，需全局样式覆盖 bkui 的 white-space: pre -->
<style lang="postcss">
  .bk-search-select-popover {
    width: 280px !important;
    max-width: 280px !important;
  }

  .bk-search-select-popover .bk-search-select-menu {
    width: 100%;
    max-width: 100%;
  }

  /* 可见范围下拉：细滚动条并隐藏上下箭头（对齐工具跳转） */
  .bk-search-select-popover .bk-search-select-menu .menu-content {
    scrollbar-width: thin;
    scrollbar-color: #c4c6cc transparent;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content::-webkit-scrollbar {
    width: 4px;
    appearance: none;
    appearance: none;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content::-webkit-scrollbar-track {
    background: transparent;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content::-webkit-scrollbar-thumb {
    background-color: #c4c6cc;
    border-radius: 2px;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content::-webkit-scrollbar-thumb:hover {
    background-color: #979ba5;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content::-webkit-scrollbar-button,
  .bk-search-select-popover .bk-search-select-menu .menu-content::-webkit-scrollbar-button:single-button,
  .bk-search-select-popover
  .bk-search-select-menu
  .menu-content::-webkit-scrollbar-button:vertical:start:decrement,
  .bk-search-select-popover
  .bk-search-select-menu
  .menu-content::-webkit-scrollbar-button:vertical:start:increment,
  .bk-search-select-popover
  .bk-search-select-menu
  .menu-content::-webkit-scrollbar-button:vertical:end:decrement,
  .bk-search-select-popover
  .bk-search-select-menu
  .menu-content::-webkit-scrollbar-button:vertical:end:increment,
  .bk-search-select-popover
  .bk-search-select-menu
  .menu-content::-webkit-scrollbar-button:single-button:vertical:decrement,
  .bk-search-select-popover
  .bk-search-select-menu
  .menu-content::-webkit-scrollbar-button:single-button:vertical:increment,
  .bk-search-select-popover .bk-search-select-menu .menu-content::-webkit-scrollbar-corner {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    background: transparent !important;
    appearance: none !important;
    appearance: none !important;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content .menu-item {
    display: flex !important;
    align-items: center;
    max-width: 100% !important;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap !important;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content .menu-item .is-selected {
    flex-shrink: 0;
  }

  /* 可见范围分组标题：无勾选框，深色加粗与选项区分 */
  .bk-search-select-popover .bk-search-select-menu .menu-content .menu-item#__group_scene__,
  .bk-search-select-popover .bk-search-select-menu .menu-content .menu-item#__group_system__ {
    height: auto;
    min-height: 24px;
    font-size: 12px;
    font-weight: 500;
    line-height: 20px;
    color: #979ba5;
    pointer-events: none;
    cursor: default;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content .menu-item#__group_scene__:hover,
  .bk-search-select-popover .bk-search-select-menu .menu-content .menu-item#__group_system__:hover {
    color: #979ba5;
    background-color: transparent;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content .menu-item#__group_scene__ .is-selected,
  .bk-search-select-popover .bk-search-select-menu .menu-content .menu-item#__group_system__ .is-selected {
    display: none !important;
  }

  .tool-manage-search-area .bk-search-select [data-type='value'] {
    display: inline-block;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    vertical-align: bottom;
  }

  .tippy-box[data-theme~='tool-manage-search-tooltip'] {
    color: #fff;
    background-color: #000;
    border-radius: 2px;
    box-shadow: 0 2px 6px rgb(0 0 0 / 20%);
  }

  .tippy-box[data-theme~='tool-manage-search-tooltip'] .tippy-content {
    padding: 4px 8px;
  }

  .tippy-box[data-theme~='tool-manage-search-tooltip'][data-placement^='top'] > .tippy-arrow::before {
    border-top-color: #000;
  }

  .tippy-box[data-theme~='tool-manage-search-tooltip'][data-placement^='bottom'] > .tippy-arrow::before {
    border-bottom-color: #000;
  }
</style>
