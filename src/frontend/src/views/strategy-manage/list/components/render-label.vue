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
    class="render-label-box"
    :style="renderStyle">
    <scroll-faker>
      <transition name="draw">
        <div
          v-if="showLabel"
          class="render-label">
          <div
            v-if="loading"
            class="label-menu-skeleton"
            data-testid="label-menu-skeleton">
            <div
              v-for="item in menuSkeletonRows"
              :key="item.id"
              class="label-item">
              <div class="label-box">
                <skeleton
                  custom-class="label-menu-skeleton-icon"
                  :height="16"
                  :width="16" />
                <skeleton
                  custom-class="label-menu-skeleton-text"
                  :height="14"
                  :width="item.textWidth" />
              </div>
              <skeleton
                custom-class="label-menu-skeleton-count"
                :height="14"
                :width="16" />
            </div>
          </div>
          <template v-else>
            <div
              v-for="(item, index) in labelList"
              :key="index"
              class="label-item"
              :class="[
                {active: active===item.tag_id},
                {final: index === final}
              ]"
              @click="handleSelect(item.tag_id)">
              <div class="label-box">
                <audit-icon
                  v-if="item?.icon"
                  class="tag-icon"
                  :class="[{active: active===item.tag_id}]"
                  :type="item?.icon" />
                <span v-else>
                  <audit-icon
                    v-if="index !== 0"
                    class="tag-icon"
                    :class="[{active: active===item.tag_id}]"
                    type="tag" />
                  <audit-icon
                    v-else
                    class="tag-icon"
                    :class="[{active: active===item.tag_id}]"
                    type="quanbu" />
                </span>
                <span
                  v-if="showTipObjects[item.tag_id]"
                  v-bk-tooltips="{content:item.tag_name, placement: 'top-start'}"
                  class="label-text"
                  :class="`item-text-${index}`">
                  {{ te( item.tag_name) ? t(item.tag_name) : item.tag_name }}
                </span>
                <span
                  v-else
                  class="label-text"
                  :class="`item-text-${index}`">
                  {{ te( item.tag_name) ? t(item.tag_name) : item.tag_name }}
                </span>
              </div>
              <div style="margin-left: auto;color: #c4c6cc;">
                <span :class="[{active: active===item.tag_id}]">{{ item?.strategy_count }}</span>
              </div>
            </div>
          </template>
        </div>
      </transition>
    </scroll-faker>
    <span
      class="operation-box"
      :class="{
        'is-show-label': showLabel
      }"
      @click="handleShowLabelToggle">
      <audit-icon
        class="operation-icon"
        type="angle-line-up" />
    </span>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute  } from 'vue-router';

  import Skeleton from '@components/skeleton/index.vue';

  import { isStrategyListRoute } from '../../utils/strategy-routes';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    strategy_count: number;
    icon: string;
  }
  interface Emits {
    (e: 'change', showLabel: boolean):void;
    (e: 'checked', name: string): void
  }
  interface Exposes{
    resetAllLabel: () => void;
    setLabel: (tag: string) => void;
    resetAll: (val: Array<TagItem>) => void;
  }
  interface Props{
    labels: Array<TagItem>,
    total: number,
    upgradeTotal: number,
    final?: number;
    renderStyle?: Record<string, any>;
    active?: string|number;
    loading?: boolean;
  }
  const props = withDefaults(defineProps<Props>(), {
    final: 1,
    renderStyle: () => ({}),
    active: 'all',
    loading: false,
  });
  const emits = defineEmits<Emits>();
  const menuSkeletonRows = [
    { id: 'menu-strategy', textWidth: 96 },
    { id: 'menu-risk', textWidth: 128 },
    { id: 'menu-rule', textWidth: 72 },
    { id: 'menu-notice', textWidth: 140 },
    { id: 'menu-link', textWidth: 88 },
    { id: 'menu-tool', textWidth: 112 },
    { id: 'menu-report', textWidth: 80 },
    { id: 'menu-scene', textWidth: 120 },
  ];
  const route = useRoute();
  const showTipObjects = ref({} as Record<string, boolean>);

  const all = ref<Array<TagItem>>([
    { tag_id: 'all', tag_name: isStrategyListRoute(route.name) ? '全部策略' : '', strategy_count: 0, icon: 'quanbu' },
  ]);
  const active = ref<string|number>(props.active);
  const showLabel = ref(true);
  const { t, te } = useI18n();

  // eslint-disable-next-line vue/no-mutating-props, vue/no-side-effects-in-computed-properties
  const labelList = computed(() => {
    // final 之前（含 final）的标签为固定分类，不参与排序
    const fixedEndIndex = props.final + 1 - all.value.length;
    const fixedLabels = props.labels.slice(0, Math.max(0, fixedEndIndex));
    const dynamicLabels = props.labels.slice(Math.max(0, fixedEndIndex)).sort((x, y) => {
      const reg = /[a-zA-Z0-9]/;
      if (reg.test(x.tag_name) || reg.test(y.tag_name)) {
        if (x.tag_name > y.tag_name) {
          return 1;
        } if (x.tag_name < y.tag_name) {
          return 1;
        }
        return 0;
      }
      return x.tag_name?.localeCompare(y.tag_name);
    });
    return [...all.value, ...fixedLabels, ...dynamicLabels];
  });


  const handleSelect = (id: string) => {
    if (active.value === id) {
      return;
    }
    active.value = id;
    emits('checked', id === 'all' ? '' : id);
  };

  const handleShowLabelToggle = () => {
    showLabel.value = !showLabel.value;
    emits('change', showLabel.value);
  };

  // 如果省略号就hover展示tips
  const handleShowTips = (data: Array<TagItem>) => {
    const labelWidth = 240;
    const iconWidth = 21;
    const showTipObjects = data.reduce((results, item, index) => {
      const textOffsettTarget = document.querySelector(`.item-text-${index}`) as HTMLElement;
      const textWidth = textOffsettTarget?.offsetWidth + iconWidth;
      if (textWidth >= labelWidth) {
        // eslint-disable-next-line no-param-reassign
        results[item.tag_id] = true;
      }
      return results;
    }, {} as Record<string, boolean>);
    return showTipObjects;
  };

  watch(() => props.labels, () => {
    nextTick(() => {
      showTipObjects.value = handleShowTips(labelList.value);
    });
  });
  watch(() => props.total, (data) => {
    if (data !== undefined && data !== null) {
      nextTick(() => {
        if (all.value[0]) {
          all.value[0].strategy_count = data;
        }
      });
    }
  }, {
    immediate: true,
  });
  watch(() => props.upgradeTotal, (data) => {
    if (data !== undefined && data !== null) {
      nextTick(() => {
        if (all.value[1]) {
          all.value[1].strategy_count = data;
        }
      });
    }
  }, {
    immediate: true,
  });

  defineExpose<Exposes>({
    resetAllLabel() {
      active.value = 'all';
    },
    setLabel(tag: string) {
      active.value = tag;
    },
    // 重置所有标签
    resetAll(val: Array<TagItem>) {
      all.value = val;
      nextTick(() => {
        if (active.value === '-3') {
          emits('checked', active.value);
        }
      });
    },
  });
