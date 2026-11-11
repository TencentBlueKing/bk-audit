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
  <div class="card">
    <teleport
      v-if="searchAnchorReady"
      to="#tools-square-search-anchor">
      <div class="card-search">
        <bk-search-select
          v-model="searchValue"
          class="search-input"
          clearable
          :data="searchSelectData"
          :defaut-using-item="{ inputHtml: t('请选择') }"
          :get-menu-list="getMenuList"
          :placeholder="t('搜索工具名称、说明、类型、创建人')"
          unique-select
          @update:model-value="handleSearch" />
      </div>
    </teleport>
    <scroll-faker
      ref="scrollFakerRef"
      :style="scrollStyle">
      <div
        v-if="loading"
        class="card-list">
        <div
          v-if="singleScopeGroup"
          class="scene-group">
          <div class="scene-group-header">
            <span class="scene-group-arrow" />
            <span class="scene-group-title">{{ singleScopeGroup.groupName }}({{ singleScopeGroup.groupId }})</span>
          </div>
        </div>
        <div class="card-list-box">
          <div
            v-for="item in skeletonCount"
            :key="item"
            class="card-skeleton"
            aria-hidden="true">
            <div class="card-skeleton-head">
              <span class="card-skeleton-mark" />
              <span class="card-skeleton-copy">
                <span class="card-skeleton-line is-title" />
                <span class="card-skeleton-line is-tags" />
              </span>
            </div>
            <span class="card-skeleton-line is-desc" />
            <span class="card-skeleton-line is-footer" />
          </div>
        </div>
      </div>
      <template v-else>
        <!-- 跨场景/跨系统分组展示模式 -->
        <template v-if="displayGroups.length > 0">
          <div
            ref="cardListRef"
            class="card-list">
            <div
              v-for="group in displayGroups"
              :key="group.groupKey"
              class="scene-group">
              <div
                class="scene-group-header"
                @click="toggleGroupCollapse(group.groupKey)">
                <span
                  class="scene-group-arrow"
                  :class="{ 'is-collapsed': collapsedGroups.has(group.groupKey) }" />
                <span class="scene-group-title">{{ group.groupName }}({{ group.groupId }})</span>
              </div>
              <div
                v-show="!collapsedGroups.has(group.groupKey)"
                class="card-list-box">
                <div
                  v-for="(item, index) in group.tools"
                  :key="index"
                  class="card-list-item"
                  @click="handleClickTool(item, group.groupKey)"
                  @mouseenter="handleMouseenter(item)"
                  @mouseleave="handleMouseleave()">
                  <!-- 右上角收藏icon -->
                  <div
                    v-show="itemMouseenter === item.uid || item.favorite"
                    class="item-top-right-icon"
                    :class="{ 'with-bg': itemMouseenter === item.uid }">
                    <img
                      v-bk-tooltips="{
                        content: item.favorite ? t('取消收藏') : t('收藏'),
                        placement: 'top',
                      }"
                      class="favorite-icon"
                      :src="item.favorite ? pentagramFillIcon : pentagramIcon"
                      @click.stop="handleToggleFavorite(item)">
                  </div>
                  <div class="item-top">
                    <div class="item-top-left">
                      <img
                        v-if="toolTypeMark(item)"
                        alt=""
                        class="type-mark"
                        :src="toolTypeMark(item)">
                      <audit-icon
                        v-else
                        class="top-left-icon"
                        svg
                        :type="itemIcon(item)" />
                    </div>
                    <div class="item-top-right">
                      <div class="top-right-title">
                        <span
                          v-bk-tooltips="{
                            disabled: !isTextOverflow(item.name, 0, '200px', { isSingleLine: true }),
                            content: item.name,
                            placement: 'top',
                            delay: [300, 0],
                            extCls: 'name-tooltip'
                          }"
                          class="title-text"
                          :class="{
                            'overflow-tooltip': isTextOverflow(item.name, 0, '200px', { isSingleLine: true }),
                          }">
                          {{ item.name }}
                        </span>
                        <bk-tag
                          v-if="item.is_bkvision"
                          v-bk-tooltips="{ content: t('BKVision参数变量待更新') }"
                          class="title-tag"
                          size="small"
                          theme="danger"
                          type="filled">
                          {{ t('待更新') }}
                        </bk-tag>
                      </div>
                      <div class="top-right-desc">
                        <bk-tag
                          v-for="(tag, tagIndex) in item.tags.slice(0, 3)"
                          :key="tagIndex"
                          class="desc-tag"
                          size="small">
                          {{ returnTagsName(tag) }}
                        </bk-tag>
                        <bk-tag
                          v-if="item.tags.length > 3"
                          v-bk-tooltips="{
                            content: tagContent(item.tags),
                            placement: 'top',
                          }"
                          class="desc-tag"
                          size="small">
                          + {{ item.tags.length - 3 }}
                        </bk-tag>
                        <bk-tag
                          class="desc-tag tag-cursor"
                          size="small"
                          theme="info"
                          @click="handlesStrategiesClick(item)">
                          {{ t('运用在') }} {{ item.strategies.length }} {{ t('个策略中') }}
                        </bk-tag>
                      </div>
                    </div>
                  </div>
                  <div
                    v-bk-tooltips="{
                      disabled: !isTextOverflow(item.description, 44, '400px', { isSingleLine: false }),
                      content: middleTtooltips(item.description),
                      width: '200px',
                      placement: 'bottom',
                      allowHTML: true,
                      extCls: 'tooltip-custom'
                    }"
                    class="item-middle">
                    {{ item.description }}
                  </div>
                  <div class="item-footer">
                    <div>
                      <span
                        v-bk-tooltips="{
                          content: t('创建人'),
                          theme: 'light',
                        }">{{ item.created_by }}</span>
                      <span class="line" />
                      <span
                        v-bk-tooltips="{
                          content: t('更新人'),
                          theme: 'light',
                        }">{{ item.updated_by }}</span>
                    </div>
                    <span
                      v-bk-tooltips="{
                        content: t('更新时间'),
                        theme: 'light',
                      }">{{ formatDate(item.updated_at) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
        <!-- 普通扁平展示模式 -->
        <template v-else-if="dataList.length > 0">
          <div
            ref="cardListRef"
            class="card-list">
            <div class="card-list-box">
              <div
                v-for="(item, index) in dataList"
                :key="index"
                class="card-list-item"
                @click="handleClickTool(item)"
                @mouseenter="handleMouseenter(item)"
                @mouseleave="handleMouseleave()">
                <!-- 右上角收藏icon -->
                <div
                  v-show="itemMouseenter === item.uid || item.favorite"
                  class="item-top-right-icon"
                  :class="{ 'with-bg': itemMouseenter === item.uid }">
                  <img
                    v-bk-tooltips="{
                      content: item.favorite ? t('取消收藏') : t('收藏'),
                      placement: 'top',
                    }"
                    class="favorite-icon"
                    :src="item.favorite ? pentagramFillIcon : pentagramIcon"
                    @click.stop="handleToggleFavorite(item)">
                </div>


                <div class="item-top">
                  <div class="item-top-left">
                    <img
                      v-if="toolTypeMark(item)"
                      alt=""
                      class="type-mark"
                      :src="toolTypeMark(item)">
                    <audit-icon
                      v-else
                      class="top-left-icon"
                      svg
                      :type="itemIcon(item)" />
                  </div>
                  <div class="item-top-right">
                    <div class="top-right-title">
                      <span
                        v-bk-tooltips="{
                          disabled: !isTextOverflow(item.name, 0, '200px', { isSingleLine: true }),
                          content: item.name,
                          placement: 'top',
                          delay: [300, 0],
                          extCls: 'name-tooltip'
                        }"
                        class="title-text"
                        :class="{ 'overflow-tooltip': isTextOverflow(item.name, 0, '200px', { isSingleLine: true }) }">
                        {{ item.name }}
                      </span>
                      <bk-tag
                        v-if="item.is_bkvision"
                        v-bk-tooltips="{ content: t('BKVision参数变量待更新') }"
                        class="title-tag"
                        size="small"
                        theme="danger"
                        type="filled">
                        {{ t('待更新') }}
                      </bk-tag>
                    </div>
                    <div class="top-right-desc">
                      <bk-tag
                        v-for="(tag, tagIndex) in item.tags.slice(0, 3)"
                        :key="tagIndex"
                        class="desc-tag"
                        size="small">
                        {{ returnTagsName(tag) }}
                      </bk-tag>
                      <bk-tag
                        v-if="item.tags.length > 3"
                        v-bk-tooltips="{
                          content: tagContent(item.tags),
                          placement: 'top',
                        }"
                        class="desc-tag"
                        size="small">
                        + {{ item.tags.length - 3
                        }}
                      </bk-tag>
                      <bk-tag
                        class="desc-tag tag-cursor"
                        size="small"
                        theme="info"
                        @click="handlesStrategiesClick(item)">
                        {{ t('运用在') }} {{ item.strategies.length }} {{ t('个策略中') }}
                      </bk-tag>
                    </div>
                  </div>
                </div>
                <div
                  v-bk-tooltips="{
                    disabled: !isTextOverflow(item.description, 44, '400px', { isSingleLine: false }),
                    content: middleTtooltips(item.description),
                    width: '200px',
                    placement: 'bottom',
                    allowHTML: true,
                    extCls: 'tooltip-custom'
                  }"
                  class="item-middle">
                  {{ item.description }}
                </div>
                <div class="item-footer">
                  <div>
                    <span
                      v-bk-tooltips="{
                        content: t('创建人'),
                        theme: 'light',
                      }">{{ item.created_by }}</span>
                    <span class="line" />

                    <span
                      v-bk-tooltips="{
                        content: t('更新人'),
                        theme: 'light',
                      }">{{ item.updated_by }}</span>
                  </div>
                  <span
                    v-bk-tooltips="{
                      content: t('更新时间'),
                      theme: 'light',
                    }">{{ formatDate(item.updated_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div
          v-if="dataList.length === 0 && groupedTools.length === 0"
          class="card-empty">
          <bk-exception
            class="empty-exception"
            :description="t('暂无数据')"
            scene="part"
            type="empty" />
        </div>
      </template>
    </scroll-faker>
  </div>
  <div
    v-for="item in allOpenToolsData"
    :key="item">
    <component
      :is="DialogVue"
      :ref="(el: any) => dialogRefs[item] = el"
      :all-tools-data="allToolsData"
      :tags-enums="tagsEnums"
      @close="handleClose"
      @open-field-down="openFieldDown" />
  </div>
