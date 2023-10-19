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
        <div style="height: calc(100vh - 214px);">
          <scroll-faker>
            <ul class="list-content">
              <li
                v-for="(item, index) in sourceList"
                :key="index"
                class="item-list item-list-active"
                @click="handelSelect(item, index)">
                <span class="item-name">{{ t(item.description) }}</span>
                <span class="item-icon"><audit-icon type="right" /></span>
              </li>
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
                <span class="item-name">{{ t(item.description) }}</span>
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
                      {{ t(element.description) }}
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

  import MetaManageService from '@service/meta-manage';

  import type StandardFieldModel from '@model/meta/standard-field';

  import useRequest from '@hooks/use-request';

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
  // 保留可选的字段
  const optionFields = ['event_id', 'request_id', 'event_content', 'end_time',
                        'access_source_ip', 'access_user_agent', 'result_content'];
  onMounted(async () => {
    fetchStandardField({});
  });
  /**
   * 获取全量字段
   */
  const {
    loading: sourceLoading,
    data: sourceList,
    run: fetchStandardField,
  } = useRequest(MetaManageService.fetchStandardField, {
    defaultValue: [],
    onSuccess: (data) => {
      initSourceList.value = data;
      sourceList.value = data.filter((item: StandardFieldModel) => optionFields.includes(item.field_name));
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

  const handelSelect = (item: any, index: number) => {
    targetList.value.push(item);
    sourceList.value.splice(index, 1);
    window.changeConfirm = true;
  };
  const handelDeleteSelect = (element: any) => {
    sourceList.value.push(element);
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
      flex: 1;
      min-height: 500px;

      .list-content {
        .item-list {
          position: relative;
          display: flex;
          height: 32px;
          padding: 8px 24px 8px 32px;
          line-height: 32px;
          color: #63656e;
          cursor: pointer;
          align-items: center;

          /* .item-name{
                        color:#63656E
                    } */
          .item-icon {
            display: none;
            margin-left: auto;
            font-size: 14px;
            color: #3a84ff;
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

    .line {
      position: absolute;
      top: 60px;
      bottom: 48px;
      left: 50%;
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
