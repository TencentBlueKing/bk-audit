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
              <template v-if="batchItem.value === 'ancestor'">
                <!-- 批量编辑选择所属父级资源 -->
                <batch-ancestor
                  :parent-resource-list="parentResourceList"
                  @cancel="handleCancelPopover"
                  @update-ancestor="handleUpdateSelectedAncestor">
                  <template #subTitle>
                    <span>({{ selectedItem.length === formData.renderData.length
                      ? t('全部资源')
                      : t('已选择资源', { count: selectedItem.length }) }})</span>
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
                      ? t('全部资源')
                      : t('已选择资源', { count: selectedItem.length }) }})</span>
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
            v-model="isSelectedAll"
            :indeterminate="isIndeterminate" />
        </div>
        <div class="field-value is-required">
          <span
            v-bk-tooltips="{
              content: t('在实现资源反向拉取协议时，审计中心会基于资源类型ID，向接入方提供的回调地址请求资源实例。并用于操作日志上报中。'),
              placement: 'top-start',
              extCls: 'resource-type-id-tooltips'
            }"
            class="tips">
            {{ t('资源ID') }}
          </span>
        </div>
        <div class="field-value is-required">
          {{ t('资源名称') }}
        </div>
        <div class="field-value">
          <span
            v-bk-tooltips="{
              content: t('多个资源类型之间支持定义父子拓扑结构。资源拓扑主要是面向「资源之间有层级或有包含关系」的场景，例如业务（业务也被认为是一种顶层资源）下包含主机、脚本等其他资源类型。'),
              placement: 'top-start',
              extCls: 'ancestor-tooltips'
            }"
            class="tips">
            {{ t('所属父级资源') }}
          </span>
          <bk-popover
            ref="ancestorPopover"
            placement="bottom"
            theme="light"
            trigger="click"
            width="380">
            <audit-icon
              style="margin-left: 4px;color: #3a84ff; cursor: pointer;"
              type="piliangbianji" />
            <template #content>
              <!-- 批量编辑所有所属父级资源 -->
              <batch-ancestor
                :parent-resource-list="parentResourceList"
                @cancel="handleCancelPopover"
                @update-ancestor="handleUpdateAllAncestor">
                <template #subTitle>
                  <span>({{ t('全部资源') }})</span>
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
              style="margin-left: 4px;color: #3a84ff; cursor: pointer;"
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
                :property="`renderData[${index}].resource_type_id`"
                required
                :rules="[
                  { message: t('不能为空'), trigger: 'change', validator: (value: string) => !!value},
                  { message: t('ID重复，请修改'), trigger: 'change', validator: (value: string) => {
                    // 检查当前表单中是否有重复
                    const duplicatesInForm = formData.renderData.filter(
                      (item, idx) => item.resource_type_id === value && idx !== index
                    );
                    // 检查props传入的资源类型列表中是否有重复
                    const duplicatesInProps = resourceTypeList.filter(
                      item => item.resource_type_id === value
                    );
                    if (duplicatesInForm.length > 0 || duplicatesInProps.length > 0) {
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
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-select
                  ref="rowSelectRef"
                  v-model="item.ancestor"
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
                  class="icon-item"
                  type="add-fill"
                  @click="handleAdd(index)" />
                <audit-icon
                  v-bk-tooltips="{
                    content: formData.renderData.length > 1 ? t('删除') : t('至少保留一个'),
                  }"
                  class="icon-item"
                  :class="[formData.renderData.length <= 1 ? 'delete-icon-disabled' : '']"
                  type="reduce-fill"
                  @click="handleDelete(index)" />
                <audit-icon
                  v-bk-tooltips="{
                    content: t('克隆'),
                  }"
                  class="icon-item"
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

  import type SystemResourceTypeModel from '@model/meta/system-resource-type';
  import type SystemResourceTypeTree from '@model/meta/system-resource-type-tree';

  import SensitivityTipsTable from '@views/system-manage/detail/components/access-model/components/sensitivity-tips/table.vue';

  import BatchAncestor from './batch-ancestor.vue';
  import BatchSensitivity from './batch-sensitivity.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'updateResource'): void;
  }

  interface Props {
    resourceTypeList: SystemResourceTypeModel[];
    sensitivityList: Array<{
      label: string;
      value: number;
    }>
  }

  interface ResourceFieldType {
    resource_type_id: string,
    name: string,
    ancestor: string,
    sensitivity: string,
    isSelected: boolean,
  }

  defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const { messageSuccess } = useMessage();

  const rowSelectRef = ref();
  const tableFormRef = ref();
  const ancestorPopover = ref();
  const sensitivityPopover = ref();
  const batchSelectPopover = ref();

  const isSelectedAll = ref(false);
  const searchValue = ref('');
  const isShowBatch = ref(false);

  const formData  = ref<{
    ancestor: string,
    sensitivity: string,
    renderData: ResourceFieldType[],
  }>({
    ancestor: '',
    sensitivity: '',
    renderData: [{
      resource_type_id: '',
      name: '',
      ancestor: '',
      sensitivity: '',
      isSelected: false,
    }],
  });

  const isIndeterminate = computed(() => {
    const selectedCount = formData.value.renderData.filter(item => item.isSelected).length;
    if (selectedCount > 0 && selectedCount === formData.value.renderData.length) {
      // eslint-disable-next-line vue/no-side-effects-in-computed-properties
      isSelectedAll.value = true;
    }
    return selectedCount > 0 && selectedCount < formData.value.renderData.length;
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

  const batchList = ref([{
    label: t('所属父级资源'),
    value: 'ancestor',
  }, {
    label: t('敏感等级'),
    value: 'sensitivity',
  }]);

  const handleShow = () => {
    isShowBatch.value = !isShowBatch.value;
    if (!isShowBatch.value) {
      // 清空选中状态
      formData.value.renderData = formData.value.renderData.map(item => ({
        ...item,
        isSelected: false,
      }));
      isSelectedAll.value = false;
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

  const handleUpdateSelectedAncestor = (value: string, selectedItems: Array<{
    label: string;
    value: string;
  }>) => {
    // 只更新选中部分
    formData.value.renderData = formData.value.renderData.map((item) => {
      // 批量操作且该项被选中 -> 更新该属性
      if (item.isSelected) {
        return {
          ...item,
          ancestor: value,
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
        };
      }
      return item;
    });

    // 关闭批量操作下拉菜单
    isShowBatch.value = false;
  };

  const handleUpdateAllAncestor = (value: string, selectedItems: Array<{
    label: string;
    value: string;
  }>) => {
    // 更新所有项
    formData.value.renderData = formData.value.renderData.map(item => ({
      ...item,
      ancestor: value,
    }));

    nextTick(() => {
      rowSelectRef.value.forEach((item: any) => {
        // eslint-disable-next-line no-param-reassign
        item.selected = selectedItems;
      });
    });

    // 关闭表头pop
    ancestorPopover.value.hide();
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
    // 关闭批量操作下拉菜单或表头pop
    if (ancestorPopover.value) {
      ancestorPopover.value.hide();
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
    formData.value.renderData[index].ancestor = data.resource_type_id;
    rowSelectRef.value[index].hidePopover();
  };

  const handleAdd = (index: number) => {
    // 在对应index后添加新字段
    formData.value.renderData.splice(index + 1, 0, {
      resource_type_id: '',
      name: '',
      ancestor: '',
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
      resource_type_id: '',
      name: item.name,
      ancestor: item.ancestor,
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

  // formData.value.renderData所有项的isSelected都为false时，isSelectedAll为false
  watch(() => formData.value.renderData, (newValue) => {
    if (newValue.every(item => !item.isSelected)) {
      isSelectedAll.value = false;
    }
  }, { deep: true });

  defineExpose({
    submit() {
      return tableFormRef.value.validate().then(() => {
        const params = {
          resource_types: formData.value.renderData.map(item => ({
            resource_type_id: item.resource_type_id,
            name: item.name,
            ancestor: item.ancestor ? [item.ancestor] : [],
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
    font-size: 16px;
    color: #979ba5;

    .icon-item {
      margin-right: 10px;
      cursor: pointer;

      &:hover:not(.delete-icon-disabled) {
        color: #4d4f56;
      }
    }

    .delete-icon-disabled {
      color: #dcdee5;
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
