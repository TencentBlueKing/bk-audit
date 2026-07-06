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
  specific language governing permissions and limitations
  under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div class="visible-range-wrapper">
    <div
      ref="selectorRef"
      class="visible-range-selector"
      @click="togglePopover">
      <!-- 已选标签展示区 -->
      <div
        ref="tagsWrapperRef"
        class="selected-tags-wrapper">
        <template v-if="formData.visibility_type === 'all_visible'">
          <bk-tag
            class="selected-tag"
            closable
            theme="default"
            @click.stop
            @close.stop="handleClearAll">
            {{ t('全部可见') }}
          </bk-tag>
        </template>
        <template v-else>
          <!-- 可见 tag（按宽度动态计算） -->
          <bk-tag
            v-for="tag in visibleTags"
            :key="tag.key"
            class="selected-tag"
            closable
            :data-key="tag.key"
            theme="default"
            @click.stop
            @close.stop="handleTagRemove(tag)">
            {{ tag.name }}
          </bk-tag>

          <!-- 溢出 +n -->
          <span
            v-if="overflowCount > 0"
            v-bk-tooltips="{ content: overflowNames, theme: 'dark', placement: 'top-start' }"
            class="overflow-count">
            +{{ overflowCount }}
          </span>
        </template>
        <span
          v-if="formData.visibility_type !== 'all_visible' && allDisplayTags.length === 0"
          class="placeholder">
          {{ t('请选择') }}
        </span>
      </div>
      <audit-icon
        class="arrow-icon"
        :class="{ 'is-open': popoverVisible }"
        type="angle-line-down" />
    </div>

    <!-- 下拉面板 -->
    <teleport to="body">
      <div
        v-show="popoverVisible"
        ref="popoverRef"
        class="visible-range-popover"
        :style="popoverStyle"
        @mousedown.prevent>
        <!-- 全部可见 -->
        <div
          class="all-visible-row"
          :class="{ 'is-active': formData.visibility_type === 'all_visible' }"
          @click.stop="handleSelectAll">
          <img
            alt=""
            class="all-icon"
            src="@images/all.svg">
          <span class="all-text">{{ t('全部可见') }}</span>
          <audit-icon
            v-if="formData.visibility_type === 'all_visible'"
            class="check-icon"
            type="check-line" />
        </div>

        <!-- 两列选择区（每列独立滚动） -->
        <div class="range-columns">
          <!-- 审计场景 -->
          <div class="range-column">
            <div class="column-title">
              {{ t('审计场景') }}
            </div>
            <div class="column-list">
              <div
                class="checkbox-item"
                :class="{
                  'is-checked': isAllSceneChecked,
                  'is-disabled': formData.visibility_type === 'all_visible',
                }"
                @click.stop="formData.visibility_type !== 'all_visible' && handleToggleAllScenes()">
                <img
                  alt=""
                  class="item-icon scene-icon"
                  src="@images/scene.svg">
                <span class="checkbox-label">{{ t('全部场景') }}</span>
                <audit-icon
                  v-if="isAllSceneChecked"
                  class="check-icon"
                  type="check-line" />
              </div>
              <div
                v-for="scene in sceneList"
                :key="scene.id"
                class="checkbox-item"
                :class="{
                  'is-checked': isSceneChecked(scene.id),
                  'is-disabled': isAllSceneChecked || formData.visibility_type === 'all_visible',
                }"
                @click.stop="
                  !isAllSceneChecked
                    && formData.visibility_type !== 'all_visible'
                    && handleSceneToggle(scene.id)">
                <img
                  alt=""
                  class="item-icon scene-icon"
                  src="@images/scene.svg">
                <!-- eslint-disable-next-line max-len -->
                <span
                  v-bk-tooltips="{
                    content: scene.name,
                    theme: 'dark',
                    placement: 'top-start',
                    disabled: !isLabelOverflowing('scene-' + scene.id),
                  }"
                  class="checkbox-label"
                  :data-scene-id="scene.id">
                  {{ scene.name }}
                </span>
                <audit-icon
                  v-if="isSceneChecked(scene.id)"
                  class="check-icon"
                  type="check-line" />
              </div>
            </div>
          </div>

          <!-- 接入系统 -->
          <div class="range-column">
            <div class="column-title">
              {{ t('接入系统') }}
            </div>
            <div class="column-list">
              <div
                class="checkbox-item"
                :class="{
                  'is-checked': isAllSystemChecked,
                  'is-disabled': formData.visibility_type === 'all_visible',
                }"
                @click.stop="formData.visibility_type !== 'all_visible' && handleToggleAllSystems()">
                <img
                  alt=""
                  class="item-icon system-icon"
                  src="@images/system.svg">
                <span class="checkbox-label">{{ t('全部系统') }}</span>
                <audit-icon
                  v-if="isAllSystemChecked"
                  class="check-icon"
                  type="check-line" />
              </div>
              <div
                v-for="system in systemList"
                :key="system.id"
                class="checkbox-item"
                :class="{
                  'is-checked': isSystemChecked(system.id),
                  'is-disabled': isAllSystemChecked || formData.visibility_type === 'all_visible',
                }"
                @click.stop="
                  !isAllSystemChecked
                    && formData.visibility_type !== 'all_visible'
                    && handleSystemToggle(system.id)">
                <img
                  alt=""
                  class="item-icon system-icon"
                  src="@images/system.svg">
                <!-- eslint-disable-next-line max-len -->
                <span
                  v-bk-tooltips="{
                    content: system.name,
                    theme: 'dark',
                    placement: 'top-start',
                    disabled: !isLabelOverflowing('system-' + system.id),
                  }"
                  class="checkbox-label"
                  :data-system-id="system.id">
                  {{ system.name }}
                </span>
                <audit-icon
                  v-if="isSystemChecked(system.id)"
                  class="check-icon"
                  type="check-line" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';
  import SceneManageService from '@service/scene-manage';

  import type { FormData } from '@views/platform-manage/tool-manage/create-tool/types';

  interface OptionItem {
    id: number;
    name: string;
  }

  interface SystemOptionItem {
    id: string;
    name: string;
  }

  interface DisplayTag {
    key: string;
    id: number | string;
    name: string;
    type: 'scene' | 'system' | 'all-scene' | 'all-system';
  }

  // 后端 visibility_type 枚举值：
  //   all_visible=全部可见, all_scenes=全部场景, all_systems=全系统,
  //   specific_scenes=指定场景, specific_systems=指定系统, scenes_and_systems=场景和系统

  const props = defineProps<{
    formData: FormData;
  }>();

  const emit = defineEmits<{(e: 'update:formData', value: FormData): void}>();

  const { t } = useI18n();

  const popoverVisible = ref(false);
  const selectorRef = ref<HTMLElement | null>(null);
  const tagsWrapperRef = ref<HTMLElement | null>(null);
  const popoverRef = ref<HTMLElement | null>(null);
  const popoverStyle = reactive({ top: '0px', left: '0px' });

  // 动态计算可显示的 tag 数量
  const visibleCount = ref(999);

  const sceneList = ref<OptionItem[]>([]);
  const systemList = ref<SystemOptionItem[]>([]);

  // 加载场景列表
  const loadSceneList = async () => {
    try {
      const data = await SceneManageService.fetchSceneAll({ status: 'enabled' });
      sceneList.value = (data || []).map((item: { scene_id: number; name: string }) => ({
        id: item.scene_id,
        name: item.name,
      }));
    } catch {
      sceneList.value = [];
    }
  };

  // 加载系统列表
  const loadSystemList = async () => {
    try {
      const data = await MetaManageService.fetchSystemWithAction({
        audit_status__in: 'accessed',
        namespace: 'default',
      });
      systemList.value = (data || []).map(item => ({
        id: item.system_id || item.id,
        name: item.name,
      }));
    } catch {
      systemList.value = [];
    }
  };

  // 根据场景/系统的选择状态计算正确的 visibility_type
  const computeVisibilityType = (
    sceneIds: number[],
    systemIds: string[],
  ): FormData['visibility_type'] => {
    const hasScenes = sceneIds.length > 0;
    const hasSystems = systemIds.length > 0;
    const isAllScenes = sceneList.value.length > 0 && sceneIds.length === sceneList.value.length;
    const isAllSystems = systemList.value.length > 0 && systemIds.length === systemList.value.length;

    if (isAllScenes && isAllSystems) {
      return 'all_visible';
    }
    if (isAllScenes && !hasSystems) {
      return 'all_scenes';
    }
    if (!hasScenes && isAllSystems) {
      return 'all_systems';
    }
    if (hasScenes && hasSystems) {
      return 'scenes_and_systems';
    }
    if (hasScenes && !hasSystems) {
      // 场景全选时用 all_scenes，否则用 specific_scenes
      return isAllScenes ? 'all_scenes' : 'specific_scenes';
    }
    if (!hasScenes && hasSystems) {
      // 系统全选时用 all_systems，否则用 specific_systems
      return isAllSystems ? 'all_systems' : 'specific_systems';
    }
    // 都没选，默认 scenes_and_systems
    return 'scenes_and_systems';
  };

  // 是否选中了全部场景
  const isAllSceneChecked = computed(() => {
    if (props.formData.visibility_type === 'all_visible') return false;
    if (props.formData.visibility_type === 'all_scenes') return true;
    if (sceneList.value.length === 0) return false;
    return props.formData.scene_ids?.length === sceneList.value.length;
  });

  // 是否选中了全部系统
  const isAllSystemChecked = computed(() => {
    if (props.formData.visibility_type === 'all_visible') return false;
    if (props.formData.visibility_type === 'all_systems') return true;
    if (systemList.value.length === 0) return false;
    return props.formData.system_ids?.length === systemList.value.length;
  });

  // 所有 tag 统一列表
  const allDisplayTags = computed<DisplayTag[]>(() => {
    if (props.formData.visibility_type === 'all_visible') return [];
    const tags: DisplayTag[] = [];

    if (isAllSceneChecked.value) {
      tags.push({ key: 'all-scene', id: -1, name: t('全部场景'), type: 'all-scene' });
    } else {
      (props.formData.scene_ids || []).forEach((id) => {
        const item = sceneList.value.find(s => s.id === id);
        if (item) tags.push({ key: `scene-${item.id}`, id: item.id, name: item.name, type: 'scene' });
      });
    }

    if (isAllSystemChecked.value) {
      tags.push({ key: 'all-system', id: -2, name: t('全部系统'), type: 'all-system' });
    } else {
      (props.formData.system_ids || []).forEach((id) => {
        const item = systemList.value.find(s => s.id === id);
        if (item) tags.push({ key: `system-${item.id}`, id: item.id, name: item.name, type: 'system' });
      });
    }

    return tags;
  });

  // 按 visibleCount 截断的可见 tags
  const visibleTags = computed(() => allDisplayTags.value.slice(0, visibleCount.value));

  // 溢出数量和名称
  const overflowCount = computed(() => Math.max(0, allDisplayTags.value.length - visibleCount.value));
  const overflowNames = computed(() => allDisplayTags.value.slice(visibleCount.value).map(t => t.name)
    .join('、'));

  // 下拉选项 label 溢出检测（仅截断时显示 tooltip）
  const labelOverflowMap = reactive<Record<string, boolean>>({});
  const checkLabelOverflow = () => {
    const popover = popoverRef.value;
    if (!popover) return;

    // 检测场景和系统 label 是否溢出
    popover.querySelectorAll<HTMLElement>('.checkbox-label').forEach((el) => {
      let key: string | null = null;
      // 从 data 属性获取唯一标识
      if (el.hasAttribute('data-scene-id')) {
        key = `scene-${el.getAttribute('data-scene-id')}`;
      } else if (el.hasAttribute('data-system-id')) {
        key = `system-${el.getAttribute('data-system-id')}`;
      }
      if (!key) return;
      labelOverflowMap[key] = el.scrollWidth > el.clientWidth + 1;
    });
  };

  // 判断指定 label 是否溢出
  const isLabelOverflowing = (key: string) => !!labelOverflowMap[key];

  // 根据 wrapper 宽度动态计算能放几个 tag
  const calcVisibleCount = () => {
    const wrapper = tagsWrapperRef.value;
    if (!wrapper) return;

    const availableWidth = wrapper.clientWidth; // 减去 padding 和箭头预留
    let totalWidth = 8; // 左右 padding
    const overflowExtra = 36; // "+n" 预留宽度

    for (let i = 0; i < allDisplayTags.value.length; i++) {
      // 估算每个 tag 宽度：文字宽度约 12px/字符 + tag 内边距 ~32px + 关闭按钮 ~20px
      const textLen = allDisplayTags.value[i].name.length;
      const tagEstimateWidth = textLen * 12 + 52;
      totalWidth += tagEstimateWidth + 4; // gap

      if (totalWidth > availableWidth - overflowExtra) {
        // 至少显示 1 个
        visibleCount.value = Math.max(1, i);
        return;
      }
    }

    visibleCount.value = allDisplayTags.value.length;
  };

  // 监听变化重新计算和检测
  watch([allDisplayTags, () => popoverVisible.value], () => {
    nextTick(() => {
      calcVisibleCount();
      checkLabelOverflow();
    });
  });

  const handleTagRemove = (tag: DisplayTag) => {
    switch (tag.type) {
    case 'all-scene':
      handleToggleAllScenes();
      break;
    case 'all-system':
      handleToggleAllSystems();
      break;
    case 'scene':
      if (typeof tag.id === 'number') {
        handleSceneToggle(tag.id);
      }
      break;
    case 'system':
      if (typeof tag.id === 'string') {
        handleSystemToggle(tag.id);
      }
      break;
    }
  };

  const isSceneChecked = (id: number) => (props.formData.scene_ids || []).includes(id);
  const isSystemChecked = (id: string) => (props.formData.system_ids || []).includes(id);

  const updatePopoverPosition = () => {
    nextTick(() => {
      const el = selectorRef.value;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      popoverStyle.top = `${rect.bottom + 4}px`;
      popoverStyle.left = `${rect.left}px`;
    });
  };

  const togglePopover = () => {
    popoverVisible.value = !popoverVisible.value;
    if (popoverVisible.value) {
      updatePopoverPosition();
    }
  };

  const handleSelectAll = () => {
    if (props.formData.visibility_type === 'all_visible') {
      // 已选中 → 取消，清空选择
      emit('update:formData', {
        ...props.formData,
        visibility_type: 'scenes_and_systems',
        scene_ids: [],
        system_ids: [],
      });
    } else {
      // 未选中 → 设为全部可见
      emit('update:formData', {
        ...props.formData,
        visibility_type: 'all_visible',
        scene_ids: [],
        system_ids: [],
      });
    }
  };

  const handleClearAll = () => {
    emit('update:formData', {
      ...props.formData,
      visibility_type: 'scenes_and_systems',
      scene_ids: [],
      system_ids: [],
    });
  };

  const handleToggleAllScenes = () => {
    if (isAllSceneChecked.value) {
      // 取消全选场景 → 清空 scene_ids，重新计算类型
      const newSceneIds: number[] = [];
      const newType = computeVisibilityType(newSceneIds, props.formData.system_ids || []);
      emit('update:formData', {
        ...props.formData,
        visibility_type: newType,
        scene_ids: newSceneIds,
      });
    } else {
      // 全选场景 → 直接设为 all_scenes 类型，后端根据类型判定全部场景可见
      emit('update:formData', {
        ...props.formData,
        visibility_type: 'all_scenes',
        scene_ids: [],
      });
    }
  };

  const handleToggleAllSystems = () => {
    if (isAllSystemChecked.value) {
      // 取消全选系统 → 清空 system_ids，重新计算类型
      const newSystemIds: string[] = [];
      const newType = computeVisibilityType(props.formData.scene_ids || [], newSystemIds);
      emit('update:formData', {
        ...props.formData,
        visibility_type: newType,
        system_ids: newSystemIds,
      });
    } else {
      // 全选系统 → 直接设为 all_systems 类型，后端根据类型判定全部系统可见
      emit('update:formData', {
        ...props.formData,
        visibility_type: 'all_systems',
        system_ids: [],
      });
    }
  };

  const handleSceneToggle = (id: number) => {
    const currentScenes = [...(props.formData.scene_ids || [])];
    const idx = currentScenes.indexOf(id);
    if (idx > -1) {
      currentScenes.splice(idx, 1);
    } else {
      currentScenes.push(id);
    }
    const newType = computeVisibilityType(currentScenes, props.formData.system_ids || []);
    emit('update:formData', {
      ...props.formData,
      visibility_type: newType,
      scene_ids: currentScenes,
    });
  };

  const handleSystemToggle = (id: string) => {
    const currentSystems = [...(props.formData.system_ids || [])];
    const idx = currentSystems.indexOf(id);
    if (idx > -1) {
      currentSystems.splice(idx, 1);
    } else {
      currentSystems.push(id);
    }
    const newType = computeVisibilityType(props.formData.scene_ids || [], currentSystems);
    emit('update:formData', {
      ...props.formData,
      visibility_type: newType,
      system_ids: currentSystems,
    });
  };

  // 点击浮层外部关闭
  const handleClickOutside = (e: MouseEvent) => {
    if (!popoverVisible.value) return;
    const target = e.target as Node;
    if (
      selectorRef.value && !selectorRef.value.contains(target)
      && popoverRef.value && !popoverRef.value.contains(target)
    ) {
      popoverVisible.value = false;
    }
  };

  const handleScrollOrResize = () => {
    if (popoverVisible.value) {
      updatePopoverPosition();
    }
    calcVisibleCount();
    checkLabelOverflow();
  };

  watch(popoverVisible, (val) => {
    if (val) {
      nextTick(() => updatePopoverPosition());
    }
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleClickOutside, true);
    window.removeEventListener('scroll', handleScrollOrResize, true);
    window.removeEventListener('resize', handleScrollOrResize);
  });

  onMounted(() => {
    document.addEventListener('click', handleClickOutside, true);
    window.addEventListener('scroll', handleScrollOrResize, true);
    window.addEventListener('resize', handleScrollOrResize);
    loadSceneList();
    loadSystemList();
  });
