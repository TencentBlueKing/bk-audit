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
      <auth-button
        action-id="create_notice_group"
        theme="primary"
        @click="handleCreate">
        <audit-icon
          style="margin-right: 6px;"
          type="add" />
        {{ t('创建工具') }}
      </auth-button>
      <bk-input
        v-model="searchValue"
        class="search-input"
        :placeholder="t('搜索 工具名称、工具说明、创建人等')"
        type="search" />
    </div>
    <div class="card-list">
      <div
        v-for="(item, index) in dataList"
        :key="index"
        class="card-list-item"
        @click="handleClick(item)"
        @mouseenter="handleMouseenter(item)"
        @mouseleave="handleMouseleave()">
        <div
          v-show="itemMouseenter === item.uid"
          class="item-top-right-icon">
          <audit-icon
            class="edit-fill"
            type="edit-fill"
            @click.stop="handleEdit(item)" />

          <bk-popover
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
                  size="small"
                  theme="primary">
                  {{ t('确定') }}
                </bk-button>
                <bk-button
                  class="ml8"
                  size="small">
                  {{ t('取消') }}
                </bk-button>
              </div>
            </template>
            <audit-icon
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
                  content: t(item.name),
                  placement: 'top',
                  delay: [300, 0],
                  extCls: 'name-tooltip'
                }"
                class="title-text"
                :class="{ 'overflow-tooltip': isTextOverflow(item.name, 0, '200px', { isSingleLine: true }) }">
                {{ item.name }}
              </span>
              <bk-tag
                v-if="!item.permission.use_tool"
                v-bk-tooltips="{ content: t('申请权限可用') }"
                class="title-tag"
                size="small"
                theme="warning"
                type="filled">
                {{ t('申请可使用') }}
              </bk-tag>
              <!-- <bk-tag
               theme="info"
               size="small"
               class="title-tag"
               type="filled"
               v-bk-tooltips="{ content: t('部分人可用') }">
               {{ t('指定人使用') }} </bk-tag> -->
            </div>
            <div class="top-right-desc">
              <bk-tag
                v-for="(tag, tagIndex) in descTag.slice(0, 3)"
                :key="tagIndex"
                class="desc-tag"
                size="small">
                {{ tag }}
              </bk-tag>
              <bk-tag
                v-if="descTag.length > 3"
                class="desc-tag"
                size="small">
                + {{ descTag.length - 3
                }}
              </bk-tag>
              <bk-tag
                class="desc-tag"
                size="small"
                theme="info">
                运用在 3 个策略中
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
          <span>@ ivonye(叶青)</span>
          <span>2015-3-20 15:22:00</span>
        </div>
        <component
          :is="DialogVue"
          :ref="(el) => dialogRefs[item.uid] = el"
          :dialog-cls="`dialogCls${item.uid}`" />
      </div>
    </div>
  </div>
</template>

<script setup lang='tsx'>
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import ToolsSquare from '@service/tools-square';

  import toolInfo from '@model/tools-square/tools-square';

  import DialogVue from '../components/dialog.vue';

  import useRequest from '@/hooks/use-request';
  import type { IRequestResponsePaginationData } from '@/utils/request';

  const { t } = useI18n();
  const router = useRouter();
  const searchValue = ref<string>('');
  const descTag = ref(['场景', '场景12', '场景1', '9']);
  const isFixedDelete = ref(false);
  const itemMouseenter = ref(null);
  const dialogRefs = ref<Record<string, any>>({});
  const dataList = ref<toolInfo[]>([
    {
      uid: '3aa8a524564711f083bb0a97de54c4dd',
      name: '具名称',
      tool_type: 'data_search',
      version: 1,
      description: '工具描述',
      namespace: '命名空间',
      permission: {
        use_tool: true,
      },
    },
    {
      uid: '3aa8a524564711f083bb0a97d',
      name: '具33336奥观海干哈案件嘎嘎·观海干哈案件嘎观海干哈案件嘎观海干哈案件嘎观海干哈案件嘎观海干哈案件嘎',
      tool_type: 'bk_vision',
      version: 1,
      description: '工具描述',
      namespace: '命名空间',
      permission: {
        use_tool: false,
      },
    }, {
      uid: '3aa8a52456d',
      name: '阿嘎hi阿豪啊ak啊A大大',
      tool_type: 'api',
      version: 1,
      description: '啊发撒反反复复烦烦烦啊啊啊啊发撒反反复复烦烦烦啊啊啊啊发撒反反复复烦烦烦啊啊啊啊发撒反反复复烦烦烦啊啊啊啊发撒反反复复烦烦烦啊啊啊啊发撒反反复复烦烦烦啊啊啊啊发撒反反复复烦烦烦啊啊啊啊发撒反反复复烦烦烦啊啊啊',
      namespace: '命名空间',
      permission: {
        use_tool: true,
      },
    },

  ]);

  const handleEdit = (item: Record<string, any>) => {
    console.log('handleEdit', item);
  };
  // 工签列表
  const {
    run: fetchToolsList,
  } = useRequest(ToolsSquare.fetchToolsList, {
    defaultValue: {} as IRequestResponsePaginationData<toolInfo>,
    onSuccess: (data) => {
      dataList.value = data.results;
    },
  });


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
    console.log('handleDelete', item);
    isFixedDelete.value = !isFixedDelete.value;
    itemMouseenter.value = item.uid;
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

  const itemIcon = (item: toolInfo) => {
    switch (item.tool_type) {
    case 'data_search':
      return 'sqlxiao';
    case 'bk_vision':
      return 'bkvisonxiao';
    case 'api':
      return 'apixiao';
    }
  };
  const handleClick = async (item: toolInfo) => {
    console.log('handleClick', item, dialogRefs.value[item.uid]);

    if (dialogRefs.value[item.uid]) {
      dialogRefs.value[item.uid].openDialog(item);
    }
  };

  onMounted(() => {
    fetchToolsList({
      page: 1,
      page_size: 10,
      keyword: '',
      limit: 10,
      offset: 0,
      tags: [],
    });
  });

</script>

<style scoped lang="postcss">
.card {
  background-color: #f5f7fa;

  .card-search {
    position: relative;
    display: flex;

    .search-input {
      position: absolute;
      right: 50px;
      width: 600px;
      margin-left: 10px;
    }
  }

  .card-list {
    display: grid;
    width: 100%;
    margin-top: 10px;
    overflow-x: auto;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 10px;

    .card-list-item {
      position: relative;
      height: 188px;
      min-width: 400px;
      cursor: pointer;
      background: #fff;
      box-shadow: 0 2px 4px 0 #1919290d;
      transition: all .3s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px 0 rgb(0 0 0 / 10%), 0 6px 12px 0 rgb(25 25 41 / 10%);
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
        justify-content: space-between
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
