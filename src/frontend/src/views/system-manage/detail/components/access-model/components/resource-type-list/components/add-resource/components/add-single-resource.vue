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
  <div class="add-single-resource">
    <h3 style="margin-bottom: 16px;">
      {{ t('基础信息') }}
    </h3>
    <bk-radio-group
      v-model="addType"
      type="card">
      <bk-radio-button label="customize">
        {{ t('自定义') }}
      </bk-radio-button>
      <bk-radio-button
        v-bk-tooltips="t('暂不支持，敬请期待')"
        disabled
        label="other">
        {{ t('从其他系统引入') }}
      </bk-radio-button>
    </bk-radio-group>
    <audit-form
      ref="formRef"
      class="customize-form"
      form-type="vertical"
      :model="formData"
      :rules="rules">
      <div class="flex-center">
        <bk-form-item
          class="is-required mr16"
          label=""
          label-width="100"
          property="resource_type_id"
          required
          style="flex: 1;">
          <template #label>
            <span
              v-bk-tooltips="{
                content: t('在实现资源反向拉取协议时，审计中心会基于资源类型ID，向接入方提供的回调地址请求资源实例。并用于操作日志上报中。'),
                placement: 'top-start',
                extCls: 'resource-type-id-tooltips'
              }"
              style="
                color: #63656e;
                cursor: pointer;
                border-bottom: 1px dashed #979ba5;
              ">
              {{ t('资源类型ID') }}
            </span>
          </template>
          <bk-input
            v-model.trim="formData.resource_type_id"
            :disabled="isEdit"
            :placeholder="t('请输入资源类型ID')"
            style="width: 100%;" />
        </bk-form-item>
        <bk-form-item
          class="is-required mr16"
          :label="t('资源类型名称')"
          label-width="100"
          property="name"
          required
          style="flex: 1;">
          <bk-input
            v-model.trim="formData.name"
            :placeholder="t('请输入，仅可由汉字、小写英文字母、数字、“-”组成')"
            style="width: 100%;" />
        </bk-form-item>
      </div>
      <bk-form-item
        label=""
        label-width="160"
        property="ancestor">
        <template #label>
          <span
            v-bk-tooltips="{
              content: t('多个资源类型之间支持定义父子拓扑结构。资源拓扑主要是面向「资源之间有层级或有包含关系」的场景，例如业务（业务也被认为是一种顶层资源）下包含主机、脚本等其他资源类型。'),
              placement: 'top-start',
              extCls: 'ancestor-tooltips'
            }"
            style="
              color: #63656e;
              cursor: pointer;
              border-bottom: 1px dashed #979ba5;
            ">
            {{ t('所属父级资源') }}
          </span>
        </template>
        <bk-select
          ref="selectRef"
          v-model="formData.ancestor"
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
            label="name"
            node-key="resource_type_id"
            :search="searchValue"
            selectable
            :selected="selected"
            :show-node-type-icon="false"
            @node-click="handleNodeClick" />
        </bk-select>
      </bk-form-item>
      <bk-form-item
        class="sensitivity-level-group"
        :label="t('敏感等级')"
        label-width="160"
        property="sensitivity"
        required>
        <bk-button-group>
          <bk-popover
            v-for="item in sensitivityList"
            :key="item.value"
            ext-cls="sensitivity-tips-pop"
            max-width="408"
            placement="bottom"
            theme="light">
            <bk-button
              :selected="formData.sensitivity === item.value"
              @click="handleSensitivity(item.value)">
              <span>{{ item.label }}</span>
            </bk-button>
            <template #content>
              <sensitivity-tips-list :item="item" />
            </template>
          </bk-popover>
        </bk-button-group>
      </bk-form-item>
    </audit-form>
    <div
      v-if="!isEdit"
      class="other-action">
      <h3 style="margin-bottom: 16px;">
        {{ t('还可以快捷创建该资源的以下操作：') }}
      </h3>
      <bk-checkbox-group v-model="actionArr">
        <bk-checkbox label="create">
          {{ t('新建') }}{{ formData.name }}
        </bk-checkbox>
        <bk-checkbox label="edit">
          {{ t('编辑') }}{{ formData.name }}
        </bk-checkbox>
        <bk-checkbox label="view">
          {{ t('查看') }}{{ formData.name }}
        </bk-checkbox>
        <bk-checkbox label="delete">
          {{ t('删除') }}{{ formData.name }}
        </bk-checkbox>
      </bk-checkbox-group>
    </div>
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import type SystemResourceTypeModel from '@model/meta/system-resource-type';
  import type SystemResourceTypeTree from '@model/meta/system-resource-type-tree';

  import SensitivityTipsList from '@views/system-manage/detail/components/access-model/components/sensitivity-tips/list.vue';

  interface Emits {
    (e: 'updateResource'): void;
  }
  interface Props {
    isEdit: boolean;
    editData: SystemResourceTypeModel;
    resourceTypeList: SystemResourceTypeModel[];
    sensitivityList: Array<{
      label: string;
      value: number;
    }>
  }

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const actionMap = {
    create: '新建',
    edit: '编辑',
    view: '查看',
    delete: '删除',
  };

  const { t } = useI18n();
  const route = useRoute();
  const selectRef = ref();
  const formRef = ref();
  const treeRef = ref();
  const { messageSuccess } = useMessage();
  const addType = ref('customize');
  const formData  = ref({
    resource_type_id: '',
    name: '',
    ancestor: '',
    sensitivity: 1,
  });
  const searchValue = ref('');
  const actionArr = ref([]);
  const selected = ref<Array<string>>([]);

  const rules = {
    resource_type_id: [
      { message: '不能为空', trigger: 'change', validator: (value: string) => !!value },
      { message: 'ID重复，请修改', trigger: 'change', validator: (value: string) => {
        const duplicates = props.resourceTypeList.filter(item => item.resource_type_id === value);
        // 编辑模式且只有一个重复项（即当前编辑的资源本身）时允许通过
        if (duplicates.length > 0 && (!props.isEdit || duplicates.length > 1)) {
          return false;
        }
        return true;
      } },
    ],
    name: [
      { message: '不能为空', trigger: 'change', validator: (value: string) => !!value },
      { message: '仅可由汉字、小写英文字母、数字、“-”组成', trigger: 'change', validator: (value: string) => {
        if (/^[\u4e00-\u9fa5a-z0-9-]+$/.test(value)) {
          return true;
        }
        return false;
      } },
    ],
  };

  if (props.isEdit) {
    nextTick(() => {
      formData.value.resource_type_id = props.editData.resource_type_id;
      formData.value.name = props.editData.name;
      // eslint-disable-next-line prefer-destructuring
      formData.value.ancestor = props.editData.ancestor[0];
      formData.value.sensitivity = props.editData.sensitivity;
    });
  }

  // 添加递归查找函数
  // eslint-disable-next-line max-len
  const findResourceRecursive = (items: SystemResourceTypeTree[], targetId: string): SystemResourceTypeTree | undefined => {
    for (const item of items) {
      if (item.resource_type_id === targetId) {
        return item;
      }
      if (item.children && item.children.length > 0) {
        const found = findResourceRecursive(item.children, targetId);
        if (found) return found;
      }
    }
    return undefined;
  };

  // 获取父级资源
  const {
    data: parentResourceList,
  }  = useRequest(MetaManageService.fetchParentResourceType, {
    defaultParams: {
      system_id: route.params.id,
    },
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      // 编辑反选
      if (formData.value.ancestor && props.isEdit) {
        const finedAncestor = findResourceRecursive(parentResourceList.value, formData.value.ancestor);
        if (finedAncestor) {
          selectRef.value.selected = [{
            value: finedAncestor.resource_type_id,
            label: finedAncestor.name,
          }];
          selected.value = [finedAncestor.resource_type_id];
        }
      }
    },
  });

  const handleSearch = (keyword: string) => {
    searchValue.value = keyword;
  };

  const handleNodeClick = (data: SystemResourceTypeTree) => {
    // 设置select选中
    selectRef.value.selected = [{
      value: data.resource_type_id,
      label: data.name,
    }];
    formData.value.ancestor = data.resource_type_id;
  };

  const handleSensitivity = (value: number) => {
    formData.value.sensitivity = value;
  };

  defineExpose({
    submit() {
      return formRef.value.validate().then(() => {
        const params: Record<string, any> = _.cloneDeep(formData.value);
        if (actionArr.value.length > 0) {
          params.actions_to_create = actionArr.value.map(item => ({
            action_id: `${item}_${params.resource_type_id}`,
            name: `${actionMap[item]}_${params.name}`,
          }));
        }
        params.ancestor = params.ancestor ? [params.ancestor] : [];
        params.system_id = route.params.id;
        params.unique_id = `${route.params.id}:${params.resource_type_id}`;
        // 编辑
        if (props.isEdit) {
          return MetaManageService.updateResourceType(params).then(() => {
            messageSuccess(t('编辑成功'));
            emits('updateResource');
          });
        }
        // 新增
        return MetaManageService.createResourceType(params).then(() => {
          messageSuccess(t('创建成功'));
          emits('updateResource');
        });
      });
    },
  });
