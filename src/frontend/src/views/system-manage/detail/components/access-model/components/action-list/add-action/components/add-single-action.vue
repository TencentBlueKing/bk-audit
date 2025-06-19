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
      :model="formData">
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
            :search="searchValue"
            :show-node-type-icon="false"
            @node-click="handleNodeClick">
            <template #default="{ data }: { data: SystemResourceTypeTree }">
              <span> {{ data.name }}</span>
            </template>
          </bk-tree>
        </bk-select>
      </bk-form-item>
    </audit-form>
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import SystemActionModel from '@model/meta/system-action';
  import type SystemResourceTypeTree from '@model/meta/system-resource-type-tree';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'updateAction'): void;
  }

  interface Props {
    isEdit: boolean;
    editData: SystemActionModel;
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
  });
  const searchValue = ref('');

  if (props.isEdit) {
    nextTick(() => {
      formData.value.action_id = props.editData.action_id;
      formData.value.name = props.editData.name;
      // eslint-disable-next-line prefer-destructuring
      formData.value.resource_type_ids = props.editData.resource_type_ids[0];
    });
  }

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

  const handleNodeClick = (data: SystemResourceTypeTree) => {
    // 设置select选中
    selectRef.value.selected = [{
      value: data.resource_type_id,
      label: data.name,
    }];
    formData.value.resource_type_ids = data.resource_type_id;
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
  }
}
</style>
