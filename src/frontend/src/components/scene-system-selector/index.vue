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
  <bk-popover
    ref="popoverRef"
    :arrow="false"
    :ext-cls="dark ? 'scene-system-selector-popover-dark' : ''"
    :is-show="isPopoverShow"
    placement="bottom-start"
    :theme="dark ? 'dark' : 'light'"
    trigger="click"
    :width="popoverWidth"
    @after-hidden="handlePopoverHidden"
    @after-show="handlePopoverShow">
    <div
      class="scene-system-selector"
      :class="{ 'is-active': isPopoverShow, 'is-dark': dark }"
      :style="{ width: typeof width === 'number' ? `${width}px` : width }">
      <div class="selector-content">
        <bk-tag
          v-if="selectedItem"
          class="type-tag"
          :class="[`type-${selectedItem.type}`]">
          {{ getTypeLabel(selectedItem.type) }}
        </bk-tag>
        <show-tooltips-text
          class="selector-text"
          :data="displayText" />
      </div>
      <audit-icon
        class="selector-arrow"
        :class="{ 'is-flip': isPopoverShow }"
        type="angle-line-down" />
    </div>
    <template #content>
      <div
        class="scene-system-dropdown"
        :class="{ 'is-dark': dark }">
        <!-- 审计场景分组 -->
        <div class="dropdown-group">
          <div class="group-title">
            {{ t('审计场景') }}
          </div>
          <div class="group-list">
            <div
              v-for="item in sceneList"
              :key="item.id"
              class="dropdown-item"
              :class="{ 'is-selected': isSelected(item) }"
              @click="handleSelect(item)">
              <bk-tag
                class="type-tag"
                :class="[`type-${item.type}`]">
                {{ getTypeLabel(item.type) }}
              </bk-tag>
              <span
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }">
                {{ item.name }}
              </span>
              <span
                v-if="item.id"
                class="item-id">
                ({{ item.id }})
              </span>
            </div>
          </div>
        </div>

        <!-- 接入系统分组 -->
        <div class="dropdown-group">
          <div class="group-title">
            {{ t('接入系统') }}
          </div>
          <div class="group-list">
            <div
              v-for="item in systemList"
              :key="item.id"
              class="dropdown-item"
              :class="{ 'is-selected': isSelected(item) }"
              @click="handleSelect(item)">
              <bk-tag
                class="type-tag"
                :class="[`type-${item.type}`]">
                {{ getTypeLabel(item.type) }}
              </bk-tag>
              <span
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }">
                {{ item.name }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </bk-popover>
</template>

<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  interface SelectorItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
  }

  interface Props {
    modelValue?: SelectorItem | null;
    width?: number | string;
    popoverWidth?: number;
    dark?: boolean;
  }

  interface Emits {
    (e: 'update:modelValue', value: SelectorItem | null): void;
    (e: 'change', value: SelectorItem | null): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: null,
    width: 320,
    popoverWidth: 400,
    dark: false,
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const popoverRef = ref();
  const isPopoverShow = ref(false);
  const selectedItem = ref<SelectorItem | null>(props.modelValue);

  // 假数据 - 审计场景列表
  const sceneList = ref<SelectorItem[]>([
    { id: '1', name: '我的所有场景', type: 'aggregate' },
    { id: '100001', name: '主机安全审计', type: 'scene' },
    { id: '100002', name: '数据安全审计', type: 'scene' },
    { id: '100003', name: '网络安全审计', type: 'scene' },
  ]);

  // 假数据 - 接入系统列表
  const systemList = ref<SelectorItem[]>([
    { id: '2', name: '我的所有系统', type: 'aggregate' },
    { id: 'bk_job', name: '蓝鲸作业平台', type: 'system' },
  ]);

  // 显示文本
  const displayText = computed(() => {
    if (!selectedItem.value) {
      return t('请选择');
    }
    const { name, id } = selectedItem.value;
    return id ? `${name}(${id})` : name;
  });

  // 获取类型标签文本
  const getTypeLabel = (type: string) => {
    const labelMap: Record<string, string> = {
      aggregate: t('聚合'),
      scene: t('场景'),
      system: t('系统'),
    };
    return labelMap[type] || type;
  };

  // 判断是否选中
  const isSelected = (item: SelectorItem) => {
    if (!selectedItem.value) return false;
    return selectedItem.value.id === item.id && selectedItem.value.type === item.type;
  };

  // 选择项目
  const handleSelect = (item: SelectorItem) => {
    selectedItem.value = item;
    emits('update:modelValue', item);
    emits('change', item);
    isPopoverShow.value = false;
  };

  // 弹出层显示
  const handlePopoverShow = () => {
    isPopoverShow.value = true;
  };

  // 弹出层隐藏
  const handlePopoverHidden = () => {
    isPopoverShow.value = false;
  };

  // 监听外部值变化
  watch(() => props.modelValue, (newVal) => {
    selectedItem.value = newVal;
  });
</script>

<style lang="postcss" scoped>
.scene-system-selector {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  padding: 0 10px;
  cursor: pointer;
  background: #f0f1f5;
  border-radius: 2px;
  transition: all .3s;

  &:hover {
    border-color: #3a84ff;
  }

  &.is-active {
    border-color: #3a84ff;
  }

  /* 深色主题 */
  &.is-dark {
    background: #2e3847;
    border: 1px solid #3c4558;

    &:hover {
      border-color: #4d5565;
    }

    &.is-active {
      border-color: #699df4;
    }

    .selector-content {
      .selector-text {
        color: #c4c6cc;
      }
    }

    .selector-arrow {
      color: #63656e;
    }
  }

  .selector-content {
    display: flex;
    flex: 1;
    align-items: center;
    overflow: hidden;

    .type-tag {
      flex-shrink: 0;
      height: 22px;
      padding: 0 8px;
      margin-right: 8px;
      font-size: 12px;
      line-height: 20px;
      color: #fff;
      border: none;
      border-radius: 2px;

      &.type-aggregate {
        background-color: #ba69f4;
      }

      &.type-scene {
        background-color: #699df4;
      }

      &.type-system {
        background-color: #f8b64f;
      }
    }

    .selector-text {
      flex: 1;
      overflow: hidden;
      font-size: 14px;
      color: #313238;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .selector-arrow {
    flex-shrink: 0;
    margin-left: 8px;
    font-size: 16px;
    color: #979ba5;
    transition: transform .3s;

    &.is-flip {
      transform: rotate(180deg);
    }
  }
}

.scene-system-dropdown {
  max-height: 400px;
  overflow-y: auto;

  /* 深色主题 */
  &.is-dark {
    background: #1a2233;

    .dropdown-group {
      .group-title {
        color: #63656e;
      }

      .group-list {
        .dropdown-item {
          &:hover {
            background-color: #253047;
          }

          &.is-selected {
            background-color: #2a3a54;

            .item-name.is-highlight {
              color: #699df4;
            }
          }

          .item-name {
            color: #979ba5;

            &.is-highlight {
              color: #c4c6cc;
            }
          }

          .item-id {
            color: #63656e;
          }
        }
      }
    }
  }

  .dropdown-group {
    &:not(:last-child) {
      margin-bottom: 8px;
    }

    .group-title {
      padding: 8px 12px;
      font-size: 12px;
      color: #979ba5;
    }

    .group-list {
      .dropdown-item {
        display: flex;
        align-items: center;
        height: 36px;
        padding: 0 12px;
        cursor: pointer;
        transition: background-color .2s;

        &:hover {
          background-color: #f5f7fa;
        }

        &.is-selected {
          background-color: #e1ecff;

          .item-name.is-highlight {
            color: #3a84ff;
          }
        }

        .type-tag {
          flex-shrink: 0;
          height: 22px;
          padding: 0 6px;
          margin-right: 8px;
          font-size: 12px;
          line-height: 20px;
          color: #fff;
          border: none;
          border-radius: 2px;

          &.type-aggregate {
            background-color: #ba69f4;
          }

          &.type-scene {
            background-color: #699df4;
          }

          &.type-system {
            background-color: #f8b64f;
          }
        }

        .item-name {
          font-size: 12px;
          color: #63656e;

          &.is-highlight {
            color: #313238;
          }
        }

        .item-id {
          margin-left: 4px;
          font-size: 12px;
          color: #979ba5;
        }
      }
    }
  }
}
</style>

<style lang="postcss">
/* 深色主题弹出层样式 */
.scene-system-selector-popover-dark.bk-popover.bk-pop2-content {
  background: #1a2233 !important;
  border: none !important;
  box-shadow: 0 3px 9px 0 rgb(0 0 0 / 50%) !important;
}
</style>
