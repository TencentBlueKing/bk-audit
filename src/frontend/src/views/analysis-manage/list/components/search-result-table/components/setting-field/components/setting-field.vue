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
          <scroll-faker>
            <ul class="list-content">
              <setting-field-item
                v-for="(item, index) in sourceList"
                :key="item.field_name"
                :index="index"
                :item="item"
                :parent-item="item"
                @add-sub-field="handleAddSubField"
                @select="handelSelect" />
            </ul>
          </scroll-faker>
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
                <template #item="{element}">
                  <li
                    class="item-list item-list-active"
                    @click="handelDeleteSelect(element)">
                    <span class="item-name">
                      <audit-icon
                        style="font-size: 13px;color: #c4c6cc;"
                        type="move" />
                      {{ element.description || element.field_name }}
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
      <audit-popconfirm
        :confirm-handler="handleSubmit"
        content=""
        :title="t('确认更新？')">
        <bk-button
          class="setting-filed-btn mr8"
          theme="primary">
          {{ t('应用') }}
        </bk-button>
      </audit-popconfirm>
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

  import type StandardFieldModel from '@model/meta/standard-field';

  import useRequest from '@hooks/use-request';

  import SettingFieldItem from './setting-field-item.vue';

  interface Emits {
    (e: 'updateField'):void;
    (e: 'update:modelValue', value: boolean): void,
  }
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
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
  const searchValue = ref('');
  const route = useRoute();
  const initSourceList = ref<Array<StandardFieldModel>>([]);
  onMounted(async () => {
    fetchStandardField();
  });

  /**
   * 获取字段
   */
  const {
    loading: sourceLoading,
    data: sourceList,
    run: fetchStandardField,
  } = useRequest(EsQueryService.fetchSearchConfig, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      initSourceList.value = data;
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
    data: targetList,
    run: fetchCustomFields,
  } = useRequest(MetaManageService.fetchCustomFields, {
    defaultParams: {
      route_path: route.name,
    },
    defaultValue: [],
    onSuccess: (data) => {
      sourceList.value = removeCheckedFields(data, sourceList.value) || [];
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
  const removeCheckedFields = (checkedLists:Array<StandardFieldModel>, data:Array<StandardFieldModel>) => {
    if (checkedLists.length) {
      const fieldNames = checkedLists.map(item => item.field_name);
      fieldNames.forEach((item) => {
        const index = data.findIndex(list => list.field_name === item);
        if (index !== -1) {
          data.splice(index, 1);
        }
      });
    }
    return data;
  };

  const handleCancel = () => {
    emits('update:modelValue', false);
  };

  const handelSelect = (item: any, index: number, parentItem: any, event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (
      target.closest('.bk-select')
      || target.closest('.sub-select-key-icon')
      || target.closest('.sub-add-key-icon')
    ) {
      return;
    }
    const formatItem = {
      ...item,
      parentItem, // 记录父级
      description: parentItem.field_name !== item.field_name
        ? `${parentItem.description || parentItem.field_alias}/${item.description || item.field_alias}(${parentItem.field_name}/${item.field_name})`
        : item.description,
    };
    targetList.value.push(formatItem);
    // 判断是一级还是多级字段，决定 splice 的目标
    if (parentItem
      && parentItem.field_name !== item.field_name
      && parentItem.property && Array.isArray(parentItem.property.sub_keys)) {
      // 二级或多级字段，从父级的 sub_keys 删除
      const subIndex = parentItem.property.sub_keys.findIndex((sub: any) => sub.field_name === item.field_name);
      if (subIndex !== -1) {
        parentItem.property.sub_keys.splice(subIndex, 1);
      }
    } else {
      // 一级字段，从 sourceList 删除
      sourceList.value.splice(index, 1);
    }
    window.changeConfirm = true;
  };
  const handleAddSubField = (parentItem: any, newItem: any) => {
    parentItem.property.sub_keys.push(newItem);
  };
  const handelDeleteSelect = (element: any) => {
    if (element.field_alias) {
      // eslint-disable-next-line no-param-reassign
      element.description = element.field_alias;
    }
    // 判断是否有 parentItem 字段且 parentItem 不等于自身
    if (element.parentItem && element.parentItem.field_name !== element.field_name
      && element.parentItem.property && Array.isArray(element.parentItem.property.sub_keys)) {
      // 还原到父级的 sub_keys
      element.parentItem.property.sub_keys.push(element);
    } else {
      // 还原到 sourceList
      sourceList.value.push(element);
    }
    const index = targetList.value.findIndex(item => item.field_name === element.field_name);
    targetList.value.splice(index, 1);
    window.changeConfirm = true;
  };
  const handleSubmit = () => Promise.resolve()
    .then(() => {
      updateField(targetList.value);
    });

  const handleReset = () => {
    sourceList.value = sourceList.value.concat(targetList.value);
    initSourceList.value = sourceList.value;
    targetList.value = [];
  };

  const handleSearch = () => {
    sourceList.value = initSourceList.value.filter(item => item.description.indexOf(searchValue.value) !== -1);
  };

  const updateField = async (fields: Array<StandardFieldModel>) => {
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
.setting-filed-box {
  .setting-filed-operation {
    display: flex;

    .search-input {
      padding: 24px;
    }

    .source-list,
    .target-list {
      min-height: 500px;

      .list-content {
        .item-list {
          position: relative;
          display: flex;
          width: auto;
          height: 32px;
          padding: 8px 24px 8px 32px;
          line-height: 32px;
          color: #63656e;
          cursor: pointer;
          align-items: center;

          .item-icon {
            display: none;
            margin-left: auto;
            font-size: 14px;
            color: #3a84ff;
          }

          .sub-add-key-icon,
          .sub-select-key-icon {
            margin: 0 5px;
            color: #c4c6cc;
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
    }

    .source-list {
      width: 350px;
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
}
</style>
