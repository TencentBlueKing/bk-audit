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
  <div class="visibility-menu">
    <!-- 全部可见 -->
    <div
      class="menu-item"
      :class="{ 'is-checked': localState.all_visible }"
      @click="handleToggle('all_visible')">
      <span
        class="checkbox"
        :class="[{ 'is-checked': localState.all_visible }]">
        <!-- eslint-disable-next-line max-len -->
        <svg
          v-if="localState.all_visible"
          class="check-icon"
          viewBox="0 0 16 16">
          <!-- eslint-disable-next-line max-len -->
          <path d="M13.854 3.646a.5.5 0 010 .708l-7 7a.5.5 0 01-.708 0l-3.5-3.5a.5.5 0 11.708-.708L6.5 10.293l6.646-6.647a.5.5 0 01.708 0z" />
        </svg>
      </span>
      <bk-tooltip
        :content="t('全部可见')"
        placement="bottom"
        theme="dark">
        <span class="item-label">{{ t('全部可见') }}</span>
      </bk-tooltip>
    </div>

    <div class="menu-divider" />

    <!-- 场景组 -->
    <div class="group-header">
      {{ t('场景') }}
    </div>
    <div
      class="menu-item group-option"
      :class="{ 'is-checked': localState.all_scenes, 'is-disabled': localState.all_visible }"
      @click="!localState.all_visible && handleToggle('all_scenes')">
      <span
        class="checkbox"
        :class="[{ 'is-checked': localState.all_scenes }]">
        <!-- eslint-disable-next-line max-len -->
        <svg
          v-if="localState.all_scenes"
          class="check-icon"
          viewBox="0 0 16 16">
          <!-- eslint-disable-next-line max-len -->
          <path d="M13.854 3.646a.5.5 0 010 .708l-7 7a.5.5 0 01-.708 0l-3.5-3.5a.5.5 0 11.708-.708L6.5 10.293l6.646-6.647a.5.5 0 01.708 0z" />
        </svg>
      </span>
      <bk-tooltip
        :content="t('全部场景')"
        placement="bottom"
        theme="dark">
        <span class="item-label">{{ t('全部场景') }}</span>
      </bk-tooltip>
    </div>
    <div
      v-for="item in sceneList"
      :key="'scene-' + item.id"
      class="menu-item sub-item"
      :class="{
        'is-checked': localState.scenes.includes(item.id),
        'is-disabled': localState.all_visible || localState.all_scenes,
      }"
      @click="handleSceneItemClick(item.id)">
      <span
        class="checkbox"
        :class="[{ 'is-checked': localState.scenes.includes(item.id) }]">
        <!-- eslint-disable-next-line max-len -->
        <svg
          v-if="localState.scenes.includes(item.id)"
          class="check-icon"
          viewBox="0 0 16 16">
          <!-- eslint-disable-next-line max-len -->
          <path d="M13.854 3.646a.5.5 0 010 .708l-7 7a.5.5 0 01-.708 0l-3.5-3.5a.5.5 0 11.708-.708L6.5 10.293l6.646-6.647a.5.5 0 01.708 0z" />
        </svg>
      </span>
      <bk-tooltip
        :content="item.name"
        placement="bottom"
        theme="dark">
        <span class="item-label">{{ item.name }}</span>
      </bk-tooltip>
    </div>

    <div class="menu-divider" />

    <!-- 系统组（平台） -->
    <div class="group-header">
      {{ t('平台') }}
    </div>
    <div
      class="menu-item group-option"
      :class="{ 'is-checked': localState.all_systems, 'is-disabled': localState.all_visible }"
      @click="!localState.all_visible && handleToggle('all_systems')">
      <span
        class="checkbox"
        :class="[{ 'is-checked': localState.all_systems }]">
        <!-- eslint-disable-next-line max-len -->
        <svg
          v-if="localState.all_systems"
          class="check-icon"
          viewBox="0 0 16 16">
          <!-- eslint-disable-next-line max-len -->
          <path d="M13.854 3.646a.5.5 0 010 .708l-7 7a.5.5 0 01-.708 0l-3.5-3.5a.5.5 0 11.708-.708L6.5 10.293l6.646-6.647a.5.5 0 01.708 0z" />
        </svg>
      </span>
      <bk-tooltip
        :content="t('全部系统')"
        placement="bottom"
        theme="dark">
        <span class="item-label">{{ t('全部系统') }}</span>
      </bk-tooltip>
    </div>
    <div
      v-for="item in systemList"
      :key="'system-' + item.id"
      class="menu-item sub-item"
      :class="{
        'is-checked': localState.systems.includes(item.id),
        'is-disabled': localState.all_visible || localState.all_systems,
      }"
      @click="handleSystemItemClick(item.id)">
      <span
        class="checkbox"
        :class="[{ 'is-checked': localState.systems.includes(item.id) }]">
        <!-- eslint-disable-next-line max-len -->
        <svg
          v-if="localState.systems.includes(item.id)"
          class="check-icon"
          viewBox="0 0 16 16">
          <!-- eslint-disable-next-line max-len -->
          <path d="M13.854 3.646a.5.5 0 010 .708l-7 7a.5.5 0 01-.708 0l-3.5-3.5a.5.5 0 11.708-.708L6.5 10.293l6.646-6.647a.5.5 0 01.708 0z" />
        </svg>
      </span>
      <bk-tooltip
        :content="item.name"
        placement="bottom"
        theme="dark">
        <span class="item-label">{{ item.name }}</span>
      </bk-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { watch, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface OptionItem {
    id: number;
    name: string;
  }

  interface SelectionState {
    all_visible: boolean;
    all_scenes: boolean;
    all_systems: boolean;
    scenes: number[];
    systems: number[];
  }

  const props = defineProps<{
    sceneList: OptionItem[];
    systemList: OptionItem[];
    modelValue: SelectionState;
  }>();

  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    (e: 'update:modelValue', value: SelectionState): void;
    (e: 'change', value: SelectionState): void;
  }>();

  const { t } = useI18n();

  // 使用本地状态确保勾选即时响应，不受父组件/bk-search-select 插槽更新时序影响
  const localState = ref<SelectionState>({
    all_visible: false,
    all_scenes: false,
    all_systems: false,
    scenes: [],
    systems: [],
  });

  // 同步外部 modelValue 到本地状态（初始化或外部重置时）
  watch(() => props.modelValue, (val) => {
    localState.value = {
      all_visible: val.all_visible,
      all_scenes: val.all_scenes,
      all_systems: val.all_systems,
      scenes: [...val.scenes],
      systems: [...val.systems],
    };
  }, { deep: true, immediate: true });

  // 同步到父组件 + 更新搜索框编辑态展示 + 触发搜索
  const syncToParent = () => {
    const newVal = { ...localState.value };
    emit('update:modelValue', newVal);
    emit('change', newVal);
  };

  const handleToggle = (type: keyof Pick<SelectionState, 'all_visible' | 'all_scenes' | 'all_systems'>) => {
    const current = localState.value;
    if (type === 'all_visible') {
      current.all_visible = !current.all_visible;
      if (current.all_visible) {
        current.all_scenes = false;
        current.all_systems = false;
        current.scenes = [];
        current.systems = [];
      }
    } else if (type === 'all_scenes') {
      current.all_scenes = !current.all_scenes;
      if (current.all_scenes) {
        current.scenes = [];
      }
    } else if (type === 'all_systems') {
      current.all_systems = !current.all_systems;
      if (current.all_systems) {
        current.systems = [];
      }
    }
    syncToParent();
  };

  const isSceneSubItemDisabled = () => (
    localState.value.all_visible || localState.value.all_scenes
  );

  const isSystemSubItemDisabled = () => (
    localState.value.all_visible || localState.value.all_systems
  );

  const handleSceneItemClick = (id: number) => {
    if (isSceneSubItemDisabled()) return;
    handleToggleItem('scenes', id);
  };

  const handleSystemItemClick = (id: number) => {
    if (isSystemSubItemDisabled()) return;
    handleToggleItem('systems', id);
  };

  const handleToggleItem = (field: 'scenes' | 'systems', id: number) => {
    const current = localState.value;
    const idx = current[field].indexOf(id);
    if (idx > -1) {
      current[field].splice(idx, 1);
    } else {
      current[field].push(id);
    }
    syncToParent();
  };
