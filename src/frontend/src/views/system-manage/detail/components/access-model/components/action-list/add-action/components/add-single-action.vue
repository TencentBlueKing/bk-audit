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
    <audit-form
      ref="formRef"
      class="customize-form"
      form-type="vertical"
      :model="formData"
      :rules="rules">
      <div class="flex-center">
        <bk-form-item
          class="is-required mr16"
          :disabled="isEdit"
          :label="t('操作ID')"
          label-width="100"
          property="action_id"
          required
          style="flex: 1;">
          <bk-input
            v-model.trim="formData.action_id"
            :disabled="isEdit"
            :placeholder="t('请输入操作ID')"
            style="width: 100%;" />
        </bk-form-item>
        <bk-form-item
          class="is-required mr16"
          :label="t('操作名称')"
          label-width="100"
          property="name"
          required
          style="flex: 1;">
          <bk-input
            v-model.trim="formData.name"
            :placeholder="t('请输入操作名称')"
            style="width: 100%;" />
        </bk-form-item>
      </div>
      <bk-form-item
        v-if="!isSimpleSystem"
        :label="t('依赖资源')"
        label-width="160"
        property="description">
        <bk-select
          ref="selectRef"
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
            label="name"
            node-key="resource_type_id"
            :search="searchValue"
            selectable
            :selected="selected"
            :show-node-type-icon="false"
            @node-click="handleNodeClick" />
        </bk-select>
        <bk-button
          text
          theme="primary"
          @click="addResourceType">
          {{ t('新建资源类型') }}
        </bk-button>
      </bk-form-item>
      <bk-form-item
        class="sensitivity-level-group"
        :label="t('敏感等级')"
        label-width="160"
        property="sensitivity">
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
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { computed, nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import SystemActionModel from '@model/meta/system-action';
  import type SystemResourceTypeTree from '@model/meta/system-resource-type-tree';

  import SensitivityTipsList from '@views/system-manage/detail/components/access-model/components/sensitivity-tips/list.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'updateAction'): void;
    (e: 'addResourceType'): void;
  }

  interface Props {
    isEdit: boolean;
    editData: SystemActionModel;
    actionList: Array<SystemActionModel>;
    sensitivityList: Array<{
      label: string;
      value: number;
    }>
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const formRef = ref();
  const { messageSuccess } = useMessage();
  const selectRef = ref();
  const treeRef = ref();
  const route = useRoute();

  const formData  = ref({
    action_id: '',
    name: '',
    resource_type_ids: '',
    sensitivity: 1,
  });
  const searchValue = ref('');
  const selected = ref<Array<string>>([]);

  const isSimpleSystem = computed(() => route.query.type === 'simple');

  const rules = {
    action_id: [
      { message: '不能为空', trigger: 'change', validator: (value: string) => !!value },
      { message: 'ID重复，请修改', trigger: 'change', validator: (value: string) => {
        const duplicates = props.actionList.filter(item => item.action_id === value);
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
      formData.value.action_id = props.editData.action_id;
      formData.value.name = props.editData.name;
      formData.value.sensitivity = props.editData.sensitivity;
      // eslint-disable-next-line prefer-destructuring
      formData.value.resource_type_ids = props.editData.resource_type_ids[0];
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
      if (formData.value.resource_type_ids && props.isEdit) {
        const finedAncestor = findResourceRecursive(parentResourceList.value, formData.value.resource_type_ids);
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

  const addResourceType = () => {
    emits('addResourceType');
  };

  const handleNodeClick = (data: SystemResourceTypeTree) => {
    // 设置select选中
    selectRef.value.selected = [{
      value: data.resource_type_id,
      label: data.name,
    }];
    formData.value.resource_type_ids = data.resource_type_id;
  };

  const handleSensitivity = (value: number) => {
    formData.value.sensitivity = value;
  };

  defineExpose({
    submit() {
      return formRef.value.validate().then(() => {
        const params: Record<string, any> = _.cloneDeep(formData.value);
        params.resource_type_ids = params.resource_type_ids ? [params.resource_type_ids] : [];
        params.system_id = route.params.id;
        params.unique_id = `${route.params.id}:${params.action_id}`;

        if (props.isEdit) {
          return  MetaManageService.updateAction(params).then(() => {
            messageSuccess(t('更新成功'));
            emits('updateAction');
          });
        }
        return MetaManageService.createAction(params).then(() => {
          messageSuccess(t('新增成功'));
          emits('updateAction');
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
            background-color: #979ba5;
            border-color: #979ba5;
          }

          &:nth-child(2):hover:not(.is-disabled, .is-selected) {
            color: #2caf5e;
            border-color: #2caf5e;
          }

          &:nth-child(2).is-selected {
            color: #fff;
            background-color: #2caf5e;
            border-color: #2caf5e;
          }


          &:nth-child(3):hover:not(.is-disabled, .is-selected) {
            color: #ff9c01;
            border-color: #ff9c01;
          }

          &:nth-child(3).is-selected {
            color: #fff;
            background-color: #ff9c01;
            border-color: #ff9c01;
          }

          &:hover:not(.is-disabled, .is-selected) {
            color: #ea3636;
            border-color: #ea3636;
          }

          &.is-selected {
            color: #fff;
            background-color: #ea3636;
            border-color: #ea3636;
          }
        }
      }
    }
  }
}
</style>
