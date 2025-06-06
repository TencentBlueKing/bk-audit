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
    class="setting-filed-operation">
    <div class="source-list">
      <bk-loading :loading="sourceLoading">
        <div class="search-input">
          <bk-input
            v-model.trim="searchValue"
            clearable
            :placeholder="t('搜索属性')"
            type="search"
            @input="handleSearch" />
        </div>
        <div style="height: calc(100vh - 260px);">
          <bk-tree
            v-if="sourceList.length"
            ref="treeRef"
            :check-strictly="false"
            children="children"
            :data="sourceList"
            :show-node-type-icon="false">
            <template #default="{ data }: { data: CascaderNode }">
              <template v-if="!data.isEdit">
                <div
                  class="item-list item-list-active"
                  style="overflow-x: auto;"
                  @click="handelSelect(data)">
                  <div>
                    <span
                      class="category-type"
                      :style="categoryStyleMap[data.category as keyof typeof categoryStyleMap]">
                      {{ categoryMap[data.category as keyof typeof categoryMap] }}
                    </span>
                    <span style="margin-left: 8px; font-size: 12px;">{{ data.description }}</span>
                  </div>
                  <div>
                    <span
                      v-if="data.isJson && data.dynamic_content"
                      class="item-icon"
                      style="font-size: 12px;"
                      @click.stop="handleAddNode(data)">
                      <audit-icon type="add" />
                    </span>
                    <span
                      class="item-icon"
                      style="margin-left: 8px;">
                      <audit-icon type="right" />
                    </span>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="add-item-list item-list-active">
                  <scroll-faker>
                    <span>{{ data.description }}</span>
                    <span style="margin: 0 5px;">/</span>
                    <!-- 多级字段输入 -->
                    <template
                      v-for="(item, index) in fieldTypeValue[data.field_name]"
                      :key="index">
                      <bk-input
                        v-model="item.field"
                        autofocus
                        :placeholder="t('请输入')"
                        style="width: 85px;" />
                      <audit-icon
                        v-if="index === fieldTypeValue[data.field_name].length - 1"
                        v-bk-tooltips="t('添加下级字段')"
                        class="add-icon"
                        :class="[!item.field ? 'disabled-add-icon' : '']"
                        type="add-fill"
                        @click="() => item.field && fieldTypeValue[data.field_name].push({ field: '' })" />
                      <span
                        v-else
                        style="margin: 0 5px;">/</span>
                    </template>
                    <span class="field-edit-right">
                      <audit-icon
                        v-bk-tooltips="t('确认')"
                        :class="[fieldTypeValue[data.field_name] && fieldTypeValue[data.field_name].
                          some(field => !field.field) ? 'disabled-submit-icon' : 'submit-icon']"
                        svg
                        type="check-line"
                        @click.stop="handleAddFieldSubmit(data)" />
                      <audit-icon
                        v-bk-tooltips="t('取消添加')"
                        style="margin-left: 4px;
                          font-size: 18px;
                          color: #c1c3c9;
                          transform: translateY(4px);"
                        svg
                        type="close"
                        @click.stop="handleAddFieldClose(data)" />
                    </span>
                  </scroll-faker>
                </div>
              </template>
            </template>
          </bk-tree>
          <bk-exception
            v-if="isSearching && !sourceList.length"
            scene="part"
            style="height: 280px;padding-top: 40px;"
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
        </div>
      </bk-loading>
    </div>
    <div class="line" />
    <div class="target-list">
      <bk-loading :loading="targetLoading">
        <div class="search-input">
          <div class="checked-number">
            {{ t('已选字段') }}({{ targetList.length + initList.length }})
          </div>
        </div>
        <div style="height: calc(100vh - 214px);">
          <scroll-faker>
            <ul class="list-content">
              <li
                v-for="(item, index) in initList"
                :key="index"
                class="not-allowed item-list">
                <span class="item-name">{{ item.description }}</span>
              </li>
              <vuedraggable
                item-key="field_name"
                :list="targetList">
                <template #item="{element}: { element: CascaderNode }">
                  <li
                    class="item-list item-list-active"
                    @click="handelDeleteSelect(element)">
                    <span class="item-name">
                      <audit-icon
                        style="font-size: 13px;color: #c4c6cc;"
                        type="move" />
                      {{ element.description }}
                      <span v-if="element.level > 1">
                        ({{ element.field_name.replace(/\./g, '\/') }})
                      </span>
                    </span>
                    <span
                      class="item-icon"
                      style="color: #c4c6cc;"><audit-icon type="close" /></span>
                  </li>
                </template>
              </vuedraggable>
            </ul>
          </scroll-faker>
        </div>
      </bk-loading>
    </div>
    <div
      class="setting-filed-footer">
      <!-- <audit-popconfirm
        :confirm-handler="handleSubmit"
        content=""
        :title="t('确认更新？')"> -->
      <bk-button
        class="setting-filed-btn mr8"
        theme="primary"
        @click="handleSubmit">
        {{ t('应用') }}
      </bk-button>
      <!-- </audit-popconfirm> -->
      <bk-button
        class="setting-filed-btn"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
      <bk-button
        class="setting-filed-btn"
        style="margin-left: auto;"
        @click="handleReset">
        {{ t('还原默认') }}
      </bk-button>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';
  import Vuedraggable from 'vuedraggable';

  import EsQueryService from '@service/es-query';
  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  interface CascaderNode {
    allow_operators: string[]
    category?: string
    children: CascaderNode[]
    disabled: boolean
    dynamic_content: boolean
    field_name: string
    isJson: boolean
    level: number
    description: string
    isEdit: boolean
    isOpen: boolean;
  }

  interface Emits {
    (e: 'updateField'):void;
    (e: 'update:modelValue', value: boolean): void,
  }
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const route = useRoute();

  const searchValue = ref('');
  const sourceList = ref<CascaderNode[]>([]);
  const initSourceList = ref<CascaderNode[]>([]);
  const targetList = ref<CascaderNode[]>([]);
  const isSearching = ref(false);
  const fieldTypeValue = ref<Record<string, Record<string, any>[]>>({});

  const initList = [
    { field_name: 'start_time', description: '操作起始时间' },
    { field_name: 'username', description: '操作人' },
    { field_name: 'system_id', description: '来源系统' },
    { field_name: 'action_id', description: '操作事件名' },
    { field_name: 'resource_type_id', description: '资源类型' },
    { field_name: 'instance_name', description: '资源实例' },
    { field_name: 'result_code', description: '操作结果' },
    { field_name: 'access_type', description: '操作途径' },
  ];
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

  onMounted(async () => {
    fetchStandardField();
  });

  /**
   * 获取字段
   */
  const {
    loading: sourceLoading,
    // data: sourceList,
    run: fetchStandardField,
  } = useRequest(EsQueryService.fetchSearchConfig, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      const processedData = convertToCascaderList(data);
      initSourceList.value = processedData;
      sourceList.value = processedData;
      fetchCustomFields({
        route_path: route.name,
      });
    },
  });

  /**
   * 获取用户自定义字段
   */
  const {
    loading: targetLoading,
    // data: targetList,
    run: fetchCustomFields,
  } = useRequest(MetaManageService.fetchCustomFields, {
    defaultParams: {
      route_path: route.name,
    },
    defaultValue: [],
    onSuccess: (data) => {
      targetList.value = convertToCascaderList(data);
      // 根据category字段排序：standard在前，system在中，snapshot在后
      const sortedData = [...removeCheckedFields(targetList.value, sourceList.value) || []].sort((a, b) => {
        const categoryOrder = { standard: 1, system: 2, snapshot: 3 };
        const aOrder = categoryOrder[a.category as keyof typeof categoryOrder] || 999;
        const bOrder = categoryOrder[b.category as keyof typeof categoryOrder] || 999;
        return aOrder - bOrder;
      });
      sourceList.value = sortedData;
    },
  });

  /**
   * 更新用户自定义字段
   */
  const {
    run: fetchUpdateCustomFields,
  } = useRequest(MetaManageService.fetchUpdateCustomFields, {
    defaultParams: {
      route_path: route.name,
      fields: targetList.value,
    },
    defaultValue: [],
  });

  /**
   * 删掉sourcelist已经选中的列/默认不可选的列
   */
  const removeCheckedFields = (checkedLists:Array<CascaderNode>, data:Array<CascaderNode>) => {
    const allCheckedLists = [...checkedLists, ...initList];
    if (allCheckedLists.length) {
      const fieldNames = allCheckedLists.map(item => item.field_name);
      console.log(fieldNames);
      fieldNames.forEach((item) => {
        const index = data.findIndex(list => list.field_name === item);
        if (index !== -1) {
          data.splice(index, 1);
        }
      });
    }
    return data;
  };

  // eslint-disable-next-line max-len
  const convertToCascaderList = (arr: any[], level = 1, parentIds: string[] = []): CascaderNode[] => (Array.isArray(arr) ? arr.map((item: any) => {
    const currentId = item?.field_name ?? '';
    // 创建包含所有父级ID的数组
    const fullIds = level === 1 ?  [currentId] : [...parentIds, currentId];

    const children = item && item.property && Array.isArray(item.property.sub_keys)
      ? convertToCascaderList(item.property.sub_keys, level + 1, fullIds)
      : [];
    const newItem = {
      allow_operators: item?.allow_operators || [],
      children,
      category: item?.category ?? '',
      dynamic_content: item.property?.dynamic_content ?? false,
      disabled: false,
      field_name: level === 1 ? currentId : fullIds,
      isJson: item?.is_json ?? false,
      level: item.field_name.split('.').length > 1 ? item.field_name.split('.').length : 1,
      description: item?.description ?? item?.field_alias ?? '',
      isEdit: false,
      isOpen: false,
    };
    newItem.field_name = Array.isArray(newItem.field_name) ? JSON.stringify(newItem.field_name) : newItem.field_name;
    return newItem;
  }) : []);

  const handelSelect = (item: CascaderNode) => {
    const formatItem = {
      ...item,
    };
    if (item.field_name && typeof item.field_name === 'string' && item.field_name.startsWith('[')) {
      const fieldNameArr = JSON.parse(formatItem.field_name);
      if (fieldNameArr.length > 1) {
        formatItem.field_name = fieldNameArr.join('.');

        // 获取第一个元素
        const firstFieldName = fieldNameArr[0];
        // 在sourceList中查找匹配的元素
        const parentNode = sourceList.value.find(sourceItem => sourceItem.field_name === firstFieldName
          || (typeof sourceItem.field_name === 'string'
            && sourceItem.field_name.includes(firstFieldName)));

        if (parentNode) {
          if (!formatItem.description.includes(parentNode.description)) {
            formatItem.description = `${parentNode.description}/${formatItem.description}`;
          }
          // 从二级字段删除
          const subIndex = parentNode.children.findIndex((sub: CascaderNode) => sub.field_name === item.field_name);
          if (subIndex !== -1) {
            parentNode.children.splice(subIndex, 1);
            parentNode.isOpen = true;
          }
        }
      }
    } else {
      // 一级字段
      const index = sourceList.value.findIndex((sourceItem: CascaderNode) => sourceItem.field_name === item.field_name);
      if (index !== -1) {
        sourceList.value.splice(index, 1);
      }
    }
    targetList.value.push(formatItem);
    window.changeConfirm = true;
  };

  const handelDeleteSelect = (element: CascaderNode) => {
    // 判断是否有 parentItem 字段且 parentItem 不等于自身
    if (element.level > 1 && element.field_name && element.field_name.includes('.')) {
      // 分割field_name，获取各级字段名
      const fieldNameParts = element.field_name.split('.');
      // 第一部分是父级字段名
      const parentFieldName = fieldNameParts[0];
      // 在sourceList中查找父节点
      const parentNode = sourceList.value.find(item => item.field_name === parentFieldName);

      if (parentNode) {
        // 创建一个还原后的元素，恢复原始状态
        const restoredElement = {
          ...element,
          // 恢复原始field_name（可能是JSON字符串）
          field_name: JSON.stringify(element.field_name.split('.')),
          // 恢复原始description（去掉父级部分）
          description: (element.description.includes('/') && element.level < 3)
            ? element.description.substring(element.description.indexOf('/') + 1)
            : element.description,
        };

        // 将还原后的元素添加到父节点的children中
        parentNode.children.push(restoredElement);
        // 确保父节点是打开状态
        parentNode.isOpen = true;
      }
    } else {
      // 还原到 sourceList
      sourceList.value.push(element);
    }
    const index = targetList.value.findIndex(item => item.field_name === element.field_name);
    targetList.value.splice(index, 1);
    window.changeConfirm = true;
  };

  const handleAddNode = (node: CascaderNode) => {
    if (fieldTypeValue.value[node.field_name]) {
      return;
    }
    fieldTypeValue.value[node.field_name] = [{ field: '' }];
    node.children.push({
      allow_operators: [],
      children: [],
      disabled: false,
      dynamic_content: false,
      field_name: node.field_name,
      isJson: false,
      level: node.level + 2,
      description: node.description,
      isOpen: false,
      isEdit: true,
    });
    // eslint-disable-next-line no-param-reassign
    node.isOpen = true;
  };

  const handleAddFieldSubmit = (node: CascaderNode) => {
    const customFields =  fieldTypeValue.value[node.field_name];
    if (!customFields || customFields.length === 0) {
      return;
    }
    if (customFields.some(field => !field.field)) {
      return;
    }
    const newIdArray = [node.field_name, ...customFields.map(item => item.field)];
    const newNameStr = `${node.description}/${customFields.map(item => item.field).join('/')}`;
    // eslint-disable-next-line no-param-reassign
    node.field_name = JSON.stringify(newIdArray);
    // eslint-disable-next-line no-param-reassign
    node.description = newNameStr;
    // eslint-disable-next-line no-param-reassign
    node.isEdit = false;
    // 清空customFields
    // eslint-disable-next-line no-param-reassign
    delete fieldTypeValue.value[node.field_name];
  };

  const handleAddFieldClose = (node: CascaderNode) => {
    delete fieldTypeValue.value[node.field_name];
    const nodeFieldName = node.field_name;
    const parentNode = sourceList.value.find(item => item.field_name === nodeFieldName);
    if (parentNode) {
      parentNode.children.pop();
    }
  };

  const handleSubmit = () => Promise.resolve()
    .then(() => {
      console.log(targetList.value);
      updateField(targetList.value);
    });

  const handleCancel = () => {
    emits('update:modelValue', false);
  };

  const handleReset = () => {
    sourceList.value = sourceList.value.concat(targetList.value);
    initSourceList.value = sourceList.value;
    targetList.value = [];
  };

  const handleSearch = () => {
    isSearching.value = true;
    sourceList.value = initSourceList.value.filter(item => item.description.indexOf(searchValue.value) !== -1);
  };

  const handleClearSearch = () => {
    searchValue.value = '';
    isSearching.value = false;
    handleSearch();
  };

  const updateField = async (fields: Array<CascaderNode>) => {
    await fetchUpdateCustomFields({
      route_path: route.name,
      fields,
    });
    emits('update:modelValue', false);
    emits('updateField');
    window.changeConfirm = false;
  };
