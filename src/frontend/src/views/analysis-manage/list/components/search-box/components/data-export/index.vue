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
  <bk-dialog
    v-model:is-show="isShow"
    quick-close
    :title="t('审计日志导出')"
    @closed="handleClosed">
    <div class="export-data-overview">
      <div class="export-data-overview-item">
        <div class="count">
          {{ total }}
        </div>
        <div class="describe">
          {{ t('当前数据量级') }}
        </div>
      </div>
      <div class="export-data-overview-item">
        <div class="count">
          {{ Math.ceil((total / 20) / 60) }}min
        </div>
        <div class="describe">
          {{ t('预计下载用时') }}
        </div>
      </div>
    </div>
    <div class="export-data-range">
      {{ t('导出范围') }}
    </div>
    <bk-radio-group
      v-model="exportRange"
      class="export-data-range-radio">
      <bk-radio
        label="all">
        {{ t('全部字段') }}
      </bk-radio>
      <bk-radio
        label="standard">
        {{ t('标准字段') }}
        <audit-icon
          v-bk-tooltips="t('系统上报的审计标准字段')"
          style="margin-left: 4px; color: #c4c6cc; cursor: pointer;"
          type="help-fill" />
      </bk-radio>
      <bk-radio
        label="specified">
        {{ t('指定字段') }}
      </bk-radio>
    </bk-radio-group>
    <template v-if="exportRange === 'specified'">
      <bk-select
        ref="selectRef"
        :auto-height="false"
        collapse-tags
        custom-content
        display-key="name"
        id-key="id"
        multiple
        multiple-mode="tag"
        :popover-options="{
          'width': 'auto',
          extCls: 'add-search-tree-pop'
        }"
        @search-change="handleSearch"
        @tag-remove="handleRemoveTag">
        <bk-tree
          ref="treeRef"
          children="children"
          :data="localData"
          :empty-text="t('数据搜索为空')"
          label="raw_name"
          :node-content-action="['click']"
          show-checkbox
          :show-node-type-icon="false"
          @node-checked="handleNodeChecked">
          <template #default="{ data: nodeData }: { data: CascaderItem }">
            <template v-if="!nodeData.isEdit">
              <span> {{ nodeData.name }}</span>
              <div>
                <span
                  class="category-type"
                  :style="categoryStyleMap[nodeData.category as keyof typeof categoryStyleMap]">
                  {{ categoryMap[nodeData.category as keyof typeof categoryMap] }}
                </span>
                <!-- 添加子字段 -->
                <span style="display: inline-block; width: 14px; height: 14px;">
                  <audit-icon
                    v-if="nodeData.dynamic_content"
                    style="margin-left: 5px;
                      font-size: 14px;
                      color: #3a84ff"
                    type="plus-circle"
                    @click.stop="handleAddNode(nodeData)" />
                </span>
              </div>
            </template>
            <div
              v-else
              style="display: flex; align-items: center;">
              <span>{{ nodeData.name }}</span>
              <span style="margin: 0 5px;">/</span>
              <!-- 多级字段输入 -->
              <template
                v-for="(item, index) in fieldTypeValue[nodeData.id]"
                :key="index">
                <bk-input
                  v-model="item.field"
                  autofocus
                  :placeholder="t('请输入')"
                  style="width: 115px;" />
                <audit-icon
                  v-if="index === fieldTypeValue[nodeData.id].length - 1"
                  v-bk-tooltips="t('添加下级字段')"
                  class="add-icon"
                  :class="[!item.field ? 'disabled-add-icon' : '']"
                  type="add-fill"
                  @click="() => item.field && fieldTypeValue[nodeData.id].push({ field: '' })" />
                <span
                  v-else
                  style="margin: 0 5px;">/</span>
              </template>
              <div class="field-edit-right">
                <audit-icon
                  v-bk-tooltips="t('确认')"
                  :class="[fieldTypeValue[nodeData.id] && fieldTypeValue[nodeData.id].
                    some(field => !field.field) ? 'disabled-submit-icon' : 'submit-icon']"
                  svg
                  type="check-line"
                  @click.stop="handleAddFieldSubmit(nodeData)" />
                <audit-icon
                  v-bk-tooltips="t('取消添加')"
                  style="margin-right: 4px;
                    font-size: 18px;
                    color: #c1c3c9;"
                  svg
                  type="close"
                  @click.stop="handleAddFieldClose(nodeData)" />
              </div>
            </div>
          </template>
        </bk-tree>
      </bk-select>
    </template>
    <template #footer>
      <bk-button
        class="mr8"
        :disabled="!selectedItems.length && exportRange === 'specified'"
        :loading="createQueryTaskLoading"
        theme="primary"
        @click="handleConfirmSearch">
        {{ t('确定') }}
      </bk-button>
      <bk-button @click="handleClosed">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import _ from 'lodash';
  import { inject, type Ref, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EsQueryService from '@service/es-query';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface CascaderItem {
    allow_operators: string[]
    category?: string
    children: CascaderItem[]
    disabled: boolean
    dynamic_content: boolean
    id: string
    isJson: boolean
    level: number
    name: string
    isEdit: boolean
    isOpen: boolean;
  }

  interface Props {
    data: CascaderItem[];
    modelValue?: CascaderItem[];
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const selectRef = ref();
  const treeRef = ref();
  const isShow = defineModel<boolean>('isShow', {
    required: true,
  });

  const categoryMap = {
    system: t('系统'),
    standard: t('标准'),
    snapshot: t('快照'),
  };

  const categoryStyleMap = {
    system: {
      backgroundColor: '#E1ECFF',
      color: '#1768EF',
    },
    standard: {
      backgroundColor: '#DAF6E5',
      color: '#299E56',
    },
    snapshot: {
      backgroundColor: '#FCE5C0',
      color: '#E38B02',
    },
  };

  const total = inject <Ref<number>>('total', ref(0));
  const exportRange = ref('all');
  const tableSearchModel = inject <Ref<Record<string, any>>>('tableSearchModel', ref({}));

  const fields = ref<Array<{
    keys: string[];
    raw_name: string;
    display_name: string;
  }>>([]);
  const isSearching = ref(false);

  const localData = ref<CascaderItem[]>([]);
  // 保存原始数据，用于在搜索关键词为空时恢复
  const originalData = ref<CascaderItem[]>([]);

  const selectedItems = ref<CascaderItem[]>([]);
  const fieldTypeValue = ref<Record<string, Record<string, any>[]>>({});

  const handleSearch = (keyword: string) => {
    isSearching.value = !!keyword;

    if (!keyword) {
      // 如果关键词为空，恢复原始数据
      localData.value = [...originalData.value];
      return;
    }

    // 递归搜索匹配项
    const filterNodes = (nodes: CascaderItem[]): CascaderItem[] => nodes.filter((node) => {
      // 检查当前节点名称是否包含关键词
      const isMatch = node.name.toLowerCase().includes(keyword.toLowerCase());

      // 如果有子节点，递归搜索
      if (node.children && node.children.length) {
        const filteredChildren = filterNodes(node.children);
        // 更新子节点为过滤后的结果
        // eslint-disable-next-line no-param-reassign
        node.children = filteredChildren;
        // 如果子节点中有匹配项，或当前节点匹配，则保留该节点
        return filteredChildren.length > 0 || isMatch;
      }

      // 如果是叶子节点，根据是否匹配决定是否保留
      return isMatch;
    });

    // 对数据进行过滤
    localData.value = filterNodes([...originalData.value]);
  };

  const formatFields = (item: CascaderItem) => {
    const fieldId = item.id;
    const displayName = item.name;

    let fieldKeys: string[] = [];
    let rawName = fieldId;

    // 尝试解析 ID，检查是否为数组字符串
    try {
      const parsedId = JSON.parse(fieldId);
      if (Array.isArray(parsedId) && parsedId.length > 0) {
        // eslint-disable-next-line prefer-destructuring
        rawName = parsedId[0];
        fieldKeys = parsedId.slice(1);
      }
    } catch (e) {
      // 如果解析失败，说明不是JSON字符串，使用默认值
      rawName = fieldId;
      fieldKeys = [];
    }

    const fieldInfo = {
      keys: fieldKeys,
      raw_name: rawName,
      display_name: displayName,
    };

    // 如果是选中，添加到字段列表（避免重复添加）
    if (!fields.value.some(field => field.raw_name === fieldInfo.raw_name
      && JSON.stringify(field.keys) === JSON.stringify(fieldInfo.keys))) {
      fields.value.push(fieldInfo);
    }
  };

  const handleNodeChecked = (data: Array<CascaderItem>) => {
    const { schema } = treeRef.value.getData();

    // 过滤掉 __is_indeterminate 为 true 的项
    const filterData = data.filter((item) => {
      const schemaItem = schema.get(item);
      // eslint-disable-next-line no-underscore-dangle
      return !schemaItem?.__is_indeterminate;
    });

    selectedItems.value = filterData;
    // 设置select选中
    selectRef.value.selected = filterData.map(item => ({
      value: item.id,
      label: item.name,
    }));
  };

  const handleRemoveTag = (id: string) => {
    // 根据id在selectedItems中找到对应的节点
    const nodeToRemove = selectedItems.value.find(node => node.id === id);
    if (nodeToRemove) {
      // 从selectedItems中移除该节点
      selectedItems.value = selectedItems.value.filter(node => node !== nodeToRemove);
      treeRef.value.setChecked(nodeToRemove, false);
    }
  };

  const handleAddNode = (node: CascaderItem) => {
    if (fieldTypeValue.value[node.id]) {
      return;
    }
    fieldTypeValue.value[node.id] = [{ field: '' }];
    node.children.push({
      allow_operators: [],
      children: [],
      disabled: false,
      dynamic_content: false,
      id: node.id,
      isJson: false,
      level: node.level + 1,
      name: node.name,
      isOpen: false,
      isEdit: true,
    });
    // eslint-disable-next-line no-param-reassign
    node.isOpen = true;
    originalData.value = _.cloneDeep(localData.value);
  };

  const handleAddFieldSubmit = (node: CascaderItem) => {
    const customFields =  fieldTypeValue.value[node.id];
    if (!customFields || customFields.length === 0) {
      return;
    }
    if (customFields.some(field => !field.field)) {
      return;
    }
    const newIdArray = [node.id, ...customFields.map(item => item.field)];
    const newNameStr = `${node.name}/${customFields.map(item => item.field).join('/')}`;
    // eslint-disable-next-line no-param-reassign
    node.id = JSON.stringify(newIdArray);
    // eslint-disable-next-line no-param-reassign
    node.name = newNameStr;
    // eslint-disable-next-line no-param-reassign
    node.isEdit = false;
    // 清空customFields
    // eslint-disable-next-line no-param-reassign
    delete fieldTypeValue.value[node.id];
  };

  const handleAddFieldClose = (node: CascaderItem) => {
    delete fieldTypeValue.value[node.id];
    const nodeId = node.id;
    const parentNode = localData.value.find(item => item.id === nodeId);
    if (parentNode) {
      parentNode.children.pop();
    }
  };

  // 创建导出任务
  const {
    run: createQueryTask,
    loading: createQueryTaskLoading,
  } = useRequest(EsQueryService.createQueryTask, {
    defaultValue: {},
    onSuccess: () => {
      messageSuccess(t('导出任务已创建，结果将发送至邮箱，请注意查收'));
      handleClosed();
    },
  });

  const handleClosed = () => {
    isShow.value = false;
    exportRange.value = 'all';
    fields.value = [];
  };

  const handleConfirmSearch = () => {
    // 先重置
    fields.value = [];
    // 添加fields
    selectedItems.value.forEach((item) => {
      formatFields(item);
    });
    const params = {
      query_params: tableSearchModel.value,
      export_config: {
        field_scope: exportRange.value,
        fields: fields.value,
      },
    };
    createQueryTask(params);
  };

  // 同步外部值的改动
  watch(() => props.modelValue, (newVal) => {
    selectedItems.value = newVal || [];
  }, {
    immediate: true,
  });

  watch(
    () => props.data,
    (newVal) => {
      localData.value = newVal;
      // 保存原始数据副本
      originalData.value = _.cloneDeep(newVal);
    },
  );

</script>
<style lang="postcss" scoped>
.export-data-overview {
  display: flex;
  padding: 15px 0;
  margin: 20px 0;
  background-color: #f5f7fa;
  justify-content: space-around;

  .export-data-overview-item {
    text-align: center;

    .count {
      font-size: 20px;
      font-weight: 700;
    }

    .describe {
      font-size: 12px;
    }
  }
}

.export-data-range {
  margin-bottom: 10px;
  font-weight: 700;
}

:deep(.export-data-range-radio) {
  margin-bottom: 15px;

  .bk-radio-input {
    width: 14px;
    height: 14px
  }

  .bk-radio-label {
    font-size: 12px;
  }
}
</style>
<style lang="postcss">
.data-export-popover {
  .bk-pop2-arrow {
    display: none;
  }

  .audit-field-cascader {
    height: 300px !important;

    .audit-field-cascader-panel.audit-field-cascader-panel-child {
      height: 300px !important;
      transform: translateY(0) !important;
    }
  }
}
</style>
