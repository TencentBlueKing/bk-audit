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
        <span>{{ t('备选结果字段') }}</span>
        <span style="color: #979ba5;">（{{ t('可拖动进结果字段框') }}）</span>
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
                <span class="value">{{ element.raw_name }}({{ element.display_name }})</span>
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
      </bk-exception>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  interface Props {
    data: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      [key: string]: string;
    }>,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const rootRef = ref();
  const renderData = ref<Props['data']>([]);
  const renderStrategyClass = ref('');

  watch(() => props.data, () => {
    renderData.value = props.data;
  }, {
    immediate: true,
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
    width: 30%;

    /* max-width: 408px; */
    margin-left: var(--bk-theme-space-16);

    .wrapper {
      height: 100%;
      padding: var(--bk-theme-space-12) var(--bk-theme-space-16);
      background: var(--bk-theme-surface-subtle);
      border-radius: var(--bk-theme-tag-radius);

      &.fixed {
        position: fixed;
        top: 58px;
      }
    }

    .title {
      display: flex;
      margin-bottom: var(--bk-theme-space-16);
      line-height: 16px;
      color: var(--bk-theme-text-strong);

      .order-icon {
        margin-right: var(--bk-theme-space-4);
        font-size: 15px;
        color: var(--bk-theme-text-weak);
      }

      .order-icon:hover {
        color: var(--bk-theme-color-brand-2);
      }

      .text:hover,
      .text:hover .text-icon {
        color: var(--bk-theme-color-brand-2) !important;
      }

      .text .text-icon {
        color: var(--bk-theme-text-weak);
      }
    }

    .content-box {
      /* height: calc(100vh - 180px); */
      padding: 0 var(--bk-theme-space-8);
    }

    .list-item {
      display: flex;
      height: 36px;padding: var(--bk-theme-space-8) var(--bk-theme-space-8);
      color: var(--bk-theme-text-default);
      cursor: pointer;
      background: var(--bk-theme-surface-default);
      border-radius: var(--bk-theme-tag-radius);
      box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%);
      user-select: none;
      align-items: center;

      &:nth-child(n+2) {
        margin-top: var(--bk-theme-space-4);
      }

      .value {
        overflow: hidden;
        color: var(--bk-theme-text-weak);
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
    background: var(--bk-theme-surface-subtle);
  }
</style>