</template>

<script lang="tsx">
  // 广场/详情路由切换会重建页面实例，滚动位置需提到模块级保存
  let cachedToolsSquareScrollTop = 0;
</script>
<script setup lang='tsx'>
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';
  import MetaManageService from '@service/meta-manage';

  import ToolInfo from '@model/tool/tool-info';

  import useUrlSearch from '@hooks/use-url-search';

  import pentagramIcon from '@images/pentagram.svg';
  import pentagramFillIcon from '@images/pentagram-fill.svg';
  import toolTypeApi from '@images/tools-square/tool-type-api.svg';
  import toolTypeBkvision from '@images/tools-square/tool-type-bkvision.svg';
  import toolTypeSmart from '@images/tools-square/tool-type-smart.svg';
  import toolTypeSql from '@images/tools-square/tool-type-sql.svg';

  import { formatDate } from '@utils/assist/timestamp-conversion';

  import DialogVue from '../components/dialog/dialog.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';
  import { groupToolsByScene } from '@/views/tools/tools-square/utils/tool-scene-groups';


  interface Exposes {
    getToolsList: (id: string, restoreScroll?: boolean) => void;
    clearSearch: () => void;
    saveScrollPosition: () => void;
    restoreScrollPosition: () => Promise<void>;
  }
  interface Emits {
    (e: 'change'): void;
    (e: 'openTool', toolInfo: ToolInfo, overrideContext?: { scene_id?: number; system_id?: string }): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  interface TagItem {
    tag_id: string
    tag_name: string
    tool_count: number
  }
  interface Props {
    tagsEnums: Array<TagItem>,
    myCreated: boolean,
    recentUsed: boolean,
    tagId: string,
    scopeParams: {
      scope_type?: string,
      scope_id?: string,
    },
    isCrossScene: boolean,
    isCrossSystem: boolean,
    sceneNameMap: Record<number, string>,
    systemNameMap: Record<string, string>,
    accessibleSceneIds: number[] | null,
    singleScopeGroup?: {
      groupKey: string,
      groupName: string,
      groupId: string | number,
    } | null,
  }


  const { messageSuccess, messageError } = useMessage();
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();

  // 使用工具对话框hooks
  const {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
    // handleOpenTool,
  } = useToolDialog();

  interface SearchKey {
    id: string;
    name: string;
    values: Array<{ id: string; name: string }>;
  }

  // 列表搜索条件持久化：toolsSquare ↔ toolDetail 路由 key 不同会销毁重建组件
  const SEARCH_STORAGE_KEY = 'tools_square_list_search';
  const loadSearchValue = (): SearchKey[] => {
    try {
      const raw = sessionStorage.getItem(SEARCH_STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };
  const persistSearchValue = (value: SearchKey[]) => {
    if (value?.length) {
      sessionStorage.setItem(SEARCH_STORAGE_KEY, JSON.stringify(value));
      return;
    }
    sessionStorage.removeItem(SEARCH_STORAGE_KEY);
  };

  const searchValue = ref<SearchKey[]>(loadSearchValue());
  watch(searchValue, (val) => {
    persistSearchValue(val);
  }, { deep: true });

  // bk-search-select 搜索条件配置
  const searchSelectData = [
    {
      name: t('工具名称'),
      id: 'name',
      placeholder: t('请输入工具名称'),
    },
    {
      name: t('工具说明'),
      id: 'description',
      placeholder: t('请输入工具说明'),
    },
    {
      name: t('工具类型'),
      id: 'tool_type',
      placeholder: t('请选择工具类型'),
      multiple: false,
      children: [
        { id: 'data_search', name: t('数据查询') },
        { id: 'api', name: 'API' },
        { id: 'bk_vision', name: 'BK-Vision' },
      ],
    },
    {
      name: t('创建人'),
      id: 'created_by',
      placeholder: t('请输入创建人'),
      children: [] as Array<{ id: string; name: string }>,
    },
    {
      name: t('更新人'),
      id: 'updated_by',
      placeholder: t('请输入更新人'),
      children: [] as Array<{ id: string; name: string }>,
    },
  ];

  // 获取用户列表（用于创建人/更新人远程搜索）
  const {
    run: fetchUserList,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: { page: 1, page_size: 30 },
    defaultValue: { count: 0, results: [] } as { count: number; results: any[] },
  });

  // 远程搜索菜单列表（创建人/更新人输入时实时搜索）
  const getMenuList = async (item: any, keyword: string) => {
    if (!item) return searchSelectData;
    const searchItem = searchSelectData.find(s => s.id === item?.id);
    if (searchItem && (item.id === 'created_by' || item.id === 'updated_by')) {
      if (keyword) {
        const userList = await fetchUserList({ fuzzy_lookups: keyword });
        searchItem.children = userList.results.map((u: any) => ({
          id: u.username,
          name: `${u.username}(${u.display_name})`,
        }));
      } else {
        searchItem.children = [];
      }
    }
    return (searchSelectData.find(s => s.id === item?.id)?.children) || [];
  };

  const itemMouseenter = ref(null);
  const dataList = ref<ToolInfo[]>([]);

  // 判断 tagId 是否为有效的后端标签（排除空值和前端内置特殊标签：-3全部、-4我创建的、-5最近使用）
  const FRONTEND_SPECIAL_TAGS = ['-3', '-4', '-5'];
  const getValidTagsParam = (id: string) => {
    if (!id || FRONTEND_SPECIAL_TAGS.includes(id)) return {};
    return { tags: [id] };
  };

  const cardListRef = ref<HTMLElement | null>(null);
  const scrollFakerRef = ref<{
    getScroll:() => { scrollTop: number };
    scrollTo: (scrollLeft: number, scrollTop: number) => void;
  }>();
  const loading = ref(false);
  const skeletonCount = 4;
  let listRequestSeq = 0;

  const saveScrollPosition = () => {
    cachedToolsSquareScrollTop = scrollFakerRef.value?.getScroll()?.scrollTop ?? 0;
  };

  const restoreScrollPosition = async () => {
    if (cachedToolsSquareScrollTop <= 0) return;
    const apply = () => {
      scrollFakerRef.value?.scrollTo(0, cachedToolsSquareScrollTop);
    };
    await nextTick();
    apply();
    requestAnimationFrame(() => {
      apply();
      // 列表刚显示时高度可能尚未稳定，再补一次
      setTimeout(apply, 50);
      setTimeout(apply, 320);
    });
  };

  // 分组折叠状态
  const collapsedGroups = ref<Set<string>>(new Set());

  const UNCATEGORIZED_KEY = '__uncategorized__';

  interface ToolGroup {
    groupKey: string;
    groupName: string;
    groupId: string | number;
    tools: ToolInfo[];
  }

  const isGroupedMode = computed(() => props.isCrossScene || props.isCrossSystem);

  const buildSceneGroups = (tools: ToolInfo[]): ToolGroup[] => groupToolsByScene(tools, props.accessibleSceneIds)
    .map(({ groupKey, tools: groupTools }) => {
      const sid = Number(groupKey);
      return {
        groupKey,
        groupId: sid,
        groupName: sid === 0 ? t('未分类') : (props.sceneNameMap[sid] || `场景 ${sid}`),
        tools: groupTools,
      };
    });

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
    return systemOrder.map(key => ({
      groupKey: key,
      groupId: key === UNCATEGORIZED_KEY ? '-' : key,
      groupName: key === UNCATEGORIZED_KEY
        ? t('未分类')
        : (props.systemNameMap[key] || `系统 ${key}`),
      tools: groupMap.get(key) || [],
    }));
  };

  const groupedTools = computed<ToolGroup[]>(() => {
    if (!isGroupedMode.value || dataList.value.length === 0) return [];
    if (props.isCrossScene) {
      return buildSceneGroups(dataList.value);
    }
    return buildSystemGroups(dataList.value);
  });

  const displayGroups = computed<ToolGroup[]>(() => {
    if (isGroupedMode.value) return groupedTools.value;
    if (props.singleScopeGroup && dataList.value.length > 0) {
      return [{
        groupKey: props.singleScopeGroup.groupKey,
        groupName: props.singleScopeGroup.groupName,
        groupId: props.singleScopeGroup.groupId,
        tools: dataList.value,
      }];
    }
    return [];
  });

  const searchAnchorReady = ref(false);
  const clearSearchAnchor = () => {
    const anchor = document.getElementById('tools-square-search-anchor');
    if (anchor) anchor.replaceChildren();
  };
  onMounted(() => {
    clearSearchAnchor();
    searchAnchorReady.value = !!document.getElementById('tools-square-search-anchor');
  });
  onBeforeUnmount(() => {
    searchAnchorReady.value = false;
    clearSearchAnchor();
  });

  const toolTypeMark = (item: ToolInfo) => {
    if (item.tool_type === 'api') return toolTypeApi;
    if (item.tool_type === 'data_search') return toolTypeSql;
    if (item.tool_type === 'bk_vision') return toolTypeBkvision;
    if (item.tool_type === 'smart_page') return toolTypeSmart;
    return '';
  };

  const toggleGroupCollapse = (groupKey: string) => {
    if (collapsedGroups.value.has(groupKey)) {
      collapsedGroups.value.delete(groupKey);
    } else {
      collapsedGroups.value.add(groupKey);
    }
  };
  const scrollStyle = {
    width: '100%',
    flex: '1',
    'min-height': '0',
  };

  const urlToolsIds = ref<Set<string>>(new Set());
  // 防止复制链接打开时重复打开弹窗（fetchToolsList 的 onSuccess 可能被多次触发）
  // const processedUrlToolId = ref<string | null>(null);
  const {
    removeSearchParam,
    appendSearchParams,
  } = useUrlSearch();

  // 获取所有工具（按场景过滤）
  const {
    data: allToolsData,
    run: fetchAllToolsList,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
  });

  // 监听场景切换，按当前场景拉取全量工具列表，避免缺少 scope_type/scope_id 导致的请求失败
  // 注意：搜索条件清空只在父组件 handleSceneChange(isActualChange) 中处理，
  // 避免路由重建 / 场景初始化时误清刚恢复的搜索条件
  watch(() => props.scopeParams, (val) => {
    if (!val || !val.scope_type) return;
    fetchAllToolsList({ ...val, status: 'published' });
  }, { immediate: true, deep: true });

  // 收藏/取消收藏
  const {
    run: toggleFavorite,
  } = useRequest(ToolManageService.toggleFavorite, {
    defaultValue: {},
  });

  // const openUrlTools = () => {
  //   const toolIdParam = route.query.tool_id;
  //   if (!toolIdParam) return;

  //   const toolIdKey = typeof toolIdParam === 'string' ? toolIdParam : '';
  //   if (processedUrlToolId.value === toolIdKey) {
  //     return; // 已处理过该 tool_id，防止重复打开弹窗
  //   }
  //   processedUrlToolId.value = toolIdKey;

  //   const toolIds = toolIdKey.split(',');
  //   urlToolsIds.value = new Set(toolIds);
  //   allOpenToolsData.value = toolIds;
  //   if (urlToolsIds.value.size > 0) {
  //     urlToolsIds.value.forEach((item: string) => {
  //       // 使用hooks中的handleOpenTool
  //       handleOpenTool(item);
  //       setTimeout(() => {
  //         const modals = document.querySelectorAll('.tools-use-dialog.bk-modal-wrapper');
  //         Array.from(modals).reverse()
  //           .forEach((modal, index) => {
  //             const htmlModal = modal as HTMLElement;
  //             if (index > 0 && !htmlModal.style.transform) {
  //               htmlModal.style.left = `${50 - (index + 1) * 2}%`;
  //             }
  //           });
  //       }, 0);
  //     });
  //   }
  // };

  // 工具列表（不再分页，直接返回数组）
  const {
    run: fetchToolsList,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: [] as ToolInfo[],
    onSuccess: () => {
      // 自动打开弹窗
      if (route.query.tool_id) {
        // openUrlTools();
      }
    },
  });


  // 标签名称
  const returnTagsName = (tags: string) => {
    let tagName = '';
    props.tagsEnums.forEach((item: TagItem) => {
      if (item.tag_id === tags) {
        tagName = item.tag_name;
      }
    });
    return tagName;
  };

  // +n显示
  const tagContent = (tags: Array<string>) => {
    const tagNameList = props.tagsEnums.map((i: TagItem) => {
      if (tags.slice(3, tags.length).includes(i.tag_id)) {
        return i.tag_name;
      }
      return null;
    }).filter(e => e !== null);
    return tagNameList.join(',');
  };

  const handleMouseenter = (item: Record<string, any>) => {
    itemMouseenter.value = item.uid;
  };

  const handleMouseleave = () => {
    itemMouseenter.value = null;
  };
  // 收藏/取消收藏
  const handleToggleFavorite = (item: ToolInfo) => {
    const newFavoriteStatus = !item.favorite;
    toggleFavorite({
      uid: item.uid,
      favorite: newFavoriteStatus,
    }).then(() => {
      messageSuccess(newFavoriteStatus ? t('收藏成功') : t('取消收藏成功'));
      // 重新获取列表数据，后端会处理排序
      handleSearch();
      // 通知父组件刷新标签列表，更新"我的收藏"等标签的数量
      emits('change');
    })
      .catch(() => {
        messageError(t('操作失败，请重试'));
      });
  };

  // 策略跳转
  const handlesStrategiesClick = (item: ToolInfo) => {
    if (item?.strategies.length === 0) {
      return;
    }
    const sceneParams = getSceneSystemParams();
    const query: Record<string, string> = {
      strategy_id: item.strategies.join(','),
    };
    // 携带场景信息
    if (sceneParams.scope_id) {
      query.scene_id = sceneParams.scope_id;
      query.scope_id = sceneParams.scope_id;
      query.scope_type = sceneParams.scope_type;
    } else if (sceneParams.scope_type) {
      query.scope_type = sceneParams.scope_type;
    }
    const url = router.resolve({
      name: 'strategyList',
      query,
    }).href;
    window.open(url, '_blank');
  };

  const isTextOverflow = (text: string, maxHeight = 0, width: string, options: {
    isSingleLine?: boolean;
    fontSize?: string;
    fontWeight?: string;
    lineHeight?: string;
  } = {}) => {
    if (!text) return false;

    const {
      isSingleLine = maxHeight === 0, // 默认单行检测
      fontSize = isSingleLine ? '16px' : '14px',
      fontWeight = isSingleLine ? '700' : 'normal',
      lineHeight = '22px',
    } = options;

    const temp = document.createElement('div');
    temp.style.position = 'absolute';
    temp.style.visibility = 'hidden';
    temp.style.width = width;
    temp.style.fontSize = fontSize;
    temp.style.fontWeight = fontWeight;
    temp.style.fontFamily = 'inherit';
    temp.style.lineHeight = lineHeight;
    temp.style.boxSizing = 'border-box';
    temp.textContent = text;

    if (isSingleLine) {
      temp.style.whiteSpace = 'nowrap';
      temp.style.overflow = 'visible';
    } else {
      temp.style.display = '-webkit-box';
      temp.style.webkitLineClamp = '2';
      temp.style.overflow = 'hidden';
    }

    document.body.appendChild(temp);

    const isOverflow = maxHeight > 0
      ? temp.scrollHeight > maxHeight
      : temp.scrollWidth > temp.offsetWidth;

    document.body.removeChild(temp);
    return isOverflow;
  };


  const middleTtooltips = (text: string) => (
  <div style="max-width: 400px; word-break: break-word; white-space: normal;" >
    {text}
  </div>
  );

  const itemIcon = (item: ToolInfo) => {
    switch (item.tool_type) {
    case 'data_search':
      return 'sqlxiao';
    case 'bk_vision':
      return 'bkvisonxiao';
    case 'api':
      return 'apixiao';
    }
  };


  /* *
   * 打开工具，根据工具信息，打开工具，并传递工具信息
   * @param toolInfo: ToolInfo 工具信息
   * @returns void
   */
  const buildOverrideContext = (groupKey?: string) => {
    if (!groupKey || groupKey === '0' || groupKey === UNCATEGORIZED_KEY) {
      return undefined;
    }
    if (props.isCrossScene) {
      const sceneId = Number(groupKey);
      if (!Number.isNaN(sceneId) && sceneId > 0) {
        return { scene_id: sceneId };
      }
    }
    if (props.isCrossSystem) {
      return { system_id: groupKey };
    }
    return undefined;
  };

  const handleClickTool = async (toolInfo: ToolInfo, groupKey?: string) => {
    saveScrollPosition();
    urlToolsIds.value.add(toolInfo.uid);
    appendSearchParams({
      tool_id: Array.from(urlToolsIds.value).join(','),
    });

    emits('openTool', toolInfo, buildOverrideContext(groupKey));
  };

  // 关闭弹窗
  const handleClose = (ToolUid: string | undefined) => {
    if (ToolUid) {
      urlToolsIds.value.delete(ToolUid);
      if (urlToolsIds.value.size <= 0) {
        removeSearchParam('tool_id');
      } else {
        appendSearchParams({
          tool_id: Array.from(urlToolsIds.value).join(','),
        });
      }
    }
  };

  const handleSearch = (keyword?: SearchKey[]) => {
    listRequestSeq += 1;
    const requestSeq = listRequestSeq;
    loading.value = true;
    const search: Record<string, any> = {};
    const searchKeys = keyword || searchValue.value;
    searchKeys.forEach((item) => {
      if (item.values && item.values.length) {
        const value = item.values.map(v => v.id).join(',');
        if (item.id === 'name') {
          search.name = value;
        } else if (item.id === 'description') {
          search.description = value;
        } else if (item.id === 'tool_type') {
          search.tool_type = value.split(',').map(v => v.trim());
        } else if (item.id === 'created_by') {
          search.keyword = value;
        } else if (item.id === 'updated_by') {
          search.updated_by = value;
        }
      }
    });
    fetchToolsList({
      ...search,
      my_created: props.myCreated,
      recent_used: props.recentUsed,
      status: 'published',
      ...getValidTagsParam(props.tagId),
      ...props.scopeParams,
    }).then((data) => {
      if (requestSeq !== listRequestSeq) return;
      dataList.value = data;
    })
      .finally(() => {
        if (requestSeq !== listRequestSeq) return;
        loading.value = false;
      });
    emits('change');
  };


  defineExpose<Exposes>({
    clearSearch() {
      searchValue.value = [];
      persistSearchValue([]);
    },
    saveScrollPosition,
    restoreScrollPosition,
    getToolsList(id: string, restoreScroll = false) {
      if (!restoreScroll) {
        cachedToolsSquareScrollTop = 0;
      }
      listRequestSeq += 1;
      const requestSeq = listRequestSeq;
      loading.value = true;
      nextTick(() => {
        const search: Record<string, any> = {};
        searchValue.value.forEach((item) => {
          if (item.values && item.values.length) {
            const value = item.values.map(v => v.id).join(',');
            if (item.id === 'name') {
              search.name = value;
            } else if (item.id === 'description') {
              search.description = value;
            } else if (item.id === 'tool_type') {
              search.tool_type = value.split(',').map(v => v.trim());
            } else if (item.id === 'created_by') {
              search.keyword = value;
            } else if (item.id === 'updated_by') {
              search.updated_by = value;
            }
          }
        });
        fetchToolsList({
          ...search,
          my_created: props.myCreated,
          recent_used: props.recentUsed,
          status: 'published',
          ...getValidTagsParam(id),
          ...props.scopeParams,
        }).then((data) => {
          if (requestSeq !== listRequestSeq) return;
          dataList.value = data;
        })
          .finally(async () => {
            if (requestSeq !== listRequestSeq) return;
            loading.value = false;
            if (restoreScroll) {
              await restoreScrollPosition();
            }
          });
      });
    },
  });
