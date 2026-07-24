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
            theme="primary"
            @click="handleCreateReport">
            <audit-icon
              class="mr8"
              type="add" />
            {{ t('新建报表') }}
          </bk-button>
        </div>
        <div class="header-right report-manage-search-area">
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
            <bk-radio-button label="enabled">
              <audit-icon
                class="mr4"
                svg
                type="normal" />
              {{ t('启用') }}
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.published }}
              </bk-tag>
            </bk-radio-button>
            <bk-radio-button label="disabled">
              <audit-icon
                class="mr4"
                svg
                type="unknown" />
              {{ t('停用') }}
              <bk-tag
                class="status-count"
                theme="info">
                {{ statusCounts.unpublished }}
              </bk-tag>
            </bk-radio-button>
          </bk-radio-group>
          <bk-search-select
            v-model="searchKeyword"
            class="search-input"
            clearable
            :data="searchSelectData"
            :defaut-using-item="{ inputHtml: t('请选择') }"
            :get-menu-list="getMenuList"
            :placeholder="t('搜索 报表名称、报表描述、BKVision 报表、可见范围、更新人')"
            unique-select
            value-split-code=","
            @update:model-value="handleSearchValueUpdate" />
        </div>
      </div>

      <!-- 报表表格 -->
      <div class="report-config-content">
        <report-list-table
          v-if="isChartListsReady"
          ref="tableRef"
          :data-source="dataSource"
          :highlight-report-id="highlightReportId"
          :scene-name-map="sceneNameMap"
          :scene-options="visibilitySceneOptions"
          :scope-options-loading="visibilityOptionsLoading"
          :system-name-map="systemNameMap"
          :system-options="visibilitySystemOptions"
          @delete="handleShowDeleteConfirm"
          @edit="handleEdit"
          @edit-visibility="handleEditVisibility"
          @request-success="handleRequestSuccess"
          @toggle-status="handleConfirmToggleStatus" />
      </div>

      <!-- 新建/编辑报表侧边弹窗 -->
      <report-create-sideslider
        v-model:is-show="reportSidesliderVisible"
        :chart-lists="chartLists"
        :edit-data="editReportData"
        @cancel="handleReportSidesliderCancel"
        @submit="handleReportSubmit"
        @success="handleCreateSuccess" />

      <!-- 修改可见范围弹窗 -->
      <edit-visibility-dialog
        v-model:is-show="isEditVisibilityShow"
        :scene-options="visibilitySceneOptions"
        :system-options="visibilitySystemOptions"
        :target="editVisibilityTarget"
        @success="handleVisibilityEditSuccess" />
    </div>
  </skeleton-loading>
</template>

