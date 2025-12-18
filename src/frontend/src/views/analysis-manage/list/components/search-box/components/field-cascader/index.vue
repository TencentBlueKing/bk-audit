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
  <div class="audit-field-cascader">
    <template v-if="renderPanels.length">
      <scroll-faker
        v-for="(node, level) in renderPanels"
        :key="level"
        class="audit-field-cascader-panel"
        :class="{'audit-field-cascader-panel-child': level > 0}">
        <ul>
          <li
            v-for="(item, index) in node.data"
            :key="index"
            class="audit-field-cascader-node"
            :class="{
              'active': hoverItem && hoverItem.id === item.id,
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
              class="audit-field-cascader-icon"
              type="angle-line-up" />
          </li>
        </ul>
        <!-- 新增：如果是二级及以上，且父节点 dynamic_content 为 true，显示添加按钮 -->
        <template v-if="level > 0 && hoverItem && hoverItem.dynamic_content">
          <div class="audit-field-cascader-bottom">
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
              <div>
                <template
                  v-for="(item, index) in customFields"
                  :key="index">
                  <bk-input
                    v-model="item.field"
                    autofocus
                    :placeholder="t(`请输入${level + 1 +index}级字段`)"
                    style="width: 115px; margin-top: 5px;" />
                  <audit-icon
                    v-if="index === customFields.length - 1"
                    class="add-icon"
                    :class="[!item.field ? 'disabled-add-icon' : '']"
                    type="add-fill"
                    @click="() => customFields.push({ field: '' })" />
                  <span
                    v-else
                    style="margin: 0 5px;">/</span>
                </template>
              </div>
              <div>
                <bk-input
                  v-model="remark"
                  :placeholder="t('输入备注（非必填）')"
                  style="margin-top: 8px;" />
              </div>
              <div style="margin-top: 8px; text-align: right;">
                <bk-button
                  class="mr8"
                  :disabled="!customFields"
                  size="small"
                  theme="primary"
                  @click="handleConfirm(node)">
                  {{ t('确定') }}
                </bk-button>
                <bk-button
                  size="small"
                  @click="handleCancel">
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
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useMessage from '@/hooks/use-message';

  interface CascaderItem {
    allow_operators: string[]
    children: CascaderItem[]
    disabled: boolean
    dynamic_content: boolean
    id: string
    isJson: boolean
    level: number
    name: string
  }

  interface Props {
    data: CascaderItem[];
    modelValue?: Record<string, boolean>;
    searchKeyword: string;
    isSearching: boolean;
  }

  interface Emits {
    (e: 'update:modelValue', value: Record<string, boolean>): void;
    (e: 'select', item: CascaderItem, isChecked: boolean): void;
    (e: 'clear-search'): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageError } = useMessage();

  const renderPanels = ref<Array<{
    parent: CascaderItem | null;
    data: CascaderItem[];
  }>>([]);

  const selectedItems = ref<Record<string, boolean>>({});
  const indeterminateItems = ref<Record<string, boolean>>({});

  const hoverItem = ref<CascaderItem | null>(null);
  const hoverLevel = ref<number>(-1);

  const showAdd = ref(false);
  const customFields = ref([{ field: '' }]);
  const remark = ref('');

  // 新增方法
  const handleConfirm = (node: {
    parent: CascaderItem | null;
    data: CascaderItem[];
  }) => {
    if (!node.parent) return;

    // 创建新的ID
    const newId = JSON.stringify([node.parent.id, ...customFields.value.map(item => item.field)]);

    // 检查ID是否已存在
    const idExists = node.data.some(item => item.id === newId);
    if (idExists) {
      messageError(t('字段已存在'));
      return;
    }

    node.data.push({
      allow_operators: [],
      children: [],
      disabled: false,
      dynamic_content: false,
      id: newId,
      isJson: false,
      level: node.parent.level + 1,
      name: customFields.value.map(item => item.field).join('/'),
    });

    // 重置数据;
    customFields.value = [{ field: '' }];
    remark.value = '';
    showAdd.value = false;
  };

  const handleCancel = () => {
    customFields.value = [{ field: '' }];
    remark.value = '';
    showAdd.value = false;
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
    // 判断是选中还是取消选中
    const isChecked = selectedItems.value[item.id];

    // 更新选中状态
    emits('update:modelValue', selectedItems.value);

    // 发送选择事件，并传递选中状态
    emits('select', item, isChecked);

    // 更新半选状态
    updateIndeterminateStatus(props.data);
  };

  const handleClearSearch = () => {
    emits('clear-search');
  };

  // 同步外部值的改动
  watch(() => props.modelValue, (newVal) => {
    selectedItems.value = { ...newVal };
  }, {
    immediate: true,
  });

  watch(() => props.searchKeyword, (newVal) => {
    if (!newVal) {
      renderPanels.value = [{
        parent: null,
        data: props.data,
      }];
      return;
    }

    // 搜索过滤逻辑，递归收集所有匹配节点的路径，自动展开所有层级
    const matchedPaths: CascaderItem[][] = [];
    function findMatchedPaths(nodes: CascaderItem[], path: CascaderItem[] = []): boolean {
      for (const node of nodes) {
        const currentPath = [...path, node];
        const isMatch = node.name.includes(newVal);
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
  }, {
    immediate: true,
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

<style lang="postcss" scoped>
.audit-field-cascader {
  display: flex;
  height: 350px;

  .audit-field-cascader-panel {
    position: relative;
    width: auto;
    height: 350px;
    min-width: 290px;
    padding: 4px 0;
    background-color: #fff;

    &.audit-field-cascader-panel-child {
      height: 385px !important;
      border-left: 1px solid #eee;
      transform: translateY(-35px);
    }

    .audit-field-cascader-node {
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
        background-color: #f5f7fa;
      }

      &.disabled {
        color: #c4c6cc;
        cursor: not-allowed;
        background-color: #fff;
      }

      .audit-field-cascader-icon {
        color: #979ba5;
        transform: rotate(90deg);
      }
    }

    .audit-field-cascader-bottom {
      position: absolute;
      bottom: 0;
      left: 0;
      z-index: 10;
      width: 100%;
      color: #63656e;
      cursor: pointer;
      background: #fafbfd;;
      border-top: 1px solid #f0f1f5;

      .add-icon {
        margin-left: 5px;
        color: #c4c6cc;

        &:hover {
          color: #3a84ff;
        }
      }

      .disabled-add-icon {
        color: #dcdee5;
        cursor: not-allowed;
        user-select: none
      }
    }
  }
}
</style>
