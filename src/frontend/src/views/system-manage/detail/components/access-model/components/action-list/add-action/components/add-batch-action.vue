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
  <div class="add-batch-action">
    <div class="render-field">
      <div class="field-header-row">
        <div class="field-select">
          <bk-checkbox
            v-model="isSelectedAll" />
        </div>
        <div class="field-value is-required">
          {{ t('操作ID') }}
        </div>
        <div class="field-value is-required">
          {{ t('操作名称') }}
        </div>
        <div class="field-value">
          {{ t('依赖资源') }}
          <bk-popover
            ref="batchPopover"
            placement="bottom"
            theme="light"
            trigger="click"
            width="380">
            <audit-icon
              style="margin-left: 4px;color: #3a84ff;"
              type="edit-fill" />
            <template #content>
              <h3>{{ t('批量编辑依赖资源') }}</h3>
              <audit-form
                ref="formRef"
                class="customize-form"
                form-type="vertical"
                :model="formData">
                <bk-form-item
                  :label="t('依赖资源')"
                  label-width="160"
                  property="resource_type_ids"
                  required>
                  <bk-select
                    ref="batchSelectRef"
                    v-model="formData.resource_type_ids"
                    :auto-height="false"
                    custom-content
                    display-key="name"
                    id-key="resource_type_id"
                    @search-change="handleSearch">
                    <bk-tree
                      ref="treeRef"
                      children="children"
                      :data="parentResourceList"
                      :empty-text="t('数据搜索为空')"
                      :search="searchValue"
                      :show-node-type-icon="false"
                      @node-click="(data: SystemResourceTypeTree) => handleNodeClick(data, 'batch')">
                      <template #default="{ data }: { data: SystemResourceTypeTree }">
                        <span> {{ data.name }}</span>
                      </template>
                    </bk-tree>
                  </bk-select>
                </bk-form-item>
              </audit-form>
              <div style="margin-top: 8px; font-size: 14px; line-height: 22px; color: #3a84ff; text-align: right;">
                <bk-button
                  class="mr8"
                  :disabled="!formData.resource_type_ids"
                  size="small"
                  theme="primary"
                  @click="handleSubmitBatch()">
                  {{ t('确定') }}
                </bk-button>
                <bk-button
                  size="small"
                  @click="handleCancelBatch()">
                  {{ t('取消') }}
                </bk-button>
              </div>
            </template>
          </bk-popover>
        </div>
        <div class="field-operation" />
      </div>
      <audit-form
        ref="tableFormRef"
        form-type="vertical"
        :model="formData">
        <template
          v-for="(item, index) in formData.renderData"
          :key="index">
          <div class="field-row">
            <div class="field-select">
              <bk-checkbox
                v-model="item.isSelected" />
            </div>
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0"
                :property="`renderData[${index}].action_id`"
                required
                :rules="[
                  { message: '不能为空', trigger: 'change', validator: (value: string) => !!value},
                  { message: 'ID重复，请修改', trigger: 'change', validator: (value: string) => {
                    const duplicates = formData.renderData.filter(
                      (item, idx) => item.action_id === value && idx !== index
                    );
                    if (duplicates.length > 0) {
                      return false;
                    }
                    return true;
                  }}
                ]">
                <bk-input
                  ref="fieldItemRef"
                  v-model="item.action_id" />
              </bk-form-item>
            </div>
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0"
                :property="`renderData[${index}].name`"
                required>
                <bk-input
                  ref="fieldItemRef"
                  v-model="item.name" />
              </bk-form-item>
            </div>
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-select
                  ref="singleSelectRef"
                  v-model="item.resource_type_ids"
                  :auto-height="false"
                  custom-content
                  display-key="name"
                  id-key="resource_type_id"
                  @search-change="handleSearch">
                  <bk-tree
                    ref="treeRef"
                    children="children"
                    :data="parentResourceList"
                    :empty-text="t('数据搜索为空')"
                    :search="searchValue"
                    :show-node-type-icon="false"
                    @node-click="(data: SystemResourceTypeTree) => handleNodeClick(data, index)">
                    <template #default="{ data }: { data: SystemResourceTypeTree }">
                      <span> {{ data.name }}</span>
                    </template>
                  </bk-tree>
                </bk-select>
              </bk-form-item>
            </div>
            <div class="field-operation">
              <div class="icon-group">
                <audit-icon
                  style="margin-right: 10px; cursor: pointer;"
                  type="add-fill"
                  @click="handleAdd(index)" />
                <audit-icon
                  v-bk-tooltips="{
                    content: t('至少保留一个'),
                    disabled: formData.renderData.length > 1,
                  }"
                  :class="[formData.renderData.length <= 1 ? 'delete-icon-disabled' : 'delete-icon']"
                  type="reduce-fill"
                  @click="handleDelete(index)" />
              </div>
            </div>
          </div>
        </template>
      </audit-form>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import type SystemResourceTypeTree from '@model/meta/system-resource-type-tree';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'updateAction'): void;
  }

  interface ResourceFieldType {
    action_id: string,
    name: string,
    resource_type_ids: string,
    isSelected: boolean,
  }

  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const route = useRoute();
  const { messageSuccess } = useMessage();

  const singleSelectRef = ref();
  const batchSelectRef = ref();
  const batchPopover = ref();
  const tableFormRef = ref();

  const isSelectedAll = ref(false);
  const searchValue = ref('');

  const formData  = ref<{
    resource_type_ids: string,
    renderData: ResourceFieldType[],
  }>({
    resource_type_ids: '',
    renderData: [{
      action_id: '',
      name: '',
      resource_type_ids: '',
      isSelected: false,
    }],
  });

  // 获取父级资源
  const {
    data: parentResourceList,
  }  = useRequest(MetaManageService.fetchParentResourceType, {
    defaultParams: {
      system_id: route.params.id,
    },
    defaultValue: [],
    manual: true,
  });

  const handleSearch = (keyword: string) => {
    searchValue.value = keyword;
  };

  const handleNodeClick = (data: SystemResourceTypeTree, typeOrIndex: string | number) => {
    // 根据类型选择对应的select引用
    const currentSelectRef = typeOrIndex === 'batch' ? batchSelectRef.value : singleSelectRef.value[typeOrIndex];

    // 设置选中项并关闭弹窗
    currentSelectRef.selected = [{
      value: data.resource_type_id,
      label: data.name,
    }];
    currentSelectRef.hidePopover();

    // 更新表单数据
    formData.value.resource_type_ids = data.resource_type_id;
  };

  const handleSubmitBatch = () => {
    formData.value.renderData = formData.value.renderData.map(item => ({
      ...item,
      resource_type_ids: formData.value.resource_type_ids,
    }));
    batchPopover.value.hide();
  };

  const handleCancelBatch = () => {
    formData.value.resource_type_ids = '';
    batchPopover.value.hide();
  };

  const handleAdd = (index: number) => {
    // 在对应index后添加新字段
    formData.value.renderData.splice(index + 1, 0, {
      action_id: '',
      name: '',
      resource_type_ids: '',
      isSelected: false,
    });
  };

  const handleDelete = (index: number) => {
    // 只有一个不能再删除
    if (formData.value.renderData.length === 1) {
      return;
    }
    // 在对应index后删除字段
    formData.value.renderData.splice(index, 1);
  };

  defineExpose({
    submit() {
      return tableFormRef.value.validate().then(() => {
        const params = {
          system_id: route.params.id,
          actions: formData.value.renderData.map(item => ({
            action_id: item.action_id,
            name: item.name,
            resource_type_ids: item.resource_type_ids ? [item.resource_type_ids] : [],
            system_id: route.params.id,
          })),
        };
        return MetaManageService.batchCreateAction(params).then(() => {
          messageSuccess(t('批量创建成功'));
          emits('updateAction');
        });
      });
    },
  });