</script>

<style lang="postcss" scoped>
  .visible-range-wrapper {
    display: inline-block;
    width: 100%;
  }

  .visible-range-selector {
    display: flex;
    align-items: center;
    width: 100%;
    min-height: 32px;
    padding: 0 8px;
    cursor: pointer;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    transition: border-color .2s;

    &:hover {
      border-color: #3a84ff;
    }

    &.is-focus {
      border-color: #3a84ff;
      outline: none;
    }
  }

  .selected-tags-wrapper {
    display: flex;
    flex: 1;
    flex-wrap: nowrap;
    gap: 4px;
    align-items: center;
    overflow: hidden;
  }

  .selected-tag {
    flex-shrink: 0;
    margin: 2px 0;
  }

  .overflow-count {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 22px;
    padding: 0 6px;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;
    cursor: default;
    background-color: #f0f1f5;
    border-radius: 2px;
    user-select: none;
  }

  .placeholder {
    font-size: 12px;
    line-height: 28px;
    color: #c4c6cc;
    flex-shrink: 0;
  }

  .arrow-icon {
    flex-shrink: 0;
    margin-left: 8px;
    font-size: 14px;
    color: #979ba5;
    transition: transform .2s;

    &.is-open {
      transform: rotate(180deg);
    }
  }
</style>

