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
    <div
      v-if="dataList.length > 0 || searchValue.length > 0 || (isGroupedMode && groupedTools.length > 0)"
      class="card-search">
      <bk-search-select
        v-model="searchValue"
        class="search-input"
        clearable
        :data="searchSelectData"
        :defaut-using-item="{ inputHtml: t('请选择') }"
        :get-menu-list="getMenuList"
        :placeholder="t('搜索工具名称、工具说明、工具类型、创建人、更新人')"
        unique-select
        @update:model-value="handleSearch" />
    </div>
    <scroll-faker
      :style="scrollStyle">
      <bk-loading
        :loading="loading"
        :z-index="10000">
        <!-- 跨场景/跨系统分组展示模式 -->
        <template v-if="isGroupedMode && groupedTools.length > 0">
          <div
            ref="cardListRef"
            class="card-list">
            <div
              v-for="group in groupedTools"
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
                        v-if="item.tool_type === 'smart_page'"
                        class="top-left-icon-img"
                        :src="userProfileIcon">
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
                      v-if="item.tool_type === 'smart_page'"
                      class="top-left-icon-img"
                      :src="userProfileIcon">
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
      </bk-loading>
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

<script setup lang='tsx'>
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';
  import MetaManageService from '@service/meta-manage';

  import ToolInfo from '@model/tool/tool-info';

  import useUrlSearch from '@hooks/use-url-search';

  import pentagramIcon from '@images/pentagram.svg';
  import pentagramFillIcon from '@images/pentagram-fill.svg';
  import userProfileIcon from '@images/user.svg';

  import { formatDate } from '@utils/assist/timestamp-conversion';

  import DialogVue from '../components/dialog/dialog.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';


  interface Exposes {
    getToolsList: (id: string) => void;
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

  const searchValue = ref<SearchKey[]>([]);

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
  const loading = ref(false);

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
    return sceneOrder.map((key) => {
      const sid = Number(key);
      return {
        groupKey: key,
        groupId: sid,
        groupName: sid === 0 ? t('未分类') : (props.sceneNameMap[sid] || `场景 ${sid}`),
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

  const toggleGroupCollapse = (groupKey: string) => {
    if (collapsedGroups.value.has(groupKey)) {
      collapsedGroups.value.delete(groupKey);
    } else {
      collapsedGroups.value.add(groupKey);
    }
  };
  const scrollStyle = {
    width: '98%',
    'margin-top': '10px',
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
      dataList.value = data;
    })
      .finally(() => {
        loading.value = false;
      });
    emits('change');
  };


  defineExpose<Exposes>({
    getToolsList(id: string) {
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
          dataList.value = data;
        })
          .finally(() => {
            loading.value = false;
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
  padding-top: 20px;
  padding-left: 16px;
  background-color: #f5f7fa;
  flex-direction: column;

  .card-search {
    position: relative;
    display: flex;
    width: 98%;
    justify-content: flex-end;

    .search-input {
      width: 100%;
    }
  }

  .card-list {
    position: relative;
    width: 100%;
    margin-top: 10px;
    align-content: flex-start;

    /* 顶部对齐 */
    .card-list-box {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-start;
      gap: 10px;
      width: 100%;

      .card-list-item {
        position: relative;
        width: calc((100% - 40px) / 5);
        height: 188px;
        margin-bottom: 10px;
        cursor: pointer;
        background: #fff;
        transition: all .3s ease;

        &:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 8px 0 rgb(0 0 0 / 10%), 0 6px 12px 0 rgb(25 25 41 / 10%);
        }

        @media (width <=2200px) {
          width: calc((100% - 30px) / 3);
        }

        @media (width <=2000px) {
          width: calc((100% - 30px) / 3);
        }

        @media (width <=1600px) {
          min-width: 400px;
        }

        @media (width <=1366px) {
          min-width: calc((100% - 20px) / 2);
        }

        .item-top {
          display: flex;
          height: 85px;

          .item-top-left {
            .top-left-icon {
              margin-top: 20px;
              margin-left: 20px;
              font-size: 48px;
            }

            .top-left-icon-img {
              width: 48px;
              height: 48px;
              margin-top: 20px;
              margin-left: 20px;
              border-radius: 8px;
            }
          }

          .item-top-right {
            width: 330px;
            height: 48px;
            margin-top: 20px;
            margin-left: 12px;

            .top-right-title {
              display: flex;
              align-items: flex-start;

              .title-text {
                display: inline-block;
                max-width: 300px;
                margin-right: 10px;
                overflow: hidden;
                font-size: 16px;
                font-weight: 700;
                line-height: 22px;
                letter-spacing: 0;
                color: #313238;
                text-overflow: ellipsis;
                white-space: nowrap;
                vertical-align: middle;

                &.overflow-tooltip {
                  cursor: pointer;
                }
              }

              .title-tag {
                margin-top: 0;
                line-height: 22px;
                cursor: pointer;
              }
            }

            .top-right-desc {
              .desc-tag {
                margin-right: 5px;
              }

              .tag-cursor {
                cursor: pointer;
              }
            }
          }
        }

        .item-middle {
          display: -webkit-box;
          width: calc(100% - 40px);
          height: 44px;
          margin-left: 20px;
          overflow: hidden;
          font-size: 14px;
          line-height: 22px;
          letter-spacing: 0;
          color: #313238;
          text-align: justify;
          text-overflow: ellipsis;
          word-break: break-word;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 2;
          line-clamp: 2;
        }

        .item-footer {
          display: flex;
          width: calc(100% - 40px);
          margin-top: 20px;
          margin-left: 20px;
          font-size: 14px;
          line-height: 22px;
          letter-spacing: 0;
          color: #979ba5;
          align-items: center;
          justify-content: space-between;

          .line {
            display: inline-block;
            width: 1px;
            height: 10px;
            margin-right: 5px;
            margin-left: 5px;
            background-color: #979ba5;
          }
        }

        .item-top-right-icon {
          position: absolute;
          top: 0;
          right: 0;
          z-index: 1;
          display: flex;
          align-items: flex-start;
          justify-content: flex-end;
          width: 40px;
          height: 40px;
          border-top-right-radius: 2px;

          &.with-bg {
            background: linear-gradient(225deg, #f5f7fa 50%, transparent 50%);
          }

          .favorite-icon {
            position: relative;
            top: 4px;
            right: 4px;
            width: 16px;
            height: 16px;
            cursor: pointer;
            transition: all .2s ease;

            &:hover {
              transform: scale(1.2);
            }
          }
        }


      }

    }
  }

  .scene-group {
    margin-bottom: 8px;

    .scene-group-header {
      display: flex;
      height: 36px;
      padding: 0 12px;
      margin-bottom: 16px;
      cursor: pointer;
      background-color: #eaebf0;
      border-radius: 2px;
      user-select: none;
      align-items: center;

      &:hover {
        background-color: #e1e2e6;

        .scene-group-title {
          color: #3a84ff;
        }
      }

      .scene-group-arrow {
        display: inline-block;
        width: 0;
        height: 0;
        margin-right: 8px;
        border-color: #63656e transparent transparent;
        border-style: solid;
        border-width: 6px 5px 0;
        transition: transform .2s ease;
        flex-shrink: 0;

        &.is-collapsed {
          border-color: transparent transparent transparent #63656e;
          border-width: 5px 0 5px 6px;
        }
      }

      .scene-group-title {
        font-size: 14px;
        font-weight: 400;
        line-height: 22px;
        color: #313238;
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


</style>