</script>
<style scoped lang="postcss">
.add-single-resource {
  padding: 14px 24px;

  .customize-form {
    margin-top: 24px;

    .flex-center {
      display: flex;
      align-items: center;
    }

    .sensitivity-level-group {
      :deep(.bk-button-group) {
        .bk-button {
          &:first-child:hover:not(.is-disabled, .is-selected) {
            color: #979ba5;
            border-color: #979ba5;
          }

          &:first-child.is-selected {
            color: #fff;
            background-color: #979ba5 ;
            border-color: #979ba5;
          }

          &:nth-child(2):hover:not(.is-disabled, .is-selected) {
            color: #2caf5e;
            border-color: #2caf5e ;
          }

          &:nth-child(2).is-selected {
            color: #fff;
            background-color: #2caf5e;
            border-color: #2caf5e;
          }

          &:nth-child(3):hover:not(.is-disabled, .is-selected) {
            color: #2caf5e;
            border-color: #2caf5e ;
          }

          &:nth-child(3).is-selected {
            color: #fff;
            background-color: #2caf5e;
            border-color: #2caf5e;
          }

          &:nth-child(4):hover:not(.is-disabled, .is-selected) {
            color: #ff9c01;
            border-color: #ff9c01;
          }

          &:nth-child(4).is-selected {
            color: #fff;
            background-color: #ff9c01;
            border-color: #ff9c01;
          }

          &:nth-child(5):hover:not(.is-disabled, .is-selected) {
            color: #ff9c01;
            border-color: #ff9c01;
          }

          &:nth-child(5).is-selected {
            color: #fff;
            background-color: #ff9c01;
            border-color: #ff9c01;
          }

          &:nth-child(6):hover:not(.is-disabled, .is-selected) {
            color: #ea3636;
            border-color: #ea3636;
          }

          &:nth-child(6).is-selected {
            color: #fff;
            background-color: #ea3636;
            border-color: #ea3636;
          }

          &:nth-child(7):hover:not(.is-disabled, .is-selected) {
            color: #ea3636;
            border-color: #ea3636;
          }

          &:nth-child(7).is-selected {
            color: #fff;
            background-color: #ea3636;
            border-color: #ea3636;
          }
        }
      }
    }
  }

  .other-action {
    padding: 16px;
    background: #f5f7fa;
  }
}
</style>
<style>
.resource-type-id-tooltips {
  max-width: 280px;
}

.ancestor-tooltips {
  max-width: 350px;
}
</style>