</script>

<style lang="postcss" scoped>
  .visibility-menu {
    width: 280px;
    max-height: 360px;
    padding: 2px 0;
    overflow: hidden auto;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background-color: #c4c6cc;
      border-radius: 2px;
    }

    &::-webkit-scrollbar-track {
      background-color: transparent;
    }
  }

  .group-header {
    padding: 6px 12px 2px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  .menu-item {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;

    &:hover:not(.is-disabled) {
      color: #3a84ff;
      background-color: #f5f7fa;
    }

    &.is-disabled {
      color: #c4c6cc;
      cursor: not-allowed;

      .checkbox {
        pointer-events: none;
        opacity: 50%;
      }

      &:hover {
        color: #c4c6cc;
        background-color: transparent;
      }
    }

    &.sub-item {
      padding-left: 28px;
    }

    .checkbox {
      width: 14px;
      height: 14px;
      margin-right: 8px;
      background-color: #fff;
      border: 1px solid #c4c6cc;
      border-radius: 2px;
      box-sizing: border-box;
      flex-shrink: 0;

      &.is-checked {
        background-color: #3a84ff;
        border-color: #3a84ff;
      }

      .check-icon {
        display: block;
        width: 12px;
        height: 12px;
        fill: #fff;
      }
    }

    .item-label {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .menu-divider {
    height: 1px;
    margin: 4px 0;
    background-color: #f0f1f5;
  }
</style>
