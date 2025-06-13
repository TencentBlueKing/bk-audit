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
      :model="formData">
      <div class="flex-center">
        <bk-form-item
          class="is-required mr16"
          :label="t('资源类型id')"
          label-width="100"
          property="resource_type_id"
          required
          style="flex: 1;">
          <bk-input
            v-model.trim="formData.resource_type_id"
            :placeholder="t('请输入资源类型id')"
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
            :placeholder="t('请输入资源类型名称')"
            style="width: 100%;" />
        </bk-form-item>
      </div>
      <bk-form-item
        :label="t('所属父级资源')"
        label-width="160"
        property="ancestors"
        required>
        <bk-select
          ref="selectRef"
          v-model="formData.ancestors"
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
            label="raw_name"
            :search="searchValue"
            :show-node-type-icon="false"
            @node-click="handleNodeClick">
            <template #default="{ data }: { data: SystemResourceTypeTree }">
              <span> {{ data.name }}</span>
            </template>
          </bk-tree>
        </bk-select>
      </bk-form-item>
      <bk-form-item
        class="sensitivity-level-group"
        :label="t('敏感等级')"
        label-width="160"
        property="sensitivity"
        required>
        <bk-button-group>
          <bk-button
            v-for="item in sensitivityList"
            :key="item.value"
            :selected="formData.sensitivity === item.value"
            @click="handleSensitivity(item.value)">
            <span>{{ item.label }}</span>
          </bk-button>
        </bk-button-group>
      </bk-form-item>
    </audit-form>
    <div class="other-action">
      <h3 style="margin-bottom: 16px;">
        {{ t('还可以快捷创建该资源的以下操作：') }}
      </h3>
      <bk-checkbox-group v-model="actionArr">
        <bk-checkbox label="new">
          {{ t('新建脚本') }}
        </bk-checkbox>
        <bk-checkbox label="edit">
          {{ t('编辑脚本') }}
        </bk-checkbox>
        <bk-checkbox label="view">
          {{ t('查看脚本') }}
        </bk-checkbox>
        <bk-checkbox label="delete">
          {{ t('删除脚本') }}
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

  interface Emits {
    (e: 'updateResource'): void;
  }
  interface Props {
    isEdit: boolean;
    editData: SystemResourceTypeModel;
  }

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  const props = defineProps<Props>();
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
  const selectRef = ref();
  const formRef = ref();
  const { messageSuccess } = useMessage();
  const addType = ref('customize');
  const formData  = ref({
    resource_type_id: '',
    name: '',
    ancestors: '',
    sensitivity: 2,
  });
  const searchValue = ref('');
  const actionArr = ref([]);

  if (props.isEdit) {
    nextTick(() => {
      formData.value.resource_type_id = props.editData.resource_type_id;
      formData.value.name = props.editData.name;
      // eslint-disable-next-line prefer-destructuring
      formData.value.ancestors = props.editData.ancestors[0];
      formData.value.sensitivity = props.editData.sensitivity;

      selectRef.value.selected = [{
        value: formData.value.ancestors,
        label: formData.value.name,
      }];
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
    formData.value.ancestors = data.resource_type_id;
  };

  const handleSensitivity = (value: number) => {
    formData.value.sensitivity = value;
  };

  defineExpose({
    submit() {
      return formRef.value.validate().then(() => {
        const params: Record<string, any> = _.cloneDeep(formData.value);
        params.ancestors = [params.ancestors];
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
            background-color: #979ba5;
            border-color: #979ba5;
          }

          &:nth-child(2):hover:not(.is-disabled, .is-selected) {
            color: #ff9c01;
            border-color: #ff9c01;
          }

          &:nth-child(2).is-selected {
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

  .other-action {
    padding: 16px;
    background: #f5f7fa;
  }
}
</style>