</script>
<style lang="postcss" scoped>
.setting-filed-operation {
  display: flex;

  .search-input {
    padding: 24px;
  }

  .source-list,
  .target-list {
    min-height: 500px;

    :deep(.bk-tree),
    .list-content {
      padding: 0 22px 0 8px;

      .is-selected {
        background-color: #fff;
      }

      .item-list {
        position: relative;
        display: flex;
        width: auto;
        padding: 0 8px;
        font-size: 12px;
        color: #63656e;
        align-items: center;
        justify-content: space-between;

        .item-name {
          margin-left: 8px;
        }

        .item-icon {
          display: none;
          margin-left: auto;
          font-size: 14px;
          color: #3a84ff;
          cursor: pointer;
        }

        .sub-add-key-icon,
        .sub-select-key-icon {
          margin: 0 5px;
          color: #c4c6cc;
        }

        .category-type {
          width: 28px;
          height: 16px;
          font-size: 10px;
          line-height: 16px;
          text-align: center;
          border-radius: 2px;
        }
      }

      .not-allowed {
        margin-left: 16px;
        color: lightgray;
        cursor: not-allowed;
      }

      .item-list-active:hover {
        color: #3a84ff;
        background-color: #edf4ff;
      }

      .item-list-active:hover .item-icon {
        display: inline-block;
      }
    }

    .list-content {
      padding: 0;

      .item-list {
        height: 32px;
        line-height: 32px;
      }
    }
  }

  .source-list {
    width: 350px;

    :deep(.bk-tree) {
      .bk-node-action {
        width: 14px;
        height: 32px;
      }

      .add-item-list {
        height: 32px;
        font-size: 12px;
        line-height: 32px;
        color: #63656e;
      }

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

      .field-edit-right {
        display: inline-block;
        margin-left: 5px;

        .submit-icon {
          transform: translateY(4px);
          margin-right: 4px;
          font-size: 18px;
          color: #7bbe8a;
        }

        .disabled-submit-icon {
          transform: translateY(4px);
          font-size: 18px;
          color: #dcdee5;
          cursor: not-allowed;
          user-select: none
        }
      }
    }
  }

  .line {
    position: absolute;
    top: 60px;
    bottom: 48px;
    left: 37%;
    z-index: 1;
    width: 1px;
    background: lightgray;
  }

  .target-list {
    flex: 1;

    .checked-number {
      padding: 8px 24px;
      color: #313238;
      background-color: #f5f7fa;
    }
  }
}

.setting-filed-footer {
  position: absolute;
  bottom: 0;
  display: flex;
  width: 100%;
  height: 48px;
  padding: 8px 24px;
  line-height: 48px;
  background-color: #fafbfd;

  .setting-filed-btn {
    display: flex;
    min-width: 88px;
  }
}
</style>
