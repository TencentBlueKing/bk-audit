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
        @mouseenter="handleMouseenter(item)"
        @mouseleave="handleMouseleave(item)">
        <div
          v-show="itemMouseenter === item.id"
          class="item-top-right-icon">
          <audit-icon
            class="edit-fill"
            type="edit-fill" />

          <bk-popover
            content="Top Right 文字提示"
            placement="bottom"
            theme="light"
            trigger="click">
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
                  disabled: !isTextOverflow(item.name),
                  content: t(item.name)
                }"
                class="title-text"
                :class="{ 'overflow-tooltip': isTextOverflow(item.name) }">
                {{ item.name }}
              </span>
              <bk-tag
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
            disabled: !isTextOverflow(item.desc, 44),
            content: middleTtooltips(item.desc),
            width: '200px',
            allowHTML: true,
            extCls: 'tooltip-custom'
          }"
          class="item-middle">
          {{ item.desc }}
        </div>
        <div class="item-footer">
          <span>@ xxxxx</span>
          <span>2015-3-20 15:22:00</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang='tsx'>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  const { t } = useI18n();
  const searchValue = ref([]);
  const descTag = ref(['场景', '场景12', '场景1', '9']);
  const isFixedDelete = ref(false);
  const itemMouseenter = ref(null);
  const dataList = ref([
    {
      name: '工v-bk-tooltipsv-bk-tooltipsv-bk-tooltipsv-bk-tooltipsv-bk-tooltipsv-bk-tooltips具1',
      desc: '工具1，啊哒哒哒',
      creator: '工具1',
      id: 1,
    },
    {
      name: '工具1',
      desc: '工具1',
      creator: '工具1',
      id: 2,
    }, {
      name: '工具1',
      desc: '用于查询一个用户在近90天的查询金额，单一数字查询工具很好用。'
        + '用于查询一个用户在近90天的查询金额，单一数字查询工具很好用。'
        + '用于查询一个用户在近90天的查询金额，单一数字查询工具很好用。'
        + '用于查询一个用户在近90天的查询金额，单一数字查询工具很好用。'
        + '用于查询一个用户在近90天的查询金额，单一数字查询工具很好用。'
        + '用于查询一个用户在近90天的查询金额，单一数字查询工具很好用。',
      creator: '工具1',
      id: 3,
    },
  ]);
  const handleMouseenter = (item: Record<string, any>) => {
    if (isFixedDelete.value) {
      return;
    }
    itemMouseenter.value = item.id;
  };
  const handleMouseleave = () => {
    if (isFixedDelete.value) {
      return;
    }
    itemMouseenter.value = null;
  };
  const handleCreate = () => {
    console.log('handleCreate');
  };
  // 删除
  const handleDelete = (item: Record<string, any>) => {
    console.log('handleDelete', item);
    isFixedDelete.value = !isFixedDelete.value;
    itemMouseenter.value = item.id;
  };

  const isTextOverflow = (text: string, maxHeight = 0) => {
    // 创建临时元素测量文本高度
    const temp = document.createElement('div');
    temp.style.position = 'absolute';
    temp.style.visibility = 'hidden';
    temp.style.width = '400px';
    temp.style.fontSize = '14px';
    temp.style.lineHeight = '22px';
    temp.style.display = '-webkit-box';
    temp.style.webkitLineClamp = '2';
    temp.style.webkitBoxOrient = 'vertical';
    temp.style.overflow = 'hidden';
    temp.innerText = text;
    document.body.appendChild(temp);

    const isOverflow = maxHeight > 0
      ? temp.scrollHeight > maxHeight
      : temp.scrollWidth > temp.clientWidth;

    document.body.removeChild(temp);
    return isOverflow;
  };
  const middleTtooltips = (text: string) => (
    <div style="max-width: 400px; word-break: break-word; white-space: normal;" >
        {text}
    </div>
  );
  const itemIcon = (item: Record<string, any>) => {
    switch (item.id) {
    case 1:
      return 'sqlxiao';
    case 2:
      return 'bkvisonxiao';
    case 3:
      return 'apixiao';
    }
  };
</script>

<style scoped lang="postcss">
.card {
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
      border: 1px solid transparent;
      box-shadow: 0 2px 4px 0 #0000001a, 0 2px 4px 0 #1919290d;
      transition: all .3s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px 0 rgb(0 0 0 / 10%), 0 6px 12px 0 rgb(25 25 41 / 10%);
      }

      @media (width <= 1600px) {
        min-width: 400px;
      }

      @media (width <= 1366px) {
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
          margin-right: 20px;

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
</style>
