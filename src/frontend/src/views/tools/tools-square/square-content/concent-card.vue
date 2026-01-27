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
    <div class="card-search">
      <bk-button
        class="search-button"
        theme="primary"
        @click="handleCreate">
        <audit-icon
          style="margin-right: 6px;"
          type="add" />
        {{ t('创建工具') }}
      </bk-button>
      <bk-input
        v-model="searchValue"
        class="search-input"
        :placeholder="t('搜索 工具名称、工具说明、创建人等')"
        type="search"
        @enter="handleSearch" />
    </div>
    <scroll-faker
      :style="scrollStyle"
      @reach-bottom="handleScroll">
      <bk-loading
        :loading="loading"
        :z-index="10000">
        <div
          v-if="dataList.filter(item => item.permission.manage_tool || item.permission.use_tool).length > 0"
          ref="cardListRef"
          class="card-list"
          @scroll="handleScroll">
          <div class="card-list-box">
            <div
              v-for="(item, index) in dataList.filter(item => item.permission.manage_tool || item.permission.use_tool)"
              :key="index"
              class="card-list-item"
              @click="handleClickTool(item)"
              @mouseenter="handleMouseenter(item)"
              @mouseleave="handleMouseleave()">
              <!-- 左上角收藏icon -->
              <div
                v-show="itemMouseenter === item.uid || item.favorite"
                class="item-top-left-icon"
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
              <div
                v-show="itemMouseenter === item.uid"
                class="item-top-right-icon">
                <auth-button
                  v-if="!item.permission.manage_tool"
                  v-bk-tooltips="t('暂无编辑权限')"
                  action-id="manage_tool"
                  :permission="false"
                  :resource="item.uid"
                  text
                  theme="primary">
                  <audit-icon
                    class="edit-fill"
                    type="edit-fill" />
                </auth-button>
                <audit-icon
                  v-else
                  class="edit-fill"
                  type="edit-fill"
                  @click.stop="handleEdit(item)" />

                <bk-popover
                  :ref="(el: any) => popoverRefs.set(item.uid, el)"
                  placement="bottom"
                  theme="light"
                  trigger="click">
                  <template #content>
                    <div class="delete-title">
                      {{ t('确认删除该工具？') }}
                    </div>
                    <div class="delete-text">
                      {{ t('删除操作无法撤回，请谨慎操作！') }}
                    </div>

                    <div class="delete-btn">
                      <bk-button
                        v-bk-tooltips="{
                          disabled: !(item.strategies.length > 0),
                          content: t('该工具正在被策略使用，无法删除'),
                        }"
                        :disabled="item.strategies.length > 0"
                        size="small"
                        theme="primary"
                        @click="handleDeleteItem(item)">
                        {{ t('确定') }}
                      </bk-button>
                      <bk-button
                        class="ml8"
                        size="small"
                        @click="handleCancel(item.uid)">
                        {{ t('取消') }}
                      </bk-button>
                    </div>
                  </template>

                  <auth-button
                    v-if="!item.permission.manage_tool"
                    v-bk-tooltips="t('暂无删除权限')"
                    action-id="manage_tool"
                    :permission="false"
                    :resource="item.uid"
                    text
                    theme="primary">
                    <audit-icon
                      class="delete"
                      type="delete" />
                  </auth-button>
                  <audit-icon
                    v-else
                    class="delete"
                    type="delete"
                    @click.stop="handleDelete(item)" />
                </bk-popover>
              </div>

              <div class="item-top">
                <div class="item-top-left">
                  <audit-icon
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
                    <bk-tag
                      v-if="!item.permission.use_tool"
                      v-bk-tooltips="{ content: t('申请权限可用') }"
                      class="title-tag"
                      size="small"
                      theme="warning"
                      type="filled">
                      {{ t('申请可使用') }}
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
          <div
            v-show="hasMore"
            class="has-more">
            <bk-loading
              :loading="hasMore"
              mode="spin"
              size="mini"
              theme="primary" />
            <span class="more-text">
              {{ t('加载中...') }}
            </span>
          </div>
        </div>

        <div
          v-else
          class="card-emptyt">
          <img
            class="empty-img"
            src="@images/empty.svg">
          <div class="empty-text">
            {{ t('暂无数据') }}
          </div>
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
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import ToolInfo from '@model/tool/tool-info';

  import useUrlSearch from '@hooks/use-url-search';

  import pentagramIcon from '@images/pentagram.svg';
  import pentagramFillIcon from '@images/pentagram-fill.svg';

  import { formatDate } from '@utils/assist/timestamp-conversion';

  import DialogVue from '../components/dialog.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';
  import type { IRequestResponsePaginationData } from '@/utils/request';


  interface Exposes {
    getToolsList: (id: string) => void;
  }
  interface Emits {
    (e: 'change'): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  declare global {
    interface Window {
      scrollDebounceTimer: number | undefined;
    }
  }
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
  }


  const { messageSuccess } = useMessage();
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();

  // 使用工具对话框hooks
  const {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
    handleOpenTool,
  } = useToolDialog();

  const searchValue = ref<string>('');
  const isFixedDelete = ref(false);
  const itemMouseenter = ref(null);
  const dataList = ref<ToolInfo[]>([]);
  const popoverRefs = ref<Map<string, any>>(new Map());
  const currentPage = ref(1);
  const currentPagSize = ref(50);
  const hasMore = ref(false);
  const cardListRef = ref<HTMLElement | null>(null);
  const total = ref(0);
  const loading = ref(false);
  const isMoreLoading = ref(false);
  const scrollStyle = {
    width: '98%',
    'margin-top': '10px',
    height: 'calc(100vh - 200px)',
  };

  const urlToolsIds = ref<Set<string>>(new Set());
  const {
    removeSearchParam,
    appendSearchParams,
  } = useUrlSearch();

  // 获取所有工具
  const {
    data: allToolsData,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    manual: true,
  });

  // 收藏/取消收藏
  const {
    run: toggleFavorite,
  } = useRequest(ToolManageService.toggleFavorite, {
    defaultValue: {},
  });

  const openUrlTools = () => {
    const toolIds = typeof route.query.tool_id === 'string' ? route.query.tool_id.split(',') : [];
    urlToolsIds.value = new Set(toolIds);
    allOpenToolsData.value = toolIds;
    if (urlToolsIds.value.size > 0) {
      urlToolsIds.value.forEach((item: string) => {
        // 使用hooks中的handleOpenTool
        handleOpenTool(item);
        setTimeout(() => {
          const modals = document.querySelectorAll('.tools-use-dialog.bk-modal-wrapper');
          Array.from(modals).reverse()
            .forEach((modal, index) => {
              const htmlModal = modal as HTMLElement;
              if (index > 0 && !htmlModal.style.transform) {
                htmlModal.style.left = `${50 - (index + 1) * 2}%`;
              }
            });
        }, 0);
      });
    }
  };

  // 工具列表
  const {
    run: fetchToolsList,
  } = useRequest(ToolManageService.fetchToolsList, {
    defaultValue: {} as IRequestResponsePaginationData<ToolInfo>,
    onSuccess: () => {
      // 触底拼接数据
      // dataList.value = [...dataList.value, ...data.results];
      // total.value = data.total;

      // 自动打开弹窗
      if (route.query.tool_id) {
        openUrlTools();
      }
    },
  });

  // 删除
  const {
    run: fetchDeleteTool,
  } = useRequest(ToolManageService.fetchDeleteTool, {
    defaultValue: {},
    onSuccess: () => {
      messageSuccess(t('删除成功'));
      // 刷新右侧标签数据
      emits('change');
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

  const handleDeleteItem = (item: Record<string, any>) => {
    fetchDeleteTool({
      uid: item.uid,
    }).then(() => {
      handleCancel(item.uid);
      loading.value = true;
      currentPage.value = 1;
      fetchToolsList({
        page: currentPage.value,
        page_size: currentPagSize.value,
        my_created: props.myCreated,
        recent_used: props.recentUsed,
        keyword: searchValue.value,
        tags: [props.tagId],
      }).then((data) => {
        // 非拼接模式，重新赋值
        dataList.value = data.results;
        total.value = data.total;
      })
        .finally(() => {
          loading.value = false;
        });
    });
  };

  const handleCancel = (itemUid: string) => {
    const popover = popoverRefs.value.get(itemUid);
    popover?.hide();
    isFixedDelete.value = false;
    itemMouseenter.value = null;
  };

  const handleEdit = (item: Record<string, any>) => {
    if (!item.permission.manage_tool) {
      return;
    }
    if (item.permission.use_tool) {
      router.push({
        name: 'toolsEdit',
        params: {
          id: item.uid,
        },
      });
    }
  };

  const handleMouseenter = (item: Record<string, any>) => {
    if (isFixedDelete.value) {
      return;
    }
    itemMouseenter.value = item.uid;
  };

  const handleMouseleave = () => {
    if (isFixedDelete.value) {
      return;
    }
    itemMouseenter.value = null;
  };

  const handleCreate = () => {
    router.push({
      name: 'toolsAdd',
    });
  };

  // 删除
  const handleDelete = (item: Record<string, any>) => {
    if (item.permission.manage_tool) {
      isFixedDelete.value = !isFixedDelete.value;
      itemMouseenter.value = item.uid;
    }
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
      fetchToolsList({
        page: 1,
        page_size: currentPage.value * currentPagSize.value,
        my_created: props.myCreated,
        recent_used: props.recentUsed,
        keyword: searchValue.value,
        tags: [props.tagId],
      }).then((data) => {
        dataList.value = data.results;
        total.value = data.total;
      });
    });
  };

  // 策略跳转
  const handlesStrategiesClick = (item: ToolInfo) => {
    if (item?.strategies.length === 0) {
      return;
    }
    const url = router.resolve({
      name: 'strategyList',
      query: {
        strategy_id: item.strategies.join(','),
      },
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
  const handleClickTool = async (toolInfo: ToolInfo) => {
    urlToolsIds.value.add(toolInfo.uid);
    // 在游览器地址增加参数单不刷新页面
    appendSearchParams({
      tool_id: Array.from(urlToolsIds.value).join(','),
    });

    handleCancel(toolInfo.uid);

    // 使用hooks中的handleOpenTool
    handleOpenTool(toolInfo.uid);
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

  const handleSearch = () => {
    loading.value = true;
    currentPage.value = 1;
    fetchToolsList({
      page: currentPage.value,
      page_size: currentPagSize.value,
      keyword: searchValue.value,
      my_created: props.myCreated,
      recent_used: props.recentUsed,
      tags: [props.tagId],
    }).then((data) => {
      // 非拼接模式，重新赋值
      dataList.value = data.results;
      total.value = data.total;
    })
      .finally(() => {
        loading.value = false;
      });
    emits('change');
  };

  // 下拉加载
  const handleScroll = () => {
    if (total.value <= dataList.value.length || isMoreLoading.value) {
      hasMore.value = false;
      return;
    }

    // 防抖逻辑
    clearTimeout(window.scrollDebounceTimer);
    window.scrollDebounceTimer = window.setTimeout(() => {
      loading.value = false;
      isMoreLoading.value = true;
      hasMore.value = true;
      currentPage.value += 1;

      fetchToolsList({
        page: currentPage.value,
        page_size: 50,
        keyword: searchValue.value,
        my_created: props.myCreated,
        recent_used: props.recentUsed,
        tags: [props.tagId],
      })
        .then((data) => {
          // 拼接模式，追加数据
          dataList.value = [...dataList.value, ...data.results];
          total.value = data.total;
        })
        .finally(() => {
          hasMore.value = false;
          isMoreLoading.value = false;
        });
    }, 1000);
  };

  defineExpose<Exposes>({
    getToolsList(id: string) {
      nextTick(() => {
        currentPage.value = 1;
        fetchToolsList({
          page: currentPage.value,
          page_size: 50,
          keyword: searchValue.value,
          my_created: props.myCreated,
          recent_used: props.recentUsed,
          tags: [id],
        }).then((data) => {
          // 非拼接模式，重新赋值
          dataList.value = data.results;
          total.value = data.total;
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
  width: 100%;
  padding-top: 20px;
  padding-left: 20px;
  background-color: #f5f7fa;

  .card-search {
    position: relative;
    display: flex;
    width: 98%;

    .search-input {
      position: absolute;
      right: 0;
      width: 600px;
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
                max-width: 200px;
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

        .item-top-left-icon {
          position: absolute;
          top: 0;
          left: 0;
          z-index: 1;
          display: flex;
          align-items: flex-start;
          justify-content: flex-start;
          width: 40px;
          height: 40px;
          border-top-left-radius: 2px;

          &.with-bg {
            background: linear-gradient(135deg, #f5f7fa 50%, transparent 50%);
          }

          .favorite-icon {
            position: relative;
            top: 4px;
            left: 4px;
            width: 16px;
            height: 16px;
            cursor: pointer;
            transition: all .2s ease;

            &:hover {
              transform: scale(1.2);
            }
          }
        }

        .item-top-right-icon {
          position: absolute;
          top: 10px;
          right: 10px;
          font-size: 16px;
          line-height: 22px;
          letter-spacing: 0;
          color: #979ba5;

          .edit-fill {
            margin-right: 5px;

            &:hover {
              color: #3a84ff;
            }
          }

          .delete {
            &:hover {
              color: #3a84ff;
            }
          }
        }

      }

    }

    .has-more {
      display: flex;
      justify-content: center;
      align-items: center;
      margin-top: 5px;
      font-size: 14px;
      color: #979ba5;

      .more-text {
        margin-left: 5px;
        color: #3a84ff;
      }
    }
  }

  .card-emptyt {
    position: relative;
    height: calc(100vh - 300px);

    .empty-img {
      position: absolute;
      top: 30%;
      left: 50%;
      width: 500px;
      transform: translate(-50%, -30%);
    }

    .empty-text {
      position: absolute;
      top: 45%;
      left: 50%;
      font-size: 18px;
      color: #979ba5;
      transform: translate(-50%, -45%);
    }
  }

}

.delete-title {
  width: 250px;
  font-size: 16px;
  line-height: 24px;
  letter-spacing: 0;
  color: #313238;
}

.delete-text {
  margin-top: 5px;
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0;
  color: #4d4f56;
}

.delete-btn {
  display: flex;
  justify-content: flex-end;
  margin-top: 5px;
}
</style>