<script setup lang="ts">
  import { computed, h, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
  import { InfoBox } from 'bkui-vue';
  import { useI18n } from 'vue-i18n';
  import tippy, { type Instance } from 'tippy.js';

  import PanelModelService from '@service/report-config';
  import ToolManageService from '@service/tool-manage';
  import MetaManageService from '@service/meta-manage';
  import SceneManageService from '@service/scene-manage';

  import PanelModel from '@model/report-config/panel';

  import useRequest from '@hooks/use-request';
  import useMessage from '@/hooks/use-message';

  import { buildVisibilitySearchQuery } from '@views/platform-manage/tool-manage/create-tool/submit-payload';

  import ReportCreateSideslider, {
    type ReportFormData,
  } from './components/report-create-sideslider.vue';
  import ReportListTable from './components/report-list-table.vue';
  import EditVisibilityDialog from './components/edit-visibility-dialog.vue';
  import { showReportDisableConfirm } from './show-report-disable-confirm';

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

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const tableRef = ref();
  const statusFilter = ref('all');
  const statusCounts = reactive({
    all: 0,
    published: 0,
    unpublished: 0,
  });
  const searchKeyword = ref<SearchKey[]>([]);
  const highlightReportId = ref<string | null>(null);
  const chartLists = ref<any[]>([]);
  const isChartListsReady = ref(false);
  const reportSidesliderVisible = ref(false);
  const editReportData = ref<ReportFormData | null>(null);
  const isEditVisibilityShow = ref(false);
  const editVisibilityTarget = ref<any>(null);

  const visibilitySceneOptions = ref<Array<{ id: number; name: string }>>([]);
  const visibilitySystemOptions = ref<Array<{ id: number; system_id?: string; name: string }>>([]);
  const visibilityOptionsLoading = ref(false);

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
      id: `system_${system.system_id || system.id}`,
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
        result.push({ id: `system_${system.system_id || system.id}`, name: system.name });
      });
    }

    return result;
  };

  const buildBkvisionChildren = () => {
    const children: Array<{ id: string; name: string }> = [];
    chartLists.value.forEach((group) => {
      (group.share || []).forEach((item: { uid: string; name: string }) => {
        children.push({
          id: item.uid,
          name: `【${group.name}】${item.name}`,
        });
      });
    });
    return children;
  };

  const buildSearchSelectData = (): SearchSelectItem[] => [
    {
      name: t('报表名称'),
      id: 'name',
      placeholder: t('请输入报表名称'),
    },
    {
      name: t('报表描述'),
      id: 'description',
      placeholder: t('请输入报表描述'),
    },
    {
      name: t('BKVision 报表'),
      id: 'bkvision_report',
      placeholder: t('请输入BKVision报表'),
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
      name: t('更新人'),
      id: 'updated_by',
      placeholder: t('请输入更新人'),
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
    buildBkvisionChildren().forEach((item) => {
      map[item.id] = item.name;
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
    const refEl = instance.reference as HTMLElement;
    const { fontSize, lineHeight, fontFamily, fontWeight } = window.getComputedStyle(refEl);
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
        theme: 'report-manage-search-tooltip',
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

    const valueEl = target.closest('.report-manage-search-area [data-type="value"]') as HTMLElement | null;
    if (!valueEl) return;

    const optionId = valueEl.dataset.id;
    const fullText = (optionId && visibilityOptionLabelMap.value[optionId])
      || valueEl.dataset.key
      || valueEl.textContent?.replace(/\s+/g, ' ').trim()
      || '';
    bindOverflowTooltip(valueEl, fullText);
  };

  watch([visibilitySceneOptions, visibilitySystemOptions, chartLists], () => {
    searchSelectData.value = buildSearchSelectData();
  });

  // 根据 vision_id 从 share_list 接口数据中查找 BKVision 报表名称
  const findVisionName = (visionId: string): string => {
    for (const parent of chartLists.value) {
      if (parent.share) {
        const child = parent.share.find((item: { uid: string }) => item.uid === visionId);
        if (child) {
          return child.name;
        }
      }
    }
    return '';
  };

  // 根据 vision_id 查找父级空间的 uid
  const findVisionSpaceUid = (visionId: string): string => {
    for (const parent of chartLists.value) {
      if (parent.share) {
        const child = parent.share.find((item: { uid: string }) => item.uid === visionId);
        if (child) {
          return parent.uid;
        }
      }
    }
    return '';
  };

  const buildVisibilitySearchFields = (selectedIds: string[]) => buildVisibilitySearchQuery(selectedIds);

  const getSearchParams = (): Record<string, any> => {
    const search: Record<string, any> = {
      name: '',
      description: '',
      bkvision_report: '',
      updated_by: '',
      visibility_type: undefined,
      scene_ids: undefined,
      system_ids: undefined,
    };

    searchKeyword.value.forEach((item) => {
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
      } else if (item.id === 'bkvision_report') {
        search.bkvision_report = value;
      } else if (item.id === 'updated_by') {
        search.updated_by = value;
      }
    });
    return search;
  };

  const buildListParams = (params: Record<string, any> = {}) => {
    const searchParams = getSearchParams();
    const listParams: Record<string, any> = {
      page: params.page || 1,
      page_size: params.page_size || 20,
      ...searchParams,
    };

    if (statusFilter.value === 'enabled') {
      listParams.status = 'published';
    } else if (statusFilter.value === 'disabled') {
      listParams.status = 'unpublished';
    }

    Object.keys(listParams).forEach((key) => {
      if (listParams[key] === '' || listParams[key] === undefined || listParams[key] === null) {
        delete listParams[key];
      }
    });

    return listParams;
  };

  const filterResultsByBkvisionReport = (results: any[], bkvisionReport: string) => {
    if (!bkvisionReport) return results;

    const keyword = bkvisionReport.toLowerCase();
    const bkvisionUidSet = new Set(buildBkvisionChildren().map(item => item.id));

    if (bkvisionUidSet.has(bkvisionReport)) {
      return results.filter(item => item.vision_id === bkvisionReport);
    }

    return results.filter(item => (item.bkvisionReportName ?? '').toLowerCase().includes(keyword));
  };

  const dataSource = (params: any) => {
    const searchParams = getSearchParams();
    return PanelModelService.fetchPlatformPanels(buildListParams(params))
      .then((data) => {
        const results = data.results.map((panel: PanelModel) => ({
          id: panel.id,
          binding_type: panel.binding_type,
          name: panel.name,
          description: panel.description || '--',
          vision_id: panel.vision_id,
          bkvisionReportName: findVisionName(panel.vision_id),
          bkvisionSpaceUid: findVisionSpaceUid(panel.vision_id),
          status: panel.status || 'unpublished',
          updated_by: panel.updated_by || '--',
          updated_at: panel.updated_at || '--',
          visibility_type: panel.visibility_type,
          scene_ids: panel.scene_ids || [],
          system_ids: panel.system_ids || [],
          default_value_overrides: panel.default_value_overrides,
        }));
        const filteredResults = filterResultsByBkvisionReport(results, searchParams.bkvision_report);

        return {
          ...data,
          results: filteredResults,
          total: searchParams.bkvision_report ? filteredResults.length : data.total,
        };
      });
  };

  const { run: fetchUserList } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: { page: 1, page_size: 30 },
    defaultValue: { count: 0, results: [] as any[] },
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
      const normalizedKeyword = keyword.trim();
      const selectedNames = (searchKeyword.value.find(s => s.id === 'visibility')?.values || [])
        .map(value => value.name);
      const isEditingExistingSelection = normalizedKeyword && (
        selectedNames.includes(normalizedKeyword)
        || selectedNames.join(',') === normalizedKeyword
      );
      searchItem.children = (!normalizedKeyword || isEditingExistingSelection)
        ? buildVisibilityChildren()
        : filterVisibilityChildren(keyword);
      return searchItem.children;
    }

    return searchItem.children || [];
  };

  const { loading: isLoading, run: fetchChartLists } = useRequest(ToolManageService.fetchChartLists, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      if (Array.isArray(data)) {
        chartLists.value = data;
      }
    },
    onFinally: () => {
      isChartListsReady.value = true;
    },
  });

  const handleSearchValueUpdate = (keyword: SearchKey[]) => {
    const visibilityItem = keyword.find(item => item.id === 'visibility');

    if (visibilityItem?.values?.length) {
      const normalizedIds = normalizeVisibilitySelectedIds(visibilityItem.values.map(value => value.id));
      visibilityItem.values = normalizedIds.map(id => ({
        id,
        name: getVisibilityOptionName(id),
      }));
    }

    searchKeyword.value = keyword;
    handleSearch();
  };

  const handleSearch = () => {
    nextTick(() => {
      tableRef.value?.fetchData({ page: 1 });
    });
  };

  const handleStatusFilterChange = () => {
    nextTick(() => {
      tableRef.value?.fetchData({ page: 1 });
    });
  };

  const fetchStatusCounts = () => {
    const baseParams = { enable_paginate: true, page: 1, page_size: 1 };
    Promise.all([
      PanelModelService.fetchPlatformPanels(baseParams),
      PanelModelService.fetchPlatformPanels({ ...baseParams, status: 'published' }),
      PanelModelService.fetchPlatformPanels({ ...baseParams, status: 'unpublished' }),
    ]).then(([allData, publishedData, unpublishedData]) => {
      statusCounts.all = allData.total || 0;
      statusCounts.published = publishedData.total || 0;
      statusCounts.unpublished = unpublishedData.total || 0;
    });
  };

  const loadVisibilityOptions = async () => {
    visibilityOptionsLoading.value = true;
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
    } finally {
      visibilityOptionsLoading.value = false;
    }
    searchSelectData.value = buildSearchSelectData();
  };

  const handleCreateReport = () => {
    editReportData.value = null;
    reportSidesliderVisible.value = true;
  };

  const handleEdit = (report: any) => {
    editReportData.value = {
      id: String(report.id),
      bkvisionReport: report.vision_id || '',
      name: report.name,
      description: report.description === '--' ? '' : report.description,
      status: report.status,
      enabled: report.status === 'published',
      visibility_type: report.visibility_type || 'all_visible',
      scene_ids: report.scene_ids || [],
      system_ids: report.system_ids || [],
      default_value_overrides: report.default_value_overrides,
    };
    reportSidesliderVisible.value = true;
  };

  const handleEditVisibility = (row: any) => {
    editVisibilityTarget.value = row;
    isEditVisibilityShow.value = true;
  };

  const handleVisibilityEditSuccess = () => {
    editVisibilityTarget.value = null;
    refreshList();
  };

  const getConfirmBtnStyle = (isMatch: boolean) => ({
    height: '32px',
    padding: '0 16px',
    fontSize: '14px',
    lineHeight: '32px',
    borderRadius: '2px',
    border: '1px solid',
    outline: 'none',
    marginRight: '8px',
    backgroundColor: isMatch ? '#ea3636' : '#fff',
    borderColor: isMatch ? '#ea3636' : '#dcdee5',
    color: isMatch ? '#fff' : '#c4c6cc',
    cursor: isMatch ? 'pointer' : 'not-allowed',
  });

  const cancelBtnStyle = {
    height: '32px',
    padding: '0 16px',
    fontSize: '14px',
    lineHeight: '32px',
    borderRadius: '2px',
    border: '1px solid #c4c6cc',
    outline: 'none',
    backgroundColor: '#fff',
    color: '#63656e',
    cursor: 'pointer',
  };

  const handleCopyReportName = (name: string) => {
    if (!name) return;
    navigator.clipboard.writeText(name)
      .then(() => {
        messageSuccess(t('复制成功'));
      })
      .catch((err) => {
        console.error('复制失败:', err);
      });
  };

  const handleConfirmToggleStatus = (report: any) => {
    const isPublish = report.status !== 'published';

    if (isPublish) {
      InfoBox({
        title: t('确认启用该报表？'),
        subTitle: t('启用后，可见范围内的空间将可以查看和使用该报表，确认启用吗？'),
        confirmText: t('启用'),
        cancelText: t('取消'),
        headerAlign: 'center',
        contentAlign: 'center',
        footerAlign: 'center',
        confirmButtonTheme: 'primary',
        onConfirm: () => PanelModelService.publishPlatformPanel({
          panel_id: report.id,
          status: 'published',
        }).then(() => {
          messageSuccess(t('启用成功'));
          refreshList();
          fetchStatusCounts();
        }),
      });
      return;
    }

    showReportDisableConfirm({
      name: report.name,
      t,
      onConfirm: () => PanelModelService.publishPlatformPanel({
        panel_id: report.id,
        status: 'unpublished',
      }).then(() => {
        messageSuccess(t('停用成功'));
        refreshList();
        fetchStatusCounts();
      }),
    });
  };

  const handleShowDeleteConfirm = (report: any) => {
    const confirmName = ref('');
    /* eslint-disable prefer-const -- 赋值在闭包定义之后，必须使用 let */
    let deleteInfoInstance: any;
    deleteInfoInstance = InfoBox({
      /* eslint-enable prefer-const */
      type: 'warning',
      title: t('确定删除该报表？'),
      subTitle: () => h('div', { style: { textAlign: 'left' } }, [
        h('div', {
          style: {
            padding: '12px 16px',
            marginBottom: '16px',
            fontSize: '14px',
            color: '#63656e',
            textAlign: 'center',
            backgroundColor: '#f5f7fa',
            borderRadius: '2px',
          },
        }, [
          t('此操作将'),
          h('span', { style: { fontWeight: 600, color: '#ea3636' } }, t('永久删除该报表')),
          t('，且不可恢复，请谨慎操作！'),
        ]),
        h('div', {
          style: { marginBottom: '8px', fontSize: '14px', color: '#63656e', textAlign: 'left' },
        }, [
          t('请输入报表名称「'),
          h('span', {
            style: { color: '#3a84ff', cursor: 'pointer' },
            onClick: () => handleCopyReportName(report.name),
          }, report.name),
          t('」以确认删除'),
        ]),
        h('input', {
          value: confirmName.value,
          placeholder: t('请输入报表名称'),
          onInput: (e: Event) => {
            confirmName.value = (e.target as HTMLInputElement).value;
          },
          style: {
            width: '100%',
            height: '32px',
            padding: '0 10px',
            fontSize: '14px',
            border: '1px solid #c4c6cc',
            borderRadius: '2px',
            outline: 'none',
            boxSizing: 'border-box',
          },
        }),
      ]),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      footer: () => h('div', { style: { display: 'flex', justifyContent: 'center' } }, [
        h('button', {
          class: 'info-box-confirm-btn',
          style: getConfirmBtnStyle(confirmName.value === report.name),
          onClick: () => {
            if (confirmName.value !== report.name) return;
            PanelModelService.deletePlatformPanel({
              panel_id: report.id,
            }).then(() => {
              messageSuccess(t('删除成功'));
              deleteInfoInstance?.hide();
              refreshList();
              fetchStatusCounts();
            });
          },
        }, t('删除')),
        h('button', {
          style: cancelBtnStyle,
          onClick: () => deleteInfoInstance?.hide(),
        }, t('取消')),
      ]),
      onClose() {
        confirmName.value = '';
      },
    });
  };

  const refreshList = () => {
    nextTick(() => {
      tableRef.value?.fetchData({});
    });
  };

  const handleReportSubmit = () => {
    reportSidesliderVisible.value = false;
    editReportData.value = null;
  };

  const handleCreateSuccess = (panelId?: string) => {
    if (panelId) {
      highlightReportId.value = panelId;
    }
    refreshList();
    fetchStatusCounts();
  };

  const handleReportSidesliderCancel = () => {
    editReportData.value = null;
  };

  const handleRequestSuccess = () => {
    // 可以在这里处理请求成功后的逻辑
  };

  onMounted(() => {
    // 场景/系统选项与图表列表并行加载，表格出现时仍可能在 loading（跳转弹层可展示）
    loadVisibilityOptions();
    fetchChartLists().then(() => {
      fetchStatusCounts();
    });
    document.addEventListener('mouseover', handleSearchMenuMouseOver, true);
  });

  onUnmounted(() => {
    document.removeEventListener('mouseover', handleSearchMenuMouseOver, true);
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

  .bk-search-select-popover .bk-search-select-menu .menu-content {
    scrollbar-width: thin;
    scrollbar-color: #c4c6cc transparent;
  }

  .bk-search-select-popover .bk-search-select-menu .menu-content::-webkit-scrollbar {
    width: 4px;
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

  .report-manage-search-area .bk-search-select [data-type='value'] {
    display: inline-block;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    vertical-align: bottom;
  }

  .tippy-box[data-theme~='report-manage-search-tooltip'] {
    color: #fff;
    background-color: #000;
    border-radius: 2px;
    box-shadow: 0 2px 6px rgb(0 0 0 / 20%);
  }

  .tippy-box[data-theme~='report-manage-search-tooltip'] .tippy-content {
    padding: 4px 8px;
  }

  .tippy-box[data-theme~='report-manage-search-tooltip'][data-placement^='top'] > .tippy-arrow::before {
    border-top-color: #000;
  }

  .tippy-box[data-theme~='report-manage-search-tooltip'][data-placement^='bottom'] > .tippy-arrow::before {
    border-bottom-color: #000;
  }
</style>
