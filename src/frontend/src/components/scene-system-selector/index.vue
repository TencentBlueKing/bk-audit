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
        <div
          v-if="listScope.includes('scene')"
          class="dropdown-group">
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
              <show-tooltips-text
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }"
                :data="item.type !== 'aggregate' ? `${item.name}(${item.id})` : item.name" />
            </div>
          </div>
        </div>

        <!-- 接入系统分组 -->
        <div
          v-if="listScope.includes('system')"
          class="dropdown-group">
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
              <show-tooltips-text
                class="item-name"
                :class="{ 'is-highlight': item.type !== 'aggregate' }"
                :data="item.type !== 'aggregate' ? `${item.name}(${item.id})` : item.name" />
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
    onMounted,
    onUnmounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';
  import sceneManageService from '@service/scene-manage';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  import useRequest from '@/hooks/use-request';

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
    listScope?:  string[],
    systemPermission: 'edit_system' | 'view_system';
    scenePermission: 'manage_scene' | 'view_scene';
    isAllSystem?: boolean; // 是否展示全部接入系统
    isAllSecen?: boolean; // 是否展示全部审计场景
    isDefaultSelectFirst?: boolean; // 是否默认选中第一个场景（优先级低于外部传入的值和sessionStorage存储的值）
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
    listScope: () => ['scene', 'system'],
    isAllSecen: true,
    isAllSystem: true,
    isDefaultSelectFirst: false,
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const popoverRef = ref();
  const isPopoverShow = ref(false);
  const selectedItem = ref<SelectorItem | null>(props.modelValue);

  // 假数据 - 审计场景列表
  const sceneList = ref<SelectorItem[]>([]);

  // 假数据 - 接入系统列表
  const systemList = ref<SelectorItem[]>([]);

  // 显示文本
  const displayText = computed(() => {
    if (!selectedItem.value) {
      return t('请选择');
    }
    const { name, id, type } = selectedItem.value;
    return (id && type !== 'aggregate') ? `${name}(${id})` : name;
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

  const STORAGE_KEY = 'scene-system-selector:selected';

  // 选择项目
  const handleSelect = (item: SelectorItem) => {
    selectedItem.value = item;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(item));
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

  // 获取系统列表
  const {
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    onSuccess: (data: any[]) => {
      const list = data
        .filter(item => item.permission && item.permission[props.systemPermission] === true)
        .map(item => ({
          id: item.system_id,
          name: item.name,
          type: 'system' as const,
        }));
      systemList.value = props.isAllSystem ? [{ id: 'allSystem', name: t('我的所有系统'), type: 'aggregate' }, ...list] : list;
    },
  });
  // 获取场景列表
  const {
    run: fetchSceneAll,
  } = useRequest(sceneManageService.fetchSceneAll, {
    defaultValue: [],
    onSuccess: (data: any[]) => {
      const list = data
        .filter(item => item.permission && item.permission[props.scenePermission] === true)
        .map(item => ({
          id: String(item.scene_id),
          name: item.name,
          type: 'scene' as const,
        }));
      sceneList.value = props.isAllSecen ? [{ id: 'allSecen', name: t('我的所有场景'), type: 'aggregate' }, ...list] : list;
      // 默认选中逻辑：isDefaultSelectFirst 为 true 时优先选中第一个非聚合场景，否则有存储值则用存储值，没有则默认选中第一个非聚合的场景
      if (!selectedItem.value && list.length > 0) {
        // 先尝试从sessionStorage获取存储的值
        const storedValue = sessionStorage.getItem(STORAGE_KEY);
        let targetItem = null;
        if (props.isDefaultSelectFirst) {
          // isDefaultSelectFirst 为 true 时，优先选中第一个非聚合的场景
          [targetItem] = list;
        } else if (storedValue) {
          try {
            targetItem = JSON.parse(storedValue);
          } catch (e) {
            // 解析失败，使用第一个非聚合的场景
            [targetItem] = list;
          }
        } else {
          // 没有存储值，使用第一个非聚合的场景
          [targetItem] = list;
        }
        // 设置选中项并触发事件
        selectedItem.value = targetItem;
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(targetItem));
        emits('update:modelValue', targetItem);
        emits('change', targetItem);
      }
    },
  });
  // 监听外部值变化
  watch(() => props.modelValue, (newVal) => {
    selectedItem.value = newVal;
  });

  // 获取数据的方法
  const fetchData = () => {
    setTimeout(() => {
      fetchSystemWithAction({
        action_ids: 'view_system,edit_system',
        audit_status__in: 'accessed',
        namespace: 'default',
        order_type: 'asc',
        sort_keys: 'name',
        with_favorite: false,
        with_system_status: false,
      });
      fetchSceneAll({
        status: 'enabled',
      });
      emits('change', selectedItem.value);
    }, 0);
  };

  onMounted(() => {
    fetchData();

    // 监听路由变化，当路由变化时重新获取数据
    // router.afterEach((to, from) => {
    //   // 只有当路由真正发生变化时才重新获取数据
    //   if (to.fullPath !== from.fullPath) {
    //     fetchData();
    //   }
    // });
  });

  onUnmounted(() => {
    // 清理路由监听器（如果需要的话）
    // 通常不需要手动清理，因为router.afterEach返回的函数会在组件卸载时自动清理
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

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #c4c6cc;
    border-radius: 2px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #979ba5;
  }

  /* 深色主题 */
  &.is-dark {
    background: #1a2233;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: #2e3847;
      border-radius: 2px;
    }

    &::-webkit-scrollbar-thumb:hover {
      background: #3c4558;
    }

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