</script>
<style lang="postcss" scoped>
.add-batch-action {
  padding: 24px;

  .icon-group {
    font-size: 14px;
    color: #c4c6cc;
  }
}

.render-field {
  display: flex;
  min-width: 640px;
  overflow: hidden;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-select {
    width: 40px;
    text-align: center;
    background: #fafbfd;
  }

  .field-operation {
    width: 170px;
    padding-left: 16px;
    background: #fafbfd;
    border-left: 1px solid #dcdee5;
  }

  :deep(.field-value) {
    display: flex;
    width: 250px;
    overflow: hidden;
    border-left: 1px solid #dcdee5;
    align-items: center;

    .bk-form-item.is-error {
      .bk-input--text {
        background-color: #ffebeb;
      }
    }

    .bk-form-item {
      width: 100%;
      margin-bottom: 0;

      .bk-input {
        height: 42px;
        border: none;
      }

      .bk-input.is-focused:not(.is-readonly) {
        border: 1px solid #3a84ff;
        outline: 0;
        box-shadow: 0 0 3px #a3c5fd;
      }

      .bk-form-error-tips {
        top: 12px
      }
    }
  }


  .field-header-row {
    display: flex;
    height: 42px;
    font-size: 12px;
    line-height: 40px;
    color: #313238;
    background: #f0f1f5;

    .field-value {
      padding-left: 8px;
    }

    .field-value.is-required {
      &::after {
        margin-left: 4px;
        color: red;
        content: '*';
      }
    }

    .field-select,
    .field-operation {
      background: #f0f1f5;
    }
  }

  .field-row {
    display: flex;
    overflow: hidden;
    font-size: 12px;
    line-height: 42px;
    color: #63656e;
    border-top: 1px solid #dcdee5;
  }
}
</style>