</script>

<style scoped lang="postcss">
.card {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  padding-top: var(--bk-theme-space-16);
  padding-left: var(--bk-theme-space-16);
  background-color: var(--bk-theme-surface-page);
  flex-direction: column;

  .card-search {
    position: relative;
    display: flex;
    width: calc(100% - 16px);
    justify-content: flex-end;

    .search-input {
      width: 100%;
    }
  }

  .card-list {
    position: relative;
    width: 100%;
    margin-top: 0;
    align-content: flex-start;

    /* 顶部对齐 */
    .card-list-box {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--bk-theme-space-16);
      width: 100%;

      .card-list-item {
        position: relative;
        display: flex;
        min-width: 0;
        height: 180px;
        padding: var(--bk-theme-space-16) var(--bk-theme-space-24);
        overflow: hidden;
        cursor: pointer;
        background: var(--bk-theme-surface-default);
        border: 1px solid transparent;
        border-radius: var(--bk-theme-card-radius);
        box-shadow: var(--bk-theme-card-shadow);
        flex-direction: column;
        gap: var(--bk-theme-space-16);
        transition: border-color .3s ease;

        &:hover {
          border-color: var(--bk-theme-border-brand);
        }

        .item-top {
          display: flex;
          height: auto;
          min-height: 48px;
          align-items: center;
          gap: var(--bk-theme-space-12);

          .item-top-left {
            flex-shrink: 0;

            .type-mark,
            .top-left-icon,
            .top-left-icon-img {
              display: block;
              width: 48px;
              height: 48px;
              margin: 0;
              overflow: hidden;
              font-size: 48px;
            }

            .type-mark {
              border-radius: var(--bk-theme-tab-radius);
            }

            .top-left-icon {
              border-radius: var(--bk-theme-radius-8);
            }

            .top-left-icon-img {
              border-radius: var(--bk-theme-radius-8);
            }
          }

          .item-top-right {
            flex: 1;
            width: auto;
            height: auto;
            min-width: 0;
            margin: 0;

            .top-right-title {
              display: flex;
              align-items: center;
              min-width: 0;
              gap: var(--bk-theme-space-8);

              .title-text {
                display: block;
                max-width: 100%;
                min-width: 0;
                margin-right: 0;
                overflow: hidden;
                font-size: var(--bk-theme-font-size-base);
                font-weight: 700;
                line-height: var(--bk-theme-line-height-base);
                letter-spacing: 0;
                color: var(--bk-theme-text-strong);
                text-overflow: ellipsis;
                white-space: nowrap;

                &.overflow-tooltip {
                  cursor: pointer;
                }
              }

              .title-tag {
                flex-shrink: 0;
                margin-top: 0;
                line-height: var(--bk-theme-line-height-base);
                cursor: pointer;
                border-radius: var(--bk-theme-radius-full) !important;
              }
            }

            .top-right-desc {
              display: flex;
              flex-wrap: wrap;
              align-items: center;
              margin-top: var(--bk-theme-space-8);
              gap: var(--bk-theme-space-8);

              .desc-tag {
                max-width: 100%;
                margin: 0;
                border-radius: var(--bk-theme-radius-full) !important;
              }

              .tag-cursor {
                cursor: pointer;
              }
            }
          }
        }

        .item-middle {
          display: -webkit-box;
          width: auto;
          height: auto;
          max-height: 40px;
          margin: 0;
          overflow: hidden;
          font-size: var(--bk-theme-font-size-sm);
          line-height: var(--bk-theme-line-height-sm);
          letter-spacing: 0;
          color: var(--bk-theme-text-default);
          text-overflow: ellipsis;
          word-break: break-word;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 2;
          line-clamp: 2;
        }

        .item-footer {
          position: absolute;
          right: var(--bk-theme-space-24);
          bottom: var(--bk-theme-space-16);
          left: var(--bk-theme-space-24);
          display: flex;
          width: auto;
          margin: 0;
          font-size: var(--bk-theme-font-size-sm);
          line-height: var(--bk-theme-line-height-sm);
          letter-spacing: 0;
          color: var(--bk-theme-text-weak);
          align-items: center;
          justify-content: space-between;

          .line {
            display: inline-block;
            width: 1px;
            height: 10px;
            margin-right: var(--bk-theme-space-4);
            margin-left: var(--bk-theme-space-4);
            background-color: var(--bk-theme-text-weak);
          }
        }

        .item-top-right-icon {
          position: absolute;
          top: var(--bk-theme-space-8);
          right: var(--bk-theme-space-8);
          z-index: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          width: var(--bk-theme-space-16);
          height: var(--bk-theme-space-16);
          background: none;

          .favorite-icon {
            width: var(--bk-theme-space-16);
            height: var(--bk-theme-space-16);
            cursor: pointer;
          }
        }


      }

    }
  }

  .scene-group {
    margin-bottom: var(--bk-theme-space-8);

    .scene-group-header {
      display: flex;
      height: var(--bk-theme-space-32);
      padding: 0 var(--bk-theme-space-16);
      margin-bottom: var(--bk-theme-space-16);
      cursor: pointer;
      background-color: var(--bk-theme-collapse-bg);
      border-radius: var(--bk-theme-collapse-radius);
      user-select: none;
      align-items: center;

      .scene-group-arrow {
        position: relative;
        display: inline-block;
        width: var(--bk-theme-space-12);
        height: var(--bk-theme-space-12);
        margin-right: var(--bk-theme-space-8);
        flex-shrink: 0;

        &::before {
          position: absolute;
          top: 50%;
          left: 50%;
          width: 0;
          height: 0;
          border-color: var(--bk-theme-text-default) transparent transparent;
          border-style: solid;
          border-width: 5px 4px 0;
          content: '';
          transform: translate(-50%, -50%);
          transition: transform .2s ease;
        }

        &.is-collapsed::before {
          transform: translate(-50%, -50%) rotate(-90deg);
        }
      }

      .scene-group-title {
        font-size: 14px;
        font-weight: 400;
        line-height: 22px;
        color: var(--bk-theme-text-strong);
        transition: color .2s;
      }
    }
  }

  .card-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: calc(100vh - 300px);

    .empty-exception {
      font-size: 20px;
    }
  }
}

