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
  <div
    ref="rootRef"
    class="render-alternative-field">
    <div
      class="wrapper"
      :class="renderStrategyClass">
      <div class="title">
        <span>{{ t('备选调试字段') }}</span>
        <span style="color: #979ba5;">（{{ t('可拖动进映射选择框') }}）</span>
        <div style="margin-left: auto;">
          <bk-dropdown
            :is-show="isShow">
            <bk-button
              text
              @click="handleShow">
              <audit-icon
                class="order-icon"
                :type="order?'sort': 'sort2'"
                @click="handleOrder" />
              <div class="text">
                {{ sortType === 'default'? t('解析顺序') : t('字母顺序') }}
                <audit-icon
                  class="text-icon"
                  type="angle-line-down" />
              </div>
            </bk-button>
            <template #content>
              <bk-dropdown-menu>
                <bk-dropdown-item
                  v-for="item in sortList"
                  :key="item.id"
                  :class="{'active': item.id === sortType}"
                  @click="handleSort(item.id)">
                  {{ t(item.name) }}
                </bk-dropdown-item>
              </bk-dropdown-menu>
            </template>
          </bk-dropdown>
        </div>
      </div>
      <div class="content-box">
        <scroll-faker>
          <vuedraggable
            :group="{
              name: 'field',
              pull: true,
              push: false
            }"
            item-key="key"
            :list="renderData"
            :sort="false">
            <template #item="{element}">
              <div
                class="list-item">
                <audit-icon type="move" />
                <span>{{ element.key }}</span>
                <span class="value">（{{ element.val }}）</span>
              </div>
            </template>
          </vuedraggable>
        </scroll-faker>
      </div>
      <bk-exception
        v-if="renderData.length < 1"
        class="list-empty"
        scene="part"
        type="search-empty">
        <div>{{ t('暂无数据') }}</div>
        <div
          v-if="data.length < 1"
          style="font-size: 12px; color: #979ba5;">
          {{ t('请先在上方完成调试') }}
        </div>
      </bk-exception>
    </div>
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    // onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import type EtlPreviewModel from '@model/collector/etl-preview';

  interface Props {
    data: Array<EtlPreviewModel>,
    relatedFieldMap: Record<string, string>,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const rootRef = ref();
  const renderData = ref<Props['data']>([]);
  const initData = ref<Props['data']>([]);
  const renderStrategyClass = ref('');
  const sortType = ref('default');
  const isShow = ref(false);
  const order = ref(false); // 顺序 倒序
  const sortList = [
    {
      id: 'default',
      name: '解析顺序',
    },
    {
      id: 'custom',
      name: '字母顺序',
    },
  ];

  const handleSort = (value: string) => {
    sortType.value = value;
    isShow.value = false;
    renderData.value = value === 'default' ? _.cloneDeep(initData.value) : renderData.value.sort((a, b) => a.key.localeCompare(b.key));
  };

  const handleShow = () => {
    isShow.value = true;
  };

  const handleOrder = () => {
    order.value = !order.value;
    renderData.value = renderData.value.reverse();
  };

  watch(() => [props.data, props.relatedFieldMap], () => {
    const keyMap = Object.values(props.relatedFieldMap).reduce((result, key) => ({
      ...result,
      [key]: true,
    }), {} as Record<string, boolean>);
    renderData.value = props.data.reduce((result, item) => {
      if (!keyMap[item.key]) {
        result.push(item);
      }
      return result;
    }, [] as Props['data']);
    initData.value = _.cloneDeep(renderData.value);
  }, {
    immediate: true,
  });

  // const handelFixed = _.throttle(() => {
  //   const { top } = rootRef.value.getBoundingClientRect();
  //   console.log('from handelFixed = ', top);
  //   renderStrategyClass.value = top < 55 ? 'fixed' : '';
  // }, 30);

  onMounted(() => {
    // const navigationContentEl = document.querySelector('#auditNavigationContent .scroll-faker-content');
    // console.log('from onad= ==  ', navigationContentEl);
    // if (navigationContentEl) {
    //   navigationContentEl.addEventListener('scroll', handelFixed);
    //   onBeforeUnmount(() => {
    //     navigationContentEl.removeEventListener('scroll', handelFixed);
    //   });
    // }
    // window.addEventListener('resize', handleWidth);
  });

</script>
<style lang="postcss" scoped>
  @media (width <= 1921px) {
    .render-alternative-field {
      width: 608px;

      .list-item {
        width: 592px;
      }
    }
  }

  .render-alternative-field {
    position: relative;

    /* width: 30%; */

    /* max-width: 408px; */

    /* margin-left: 16px; */

    .wrapper {
      height: 100%;
      padding: 12px 16px;
      background: #f5f7fa;
      border-radius: 2px;

      &.fixed {
        position: fixed;
        top: 58px;
      }
    }

    .title {
      display: flex;
      margin-bottom: 16px;
      line-height: 16px;
      color: #313238;

      .order-icon {
        margin-right: 3px;
        font-size: 15px;
        color: #979ba5;
      }

      .order-icon:hover {
        color: #3a84ff;
      }

      .text:hover,
      .text:hover .text-icon {
        color: #3a84ff !important;
      }

      .text .text-icon {
        color: #979ba5;
      }
    }

    .content-box {
      /* height: calc(100vh - 180px); */
      padding: 0 8px;
    }

    .list-item {
      display: flex;
      height: 36px;
      padding: 10px 8px;
      color: #63656e;
      cursor: pointer;
      background: #fff;
      border-radius: 2px;
      box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%);
      user-select: none;
      align-items: center;

      &:nth-child(n+2) {
        margin-top: 5px;
      }

      .value {
        overflow: hidden;
        color: #979ba5;
        text-overflow: ellipsis;
        word-break: keep-all;
        white-space: nowrap;
      }
    }

    .list-empty {
      position: absolute;
      top: 100px;
      right: 0;
      left: 0;
    }
  }

  .active {
    background: #f5f7fa;
  }
</style>
