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
  <div>
    <bk-popover
      ext-cls="add-search-popover"
      :is-show="isShow"
      placement="bottom"
      style="padding: 0;"
      theme="light"
      trigger="click"
      @after-hidden="handleAfterHidden">
      <span
        class="add-search-icon">
        <audit-icon
          style="margin-right: 5px;"
          type="add" />
        <span>{{ t('添加其他条件') }}</span>
      </span>
      <template #content>
        <div class="add-search-content">
          <div style="width: 290px; padding: 0 8px;">
            <bk-input
              v-model="searchKeyword"
              behavior="simplicity"
              class="mb8"
              placeholder="请输入关键字">
              <template #prefix>
                <div style="line-height: 30px;">
                  <audit-icon
                    type="search1" />
                </div>
              </template>
            </bk-input>
          </div>

          <div class="add-search-cascader">
            <template v-if="renderPanels.length">
              <scroll-faker
                v-for="(node, level) in renderPanels"
                :key="level"
                class="add-search-cascader-panel"
                :class="{'add-search-cascader-panel-child': level > 0}">
                <ul>
                  <li
                    v-for="(item, index) in node.data"
                    :key="index"
                    class="add-search-cascader-node"
                    :class="{
                      'active': selectedItems[item.id],
                      'disabled': item.disabled
                    }"
                    @mouseenter="handleNodeHover(item, index, level)">
                    <div style="display: flex; align-items: center;">
                      <bk-checkbox
                        v-model="selectedItems[item.id]"
                        class="mr8"
                        :disabled="item.disabled"
                        :indeterminate="indeterminateItems[item.id]"
                        @change="handleCheckboxChange(item)" />
                      <span>{{ item.name }}</span>
                    </div>
                    <audit-icon
                      v-if="item.children && item.children.length || item.dynamic_content"
                      class="add-search-cascader-icon"
                      type="angle-line-up" />
                  </li>
                </ul>
                <!-- 新增：如果是二级及以上，且父节点 dynamic_content 为 true，显示添加按钮 -->
                <template v-if="level > 0 && hoverItem && hoverItem.dynamic_content">
                  <div class="add-search-cascader-bottom">
                    <div
                      v-if="!showAdd"
                      style="
                        height: 40px;
                        line-height: 40px;color: #63656e;
                        text-align: center;
                        cursor: pointer;
                        flex: 1;"
                      @click="() => showAdd = true">
                      <audit-icon
                        style="margin-right: 5px;
                          font-size: 14px;
                          color: #979ba5;"
                        type="plus-circle" />
                      <span>{{ t('自定义字段') }}</span>
                    </div>
                    <div
                      v-else
                      style="padding: 12px;">
                      <bk-input
                        v-model="customFields"
                        autofocus
                        :placeholder="t('输入字段ID，多级字段使用“/”分隔')"
                        @enter="confirmAdd" />
                      <bk-input
                        v-model="remark"
                        :placeholder="t('输入备注（非必填）')"
                        style="margin-top: 8px;"
                        @enter="confirmAdd" />
                      <div style="margin-top: 8px; text-align: right;">
                        <bk-button
                          class="mr8"
                          :disabled="!customFields"
                          size="small"
                          theme="primary"
                          @click="confirmAdd">
                          {{ t('确定') }}
                        </bk-button>
                        <bk-button
                          size="small"
                          @click="() => showAdd = false">
                          {{ t('取消') }}
                        </bk-button>
                      </div>
                    </div>
                  </div>
                </template>
              </scroll-faker>
            </template>
            <bk-exception
              v-else-if="isSearching"
              scene="part"
              style="height: 200px;"
              type="search-empty">
              <div>
                <div style="color: #63656e;">
                  {{ t('搜索结果为空') }}
                </div>
                <div style="margin-top: 8px; color: #979ba5;">
                  {{ t('可以尝试调整关键词') }} {{ t('或') }}
                  <bk-button
                    text
                    theme="primary"
                    @click="handleClearSearch">
                    {{ t('清空搜索条件') }}
                  </bk-button>
                </div>
              </div>
            </bk-exception>
            <bk-exception
              v-else
              class="exception-part"
              scene="part"
              type="empty">
              {{ t('暂无数据') }}
            </bk-exception>
          </div>
        </div>
      </template>
    </bk-popover>
  </div>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useDebouncedRef from '@/hooks/use-debounced-ref';

  interface CascaderItem {
    id: string | number;
    name: string;
    disabled: boolean;
    children: CascaderItem[];
    dynamic_content?: boolean;
  }

  interface Props {
    data: CascaderItem[];
    modelValue?: Record<string, boolean>;
  }

  interface Emits {
    (e: 'update:modelValue', value: Record<string, boolean>): void;
    (e: 'select', item: CascaderItem): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const isShow = ref(false);
  const renderPanels = ref<Array<{
    parent: CascaderItem | null;
    data: CascaderItem[];
  }>>([]);

  const searchKeyword = useDebouncedRef('');
  const isSearching = ref(false);

  const selectedItems = ref<Record<string, boolean>>({});
  const indeterminateItems = ref<Record<string, boolean>>({});

  const hoverItem = ref<CascaderItem | null>(null);
  const hoverLevel = ref<number>(-1);

  const showAdd = ref(false);
  const customFields = ref('');
  const remark = ref('');

  // 新增方法
  const confirmAdd = () => {
    // 以 / 分割 customFields，支持多级
    const fields = customFields.value.split('/').map(f => f.trim())
      .filter(Boolean);
    if (!fields.length) return;

    const currentPanel = renderPanels.value[renderPanels.value.length - 1];
    let children = currentPanel.data;

    fields.forEach((field) => {
      let exist = children.find(item => item.id === field);
      if (!exist) {
        exist = {
          id: field,
          name: field,
          disabled: false,
          children: [],
          dynamic_content: true,
        };
        children.push(exist);
      }
      children = exist.children;
    });

    // 重置数据
    customFields.value = '';
    remark.value = '';
    showAdd.value = false;
  };

  // 弹出层隐藏后的处理
  const handleAfterHidden = (value: { isShow: boolean}) => {
    isShow.value = value.isShow;
    if (!value.isShow) {
      // 重置面板状态，只保留第一级
      renderPanels.value = [{
        parent: null,
        data: props.data,
      }];
      searchKeyword.value = '';
      isSearching.value = false;
    }
  };

  // 处理任意级别节点的hover
  const handleNodeHover = (item: CascaderItem, index: number, level: number) => {
    // 阻止事件冒泡，避免触发父节点的事件
    event?.stopPropagation();
    // 如果项目被禁用，则不处理hover事件
    if (item.disabled) return;

    hoverItem.value = item;
    hoverLevel.value = level;

    // 如果hover的节点有子节点
    if ((item.children && item.children.length) || item.dynamic_content) {
      // 截断当前级别之后的所有面板
      renderPanels.value = renderPanels.value.slice(0, level + 1);

      // 添加新的面板到激活面板列表
      renderPanels.value.push({
        parent: item,
        data: item.children || [],
      });
    } else {
      // 如果hover到没有children的节点，截断当前级别之后的所有面板
      renderPanels.value = renderPanels.value.slice(0, level + 1);
    }
  };

  // 递归设置父节点半选
  const updateIndeterminateStatus = (nodes: CascaderItem[], parent?: CascaderItem) => {
    nodes.forEach((node) => {
      if (node.children && node.children.length) {
        updateIndeterminateStatus(node.children, node);
        const total = node.children.length;
        const checked = node.children.filter(child => selectedItems.value[child.id]).length;
        if (checked === 0) {
          indeterminateItems.value[node.id] = false;
        } else if (checked === total) {
          indeterminateItems.value[node.id] = false;
          selectedItems.value[node.id] = true;
        } else {
          indeterminateItems.value[node.id] = true;
          selectedItems.value[node.id] = false;
        }
      }
    });
    // 递归向上处理父节点
    if (parent) {
      const total = parent.children.length;
      const checked = parent.children.filter(child => selectedItems.value[child.id]).length;
      if (checked === 0) {
        indeterminateItems.value[parent.id] = false;
      } else if (checked === total) {
        indeterminateItems.value[parent.id] = false;
        selectedItems.value[parent.id] = true;
      } else {
        indeterminateItems.value[parent.id] = true;
        selectedItems.value[parent.id] = false;
      }
    }
  };

  // 处理复选框变化
  const handleCheckboxChange = (item: CascaderItem) => {
    emits('update:modelValue', selectedItems.value);
    emits('select', item);
    updateIndeterminateStatus(props.data);
  };

  const handleClearSearch = () => {
    searchKeyword.value = '';
    isSearching.value = false;
  };

  // 同步外部值的改动
  watch(() => props.modelValue, (newVal) => {
    selectedItems.value = { ...newVal };
  }, {
    immediate: true,
  });

  watch(() => searchKeyword.value, (newVal) => {
    if (!newVal) {
      renderPanels.value = [{
        parent: null,
        data: props.data,
      }];
      isSearching.value = false;
      return;
    }

    // 搜索过滤逻辑，递归收集所有匹配节点的路径，自动展开所有层级
    const matchedPaths: CascaderItem[][] = [];
    function findMatchedPaths(nodes: CascaderItem[], path: CascaderItem[] = []): boolean {
      for (const node of nodes) {
        const currentPath = [...path, node];
        const isMatch = node.name.includes(searchKeyword.value);
        let childrenMatched = false;
        if (node.children && node.children.length) {
          childrenMatched = findMatchedPaths(node.children, currentPath);
        }
        if (isMatch || childrenMatched) {
          matchedPaths.push(currentPath);
        }
      }
      // 返回本层是否有匹配
      return matchedPaths.some(p => p.length && nodes.includes(p[path.length]));
    }
    findMatchedPaths(props.data);

    // 构造每一级面板展开内容
    const panels: Map<string | number, CascaderItem>[] = [];
    for (const path of matchedPaths) {
      path.forEach((node, level) => {
        if (!panels[level]) panels[level] = new Map<string | number, CascaderItem>();
        panels[level].set(node.id, node);
      });
    }
    const newPanels: Array<{parent: CascaderItem | null, data: CascaderItem[]}> = [];
    // 第一级特殊处理，parent 为 null
    if (panels.length > 0) {
      newPanels.push({
        parent: null,
        data: Array.from(panels[0].values()),
      });

      // 处理后续级别
      for (let level = 1; level < panels.length; level++) {
        newPanels.push({
          parent: Array.from(panels[level - 1].values())[0], // 简化处理，取上一级第一个元素作为父节点
          data: Array.from(panels[level].values()),
        });
      }
    }
    renderPanels.value = newPanels;
    isSearching.value = true;
  });

  // 初始化面板数据
  watch(
    () => props.data,
    (newVal) => {
      // 初始化第一级面板
      renderPanels.value = [{
        parent: null,
        data: newVal,
      }];
    },
    { immediate: true },
  );
</script>

<style lang="postcss">
  .add-search-popover {
    padding: 0 !important;
  }

  .add-search-icon {
    color: #3a84ff;
    cursor: pointer;
  }

  .add-search-content {
    min-width: 290px;

    .add-search-cascader {
      display: flex;
      height: 350px;
    }

    .add-search-cascader-panel {
      position: relative;
      height: 350px;
      min-width: 290px;
      padding: 4px 0;
      background-color: #fff;

      &.add-search-cascader-panel-child {
        height: 385px !important;
        border-left: 1px solid #eee;
        transform: translateY(-35px);
      }

      .add-search-cascader-node {
        display: flex;
        padding: 0 8px;
        overflow: hidden;
        line-height: 32px;
        text-overflow: ellipsis;
        white-space: nowrap;
        cursor: pointer;
        align-items: center;
        justify-content: space-between;

        &:hover {
          background-color: #f5f7fa;
        }

        &.active {
          color: #3a84ff;
        }

        &.disabled {
          color: #c4c6cc;
          cursor: not-allowed;
          background-color: #fff;
        }

        .add-search-cascader-icon {
          color: #979ba5;
          transform: rotate(90deg);
        }
      }

      .add-search-cascader-bottom {
        position: absolute;
        bottom: 0;
        left: 0;
        z-index: 10;
        width: 100%;
        color: #63656e;
        text-align: center;
        cursor: pointer;
        background: #fafbfd;;
        border-top: 1px solid #f0f1f5;
      }
    }
  }
</style>
