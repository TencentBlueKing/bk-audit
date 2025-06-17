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
  <div class="add-batch-resource">
    <div class="render-field">
      <div class="field-header-row">
        <div class="field-select">
          <bk-checkbox
            v-model="isSelectedAll" />
        </div>
        <div class="field-value is-required">
          {{ t('资源ID') }}
        </div>
        <div class="field-value is-required">
          {{ t('资源名称') }}
        </div>
        <div class="field-value">
          {{ t('所属父级资源') }}
          <bk-popover
            ref="ancestorsPopover"
            placement="bottom"
            theme="light"
            trigger="click"
            width="380">
            <audit-icon
              style="margin-left: 4px;color: #3a84ff; cursor: pointer;"
              type="edit-fill" />
            <template #content>
              <h3>{{ t('批量编辑所属父级资源') }}</h3>
              <audit-form
                ref="formRef"
                form-type="vertical"
                :model="formData">
                <bk-form-item
                  :label="t('所属父级资源')"
                  label-width="160"
                  property="ancestors">
                  <bk-select
                    ref="batchSelectRef"
                    v-model="formData.ancestors"
                    :auto-height="false"
                    custom-content
                    display-key="name"
                    id-key="resource_type_id"
                    :popover-options="{ boundary: 'parent' }"
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
                  :disabled="!formData.ancestors"
                  size="small"
                  theme="primary"
                  @click="handleSubmitBatch('ancestors')">
                  {{ t('确定') }}
                </bk-button>
                <bk-button
                  size="small"
                  @click="handleCancelBatch('ancestors')">
                  {{ t('取消') }}
                </bk-button>
              </div>
            </template>
          </bk-popover>
        </div>
        <div class="field-value  is-required">
          {{ t('敏感等级') }}
          <bk-popover
            ref="sensitivityPopover"
            placement="bottom"
            theme="light"
            trigger="click"
            width="380">
            <audit-icon
              style="margin-left: 4px;color: #3a84ff;"
              type="edit-fill" />
            <template #content>
              <h3>{{ t('批量编辑敏感等级') }}</h3>
              <audit-form
                ref="formRef"
                form-type="vertical"
                :model="formData">
                <bk-form-item
                  :label="t('敏感等级')"
                  label-width="160"
                  property="sensitivity">
                  <bk-select
                    v-model="formData.sensitivity"
                    class="batch-sensitivity"
                    filterable
                    :input-search="false"
                    :placeholder="t('请选择')"
                    :popover-options="{ boundary: 'parent' }"
                    :search-placeholder="t('请输入关键字')">
                    <bk-option
                      v-for="(item, index) in sensitivityList"
                      :key="index"
                      :label="item.label"
                      :value="item.value" />
                  </bk-select>
                </bk-form-item>
              </audit-form>
              <div style="margin-top: 8px; font-size: 14px; line-height: 22px; color: #3a84ff; text-align: right;">
                <bk-button
                  class="mr8"
                  :disabled="!formData.sensitivity"
                  size="small"
                  theme="primary"
                  @click="handleSubmitBatch('sensitivity')">
                  {{ t('确定') }}
                </bk-button>
                <bk-button
                  size="small"
                  @click="handleCancelBatch('sensitivity')">
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
                :property="`renderData[${index}].resource_type_id`"
                required
                :rules="[
                  { message: '不能为空', trigger: 'change', validator: (value: string) => !!value},
                  { message: 'ID重复，请修改', trigger: 'change', validator: (value: string) => {
                    const duplicates = formData.renderData.filter(
                      (item, idx) => item.resource_type_id === value && idx !== index
                    );
                    if (duplicates.length > 0) {
                      return false;
                    }
                    return true;
                  }}
                ]">
                <bk-input
                  ref="fieldItemRef"
                  v-model="item.resource_type_id" />
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
                  v-model="item.ancestors"
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
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0"
                :property="`renderData[${index}].sensitivity`"
                required>
                <bk-select
                  v-model="item.sensitivity"
                  class="bk-select"
                  filterable
                  :input-search="false"
                  :placeholder="t('请选择')"
                  :search-placeholder="t('请输入关键字')">
                  <bk-option
                    v-for="(selectItem, selectIndex) in sensitivityList"
                    :key="selectIndex"
                    :label="selectItem.label"
                    :value="selectItem.value" />
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
    (e: 'updateResource'): void;
  }

  interface ResourceFieldType {
    resource_type_id: string,
    name: string,
    ancestors: string,
    sensitivity: string,
    isSelected: boolean,
  }

  const emits = defineEmits<Emits>();

  const sensitivityList = [
    {
      value: 2,
      label: '二级(低)',
    },
    {
      value: 3,
      label: '三级(中)',
    },
    {
      value: 4,
      label: '四级(高)',
    },
  ];

  const { t } = useI18n();
  const route = useRoute();
  const { messageSuccess } = useMessage();

  const singleSelectRef = ref();
  const batchSelectRef = ref();
  const tableFormRef = ref();
  const ancestorsPopover = ref();
  const sensitivityPopover = ref();

  const isSelectedAll = ref(false);
  const searchValue = ref('');

  const formData  = ref<{
    ancestors: string,
    sensitivity: string,
    renderData: ResourceFieldType[],
  }>({
    ancestors: '',
    sensitivity: '',
    renderData: [{
      resource_type_id: '',
      name: '',
      ancestors: '',
      sensitivity: '',
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
    formData.value.ancestors = data.resource_type_id;
  };

  const handleSubmitBatch = (type: 'ancestors' | 'sensitivity') => {
    if (type === 'ancestors') {
      // 更新formData.value.ancestors
      formData.value.renderData = formData.value.renderData.map(item => ({
        ...item,
        ancestors: formData.value.ancestors,
      }));
      ancestorsPopover.value.hide();
      return;
    }
    // 更新formData.value.sensitivity
    formData.value.renderData = formData.value.renderData.map(item => ({
      ...item,
      sensitivity: formData.value.sensitivity,
    }));
    sensitivityPopover.value.hide();
  };

  const handleCancelBatch = (type: 'ancestors' | 'sensitivity') => {
    if (type === 'ancestors') {
      formData.value.ancestors = '';
      ancestorsPopover.value.hide();
      return;
    }
    formData.value.sensitivity = '';
    sensitivityPopover.value.hide();
  };

  const handleAdd = (index: number) => {
    // 在对应index后添加新字段
    formData.value.renderData.splice(index + 1, 0, {
      resource_type_id: '',
      name: '',
      ancestors: '',
      sensitivity: '',
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
          resource_types: formData.value.renderData.map(item => ({
            resource_type_id: item.resource_type_id,
            name: item.name,
            ancestors: item.ancestors ? [item.ancestors] : [],
            sensitivity: item.sensitivity,
            system_id: route.params.id,
          })),
        };
        return MetaManageService.batchCreateResourceType(params).then(() => {
          messageSuccess(t('批量创建成功'));
          emits('updateResource');
        });
      });
    },
  });
</script>
<style lang="postcss" scoped>
.add-batch-resource {
  padding: 24px;

  .icon-group {
    font-size: 14px;
    color: #c4c6cc;

    .delete-icon {
      cursor: pointer;
    }

    .delete-icon-disabled {
      cursor: not-allowed;
    }
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
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
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
    width: 160px;
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