.card {
  height: auto;
  padding: 0;
  background: transparent;
}

.card .card-search {
  width: 100%;
}

.card-skeleton {
  position: relative;
  display: flex;
  height: 180px;
  padding: var(--bk-theme-space-16) var(--bk-theme-space-24);
  background: var(--bk-theme-surface-default);
  border-radius: var(--bk-theme-card-radius);
  box-shadow: var(--bk-theme-card-shadow);
  flex-direction: column;
  gap: var(--bk-theme-space-16);
}

.card-skeleton-head {
  display: flex;
  align-items: center;
  min-height: 48px;
  gap: var(--bk-theme-space-12);
}

.card-skeleton-mark,
.card-skeleton-line {
  display: block;
  background: var(--bk-theme-collapse-bg);
  border-radius: var(--bk-theme-control-radius);
}

.card-skeleton-mark {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
}

.card-skeleton-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  gap: var(--bk-theme-space-8);
}

.card-skeleton-line {
  height: var(--bk-theme-space-12);

  &.is-title {
    width: 42%;
    height: var(--bk-theme-space-16);
  }

  &.is-tags {
    width: 68%;
  }

  &.is-desc {
    width: 86%;
  }

  &.is-footer {
    position: absolute;
    right: var(--bk-theme-space-24);
    bottom: var(--bk-theme-space-16);
    left: var(--bk-theme-space-24);
    width: auto;
  }
}

</style>