<!-- 浮层全局样式（Teleport 到 body，不受 scoped 约束） -->
<style lang="postcss">
  .visible-range-popover {
    position: fixed;
    z-index: 2100;
    width: 640px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-shadow: 0 4px 16px 0 rgb(25 25 41 / 10%);
    box-sizing: border-box;
  }

  /* ALL 全部可见 */
  .all-visible-row {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 13px 15px;
    cursor: pointer;
    border-bottom: 1px solid #f0f1f5;

    &:hover {
      color: #3a84ff;
      background-color: #f5f7fa;
    }

    &.is-active {
      color: #3a84ff;
    }

    .all-icon {
      width: 16px;
      height: 16px;
      opacity: 75%;
    }

    .all-label {
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 1px;
    }

    .all-text {
      flex: 1;
      font-size: 12px;
      color: #4d4f56;
    }

    .check-icon {
      flex-shrink: 0;
      font-size: 18px;
      color: #3a84ff;
    }
  }

  /* 两列布局 */
  .range-columns {
    display: flex;
    padding: 12px 0 12px 12px;
  }

  .range-column {
    flex: 1;
    min-width: 0;

    & + & {
      padding-left: 12px;
      border-left: 1px solid #f0f1f5;
    }
  }

  .column-title {
    padding-top: 4px;
    margin-bottom: 8px;
    font-size: 12px;
    font-weight: 500;
    color: #979ba5;
  }

  /* 每列独立滚动 */
  .column-list {
    max-height: 300px;
    overflow: hidden auto;

    /* 细滚动条样式 */
    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background-color: #c4c6cc;
      border-radius: 2px;

      &:hover {
        background-color: #979ba5;
      }
    }

    &::-webkit-scrollbar-track {
      background-color: transparent;
    }
  }

  /* 复选项行 */
  .checkbox-item {
    display: flex;
    gap: 8px;
    align-items: center;
    height: 36px;
    padding: 0 4px;
    font-size: 12px;
    color: #4d4f56;
    cursor: pointer;
    border-radius: 2px;
    user-select: none;

    &:hover:not(.is-disabled) {
      background-color: #f5f7fa;
    }

    &.is-checked {
      color: #3a84ff;
    }

    &.is-disabled {
      color: #c4c6cc;
      cursor: not-allowed;
      opacity: 60%;

      &:hover {
        background-color: transparent;
      }
    }

    .item-icon {
      width: 16px;
      height: 16px;
      flex-shrink: 0;
    }

    .checkbox-label {
      flex: 1;
      overflow: hidden;
      font-size: 12px;
      line-height: 36px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .check-icon {
      flex-shrink: 0;
      margin-left: auto;
      font-size: 18px;
      color: #3a84ff;
    }
  }
</style>
