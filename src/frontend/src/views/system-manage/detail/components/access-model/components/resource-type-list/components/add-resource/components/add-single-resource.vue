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
      <bk-radio-button label="other">
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
          :label="t('资源类型id')"
          label-width="100"
          property="id"
          style="flex: 1;">
          <bk-input
            v-model.trim="formData.id"
            :placeholder="t('请输入资源类型id')"
            style="width: 100%;" />
        </bk-form-item>
        <bk-form-item
          class="is-required mr16"
          :label="t('资源类型名称')"
          label-width="100"
          property="id"
          style="flex: 1;">
          <bk-input
            v-model.trim="formData.resource_name"
            :placeholder="t('请输入资源类型名称')"
            style="width: 100%;" />
        </bk-form-item>
      </div>
      <bk-form-item
        :label="t('所属父级资源')"
        label-width="160"
        property="description">
        <bk-select
          v-model="formData.parent_resource"
          allow-create
          class="bk-select"
          filterable
          :input-search="false"
          multiple
          multiple-mode="tag"
          :placeholder="t('请选择')"
          :search-placeholder="t('请输入关键字')">
          <bk-option
            v-for="(item, index) in parentResourceList"
            :key="index"
            :label="item.name"
            :value="item.id" />
        </bk-select>
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
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  const { t } = useI18n();

  const formData  = ref({
    id: '',
    resource_name: '',
    parent_resource: '',
  });
  const rules = ref({});
  const addType = ref('QQ');
  const parentResourceList = ref([{
    name: '1',
    id: 1,
  }]);
  const actionArr = ref([]);
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

  .other-action {
    padding: 16px;
    background: #f5f7fa;
  }
}
</style>