</script>
<style lang="postcss" scoped>
.render-label-box {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;

  .render-label {
    position: relative;
    min-width: 240px;
    padding: 20px 0;
    color: #63656e;
    transition: all .8s;

    .active {
      color: #3a84ff !important;
      background: #e1ecff;

      &:hover {
        background: #e1ecff !important;
      }
    }

    .label-item.final {
      border-bottom: 1px solid #eaebf0;
    }

    .label-item {
      display: flex;
      width: 240px;
      height: 40px;
      padding: 0 16px;
      font-size: 14px;
      line-height: 40px;
      cursor: pointer;
      align-items: center;

      .label-box {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .label-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      &:hover {
        background: #eaebf0;
      }

      .tag-icon {
        margin-right: 5px;
        font-size: 16px;
        color: #dcdee5;
      }
    }

    .label-menu-skeleton {
      .label-item {
        line-height: 1;
        cursor: default;

        &:hover {
          background: transparent;
        }
      }

      .label-box {
        display: flex;
        align-items: center;
        min-width: 0;
      }

      :deep(.audit-skeleton) {
        display: block;
        flex-shrink: 0;
        align-self: center;
        /* 灰底上比表格骨架深一档，底色用表格高光色 #E4E9F2 */
        background: linear-gradient(90deg, #e4e9f2 0%, #d3dbe8 50%, #e4e9f2 100%);
        background-position: -200% 0;
        background-size: 200% 100%;
      }

      :deep(.label-menu-skeleton-icon) {
        margin-right: 5px;
      }

      :deep(.label-menu-skeleton-count) {
        margin-left: auto;
      }
    }
  }

  .draw-enter-active,
  .draw-leave-active {
    transition: all  0s ease;
  }

  .draw-enter-from,
  .draw-leave-to {
    width: 0;
    opacity: 0%;
  }

  .operation-box {
    position: absolute;
    top: 50%;
    right: 0;
    right: -16px;
    z-index: 1;
    width: 16px;
    height: 64px;
    font-size: 14px;
    line-height: 61px;
    color: white;
    cursor: pointer;
    background: #dcdee5;
    border-radius: 0 4px 4px 0;

    .operation-icon {
      display: inline-block;
      transform: rotate(90deg);
    }
  }

  .is-show-label {
    .operation-icon {
      transform: rotate(-90deg);
    }
  }
}
</style>
