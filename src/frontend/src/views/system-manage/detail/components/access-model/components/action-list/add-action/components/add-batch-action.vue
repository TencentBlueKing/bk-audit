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
    <bk-dropdown
      :disabled="selectedItem.length === 0"
      :is-show="isShowBatch"
      style="margin-bottom: 16px;"
      trigger="manual">
      <bk-button
        class="ml10"
        :disabled="selectedItem.length === 0"
        @click="handleShow">
        {{ t('批量修改') }}
        <audit-icon
          style="margin-left: 10px;"
          type="angle-line-down" />
      </bk-button>
      <template #content>
        <bk-dropdown-menu>
          <bk-popover
            v-for="batchItem in batchList"
            :key="batchItem.value"
            ref="batchSelectPopover"
            placement="right"
            theme="light"
            trigger="click"
            width="380">
            <bk-dropdown-item>
              <span>{{ batchItem.label }}</span>
            </bk-dropdown-item>
            <template #content>
              <template v-if="batchItem.value === 'resource_type_ids'">
                <!-- 批量编辑选择依赖资源 -->
                <batch-ancestor
                  :label="t('依赖资源')"
                  :parent-resource-list="parentResourceList"
                  :placeholder="t('请选择依赖资源')"
                  :title="t('批量编辑依赖资源')"
                  @cancel="handleCancelPopover"
                  @update-ancestor="handleUpdateSelectedResourceTypeIds">
                  <template #subTitle>
                    <span>({{ selectedItem.length === formData.renderData.length
                      ? t('全部操作')
                      : t('已选择操作', { count: selectedItem.length }) }})</span>
                  </template>
                </batch-ancestor>
              </template>
              <template v-if="batchItem.value === 'sensitivity'">
                <!-- 批量编辑选择敏感等级 -->
                <batch-sensitivity
                  :sensitivity-list="sensitivityList"
                  @cancel="handleCancelPopover"
                  @update-sensitivity="handleUpdateSelectedSensitivity">
                  <template #subTitle>
                    <span>({{ selectedItem.length === formData.renderData.length
                      ? t('全部操作')
                      : t('已选择操作', { count: selectedItem.length }) }})</span>
                  </template>
                </batch-sensitivity>
              </template>
            </template>
          </bk-popover>
        </bk-dropdown-menu>
      </template>
    </bk-dropdown>
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
        <div
          v-if="!isSimpleSystem"
          class="field-value">
          <span
            v-bk-tooltips="{
              content: t('在实现资源反向拉取协议时，审计中心会基于资源类型ID，向接入方提供的回调地址请求资源实例。并用于操作日志上报中。'),
              placement: 'top-start',
              extCls: 'resource-type-id-tooltips'
            }"
            class="tips">
            {{ t('依赖资源') }}
          </span>
          <bk-popover
            ref="resourceTypeIdsRef"
            placement="bottom"
            theme="light"
            trigger="click"
            width="380">
            <audit-icon
              style="margin-left: 4px;color: #3a84ff;cursor: pointer;"
              type="piliangbianji" />
            <template #content>
              <!-- 批量编辑所有依赖资源 -->
              <batch-ancestor
                :label="t('依赖资源')"
                :parent-resource-list="parentResourceList"
                :placeholder="t('请选择依赖资源')"
                :title="t('批量编辑依赖资源')"
                @cancel="handleCancelPopover"
                @update-ancestor="handleUpdateAllResourceTypeIds">
                <template #subTitle>
                  <span>({{ t('全部操作') }})</span>
                </template>
              </batch-ancestor>
            </template>
          </bk-popover>
        </div>
        <div class="field-value  is-required">
          <bk-popover
            placement="bottom"
            theme="light">
            <span class="tips">
              {{ t('敏感等级') }}
            </span>
            <template #content>
              <sensitivity-tips-table />
            </template>
          </bk-popover>
          <bk-popover
            ref="sensitivityPopover"
            placement="bottom"
            theme="light"
            trigger="click"
            width="380">
            <audit-icon
              style="margin-left: 4px;color: #3a84ff;cursor: pointer;"
              type="piliangbianji" />
            <template #content>
              <!-- 批量编辑所有敏感等级 -->
              <batch-sensitivity
                :sensitivity-list="sensitivityList"
                @cancel="handleCancelPopover"
                @update-sensitivity="handleUpdateAllSensitivity">
                <template #subTitle>
                  <span>({{ t('全部资源') }})</span>
                </template>
              </batch-sensitivity>
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
                    // 检查当前表单中是否有重复
                    const duplicatesInForm = formData.renderData.filter(
                      (item, idx) => item.action_id === value && idx !== index
                    );
                    // 检查props传入的资源类型列表中是否有重复
                    const duplicatesInProps = actionList.filter(
                      item => item.action_id === value
                    );
                    if (duplicatesInForm.length > 0 || duplicatesInProps.length > 0) {
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
                required
                :rules="[
                  { message: t('不能为空'), trigger: 'change', validator: (value: string) => !!value },
                  { message: t('仅可由汉字、小写英文字母、数字、“-”组成'), trigger: 'change', validator: (value: string) => {
                    if (/^[\u4e00-\u9fa5a-z0-9-]+$/.test(value)) {
                      return true;
                    }
                    return false;
                  } },
                ]">
                <bk-input
                  ref="fieldItemRef"
                  v-model="item.name" />
              </bk-form-item>
            </div>
            <div
              v-if="!isSimpleSystem"
              class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-select
                  ref="rowSelectRef"
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
                    @node-click="(data: SystemResourceTypeTree) => handleRowNodeClick(data, index)">
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
                    :id="selectItem.value"
                    :key="selectIndex"
                    :name="selectItem.label">
                    <span
                      :style="{
                        color: getSensitivityColor(selectItem.value)
                      }">{{ selectItem.label }}</span>
                  </bk-option>
                </bk-select>
              </bk-form-item>
            </div>
            <div class="field-operation">
              <div class="icon-group">
                <audit-icon
                  v-bk-tooltips="{
                    content: t('添加'),
                  }"
                  style="margin-right: 10px; cursor: pointer;"
                  type="add-fill"
                  @click="handleAdd(index)" />
                <audit-icon
                  v-bk-tooltips="{
                    content: formData.renderData.length > 1 ? t('删除') : t('至少保留一个'),
                  }"
                  :class="[formData.renderData.length <= 1 ? 'delete-icon-disabled' : 'delete-icon']"
                  type="reduce-fill"
                  @click="handleDelete(index)" />
                <audit-icon
                  v-bk-tooltips="{
                    content: t('克隆'),
                  }"
                  style="margin-left: 10px; cursor: pointer;"
                  type="fuzhi"
                  @click="handleClone(item)" />
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
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import SystemActionModel from '@model/meta/system-action';
  import type SystemResourceTypeTree from '@model/meta/system-resource-type-tree';

  import SensitivityTipsTable from '@views/system-manage/detail/components/access-model/components/sensitivity-tips/table.vue';

  import BatchAncestor from '../../../resource-type-list/components/add-resource/components/batch-ancestor.vue';
  import BatchSensitivity from '../../../resource-type-list/components/add-resource/components/batch-sensitivity.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface Props {
    actionList: SystemActionModel[],
    sensitivityList: Array<{
      label: string;
      value: number;
    }>
  }
  interface Emits {
    (e: 'updateAction'): void;
  }

  interface ResourceFieldType {
    action_id: string,
    name: string,
    resource_type_ids: string,
    sensitivity: string,
    isSelected: boolean,
  }

  defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const route = useRoute();
  const { messageSuccess } = useMessage();

  const rowSelectRef = ref();
  const sensitivityPopover = ref();
  const tableFormRef = ref();
  const batchSelectPopover = ref();
  const resourceTypeIdsRef = ref();

  const isSelectedAll = ref(false);
  const searchValue = ref('');
  const isShowBatch = ref(false);

  const formData  = ref<{
    resource_type_ids: string,
    sensitivity: string,
    renderData: ResourceFieldType[],
  }>({
    resource_type_ids: '',
    sensitivity: '',
    renderData: [{
      action_id: '',
      name: '',
      resource_type_ids: '',
      sensitivity: '',
      isSelected: false,
    }],
  });

  const isSimpleSystem = computed(() => route.query.type === 'simple');

  const batchList = computed(() => {
    const list = [{
      label: t('敏感等级'),
      value: 'sensitivity',
    }];
    if (!isSimpleSystem.value) {
      list.unshift({
        label: t('依赖资源'),
        value: 'resource_type_ids',
      });
    }
    return list;
  });

  // 根据敏感等级值获取对应颜色
  const getSensitivityColor = (value: number) => {
    const colorMap: Record<number, string> = {
      1: '#979ba5', // 不敏感 - 灰色
      2: '#52c41a', // 低敏感 - 绿色
      3: '#faad14', // 中敏感 - 橙色
      4: '#f5222d', // 高敏感 - 红色
    };
    return colorMap[value] || '#333'; // 默认颜色
  };

  const handleShow = () => {
    isShowBatch.value = !isShowBatch.value;
    if (!isShowBatch.value) {
      // 清空选中状态
      formData.value.renderData = formData.value.renderData.map(item => ({
        ...item,
        isSelected: false,
      }));
    }
  };

  const selectedItem = computed(() => formData.value.renderData.filter(item => item.isSelected));

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

  const handleUpdateSelectedResourceTypeIds = (value: string, selectedItems: Array<{
    label: string;
    value: string;
  }>) => {
    // 只更新选中部分
    formData.value.renderData = formData.value.renderData.map((item) => {
      // 批量操作且该项被选中 -> 更新该属性
      if (item.isSelected) {
        return {
          ...item,
          resource_type_ids: value,
          isSelected: false,
        };
      }
      return item;
    });
    nextTick(() => {
      rowSelectRef.value.forEach((item: any) => {
        if (item.selected[0] && item.selected[0].value === value) {
          // eslint-disable-next-line no-param-reassign
          item.selected = selectedItems;
        }
      });
    });

    // 关闭批量操作下拉菜单
    isShowBatch.value = false;
  };

  const handleUpdateSelectedSensitivity = (value: string) => {
    // 只更新选中部分
    formData.value.renderData = formData.value.renderData.map((item) => {
      // 批量操作且该项被选中 -> 更新该属性
      if (item.isSelected) {
        return {
          ...item,
          sensitivity: value,
          isSelected: false,
        };
      }
      return item;
    });

    // 关闭批量操作下拉菜单
    isShowBatch.value = false;
  };

  const handleUpdateAllResourceTypeIds = (value: string, selectedItems: Array<{
    label: string;
    value: string;
  }>) => {
    // 更新所有项
    formData.value.renderData = formData.value.renderData.map(item => ({
      ...item,
      resource_type_ids: value,
    }));

    nextTick(() => {
      rowSelectRef.value.forEach((item: any) => {
        // eslint-disable-next-line no-param-reassign
        item.selected = selectedItems;
      });
    });

    // 关闭表头pop
    resourceTypeIdsRef.value.hide();
  };

  const handleUpdateAllSensitivity = (value: string) => {
    // 更新所有项
    formData.value.renderData = formData.value.renderData.map(item => ({
      ...item,
      sensitivity: value,
    }));

    // 关闭表头pop
    sensitivityPopover.value.hide();
  };

  const handleCancelPopover = () => {
    // 清空选择项
    formData.value.renderData = formData.value.renderData.map(item => ({
      ...item,
      isSelected: false,
    }));

    // 关闭批量操作下拉菜单或表头pop
    if (resourceTypeIdsRef.value) {
      resourceTypeIdsRef.value.hide();
    }
    if (sensitivityPopover.value) {
      sensitivityPopover.value.hide();
    }
    isShowBatch.value = false;
  };

  // 单个节点(row)点击处理函数
  const handleRowNodeClick = (data: SystemResourceTypeTree, index: number) => {
    rowSelectRef.value[index].selected = [{
      value: data.resource_type_id,
      label: data.name,
    }];
    formData.value.renderData[index].resource_type_ids = data.resource_type_id;
    rowSelectRef.value[index].hidePopover();
  };

  const handleAdd = (index: number) => {
    // 在对应index后添加新字段
    formData.value.renderData.splice(index + 1, 0, {
      action_id: '',
      name: '',
      resource_type_ids: '',
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

  // 克隆
  const handleClone = (item: ResourceFieldType) => {
    // 在formData.value.renderData中添加新字段
    formData.value.renderData.push({
      action_id: '',
      name: item.name,
      resource_type_ids: item.resource_type_ids,
      sensitivity: item.sensitivity,
      isSelected: false,
    });
  };

  watch(() => isSelectedAll.value, (newValue) => {
    formData.value.renderData = formData.value.renderData.map(item => ({
      ...item,
      isSelected: newValue,
    }));
  });

  defineExpose({
    submit() {
      return tableFormRef.value.validate().then(() => {
        const params = {
          system_id: route.params.id,
          actions: formData.value.renderData.map(item => ({
            action_id: item.action_id,
            name: item.name,
            resource_type_ids: item.resource_type_ids ? [item.resource_type_ids] : [],
            sensitivity: item.sensitivity,
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
    flex: 1;
    overflow: hidden;
    border-left: 1px solid #dcdee5;
    align-items: center;

    .tips {
      line-height: 16px;
      cursor: pointer;
      border-bottom: 1px dashed #979ba5;
    }

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
