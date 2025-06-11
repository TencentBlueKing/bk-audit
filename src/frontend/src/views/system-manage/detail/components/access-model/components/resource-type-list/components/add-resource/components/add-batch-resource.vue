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
        <div class="field-value">
          {{ t('资源ID') }}
        </div>
        <div class="field-value">
          {{ t('资源名称') }}
        </div>
        <div class="field-value">
          {{ t('所属父级资源') }}
          <bk-popover
            ref="commAggRef"
            allow-html
            boundary="parent"
            content="#hidden_parent_resource_pop_content"
            ext-cls="comm-agg-pop"
            placement="bottom"
            theme="light"
            trigger="click">
            <audit-icon
              style="margin-left: 4px;color: #3a84ff;"
              type="edit-fill" />
          </bk-popover>
          <div style="display: none">
            <div id="hidden_parent_resource_pop_content">
              <h3>{{ t('批量编辑所属父级资源') }}</h3>
              <audit-form
                ref="formRef"
                class="customize-form"
                form-type="vertical"
                :model="formData"
                :rules="rules">
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
            </div>
          </div>
        </div>
        <div class="field-value">
          {{ t('敏感等级') }}
          <bk-popover
            ref="commAggRef"
            allow-html
            boundary="parent"
            content="#hidden_pop_content"
            ext-cls="comm-agg-pop"
            placement="bottom"
            theme="light"
            trigger="click">
            <audit-icon
              style="margin-left: 4px;color: #3a84ff;"
              type="edit-fill" />
          </bk-popover>
          <div style="display: none">
            <div id="hidden_pop_content">
              <h3>{{ t('批量编辑敏感等级') }}</h3>
              <audit-form
                ref="formRef"
                class="customize-form"
                form-type="vertical"
                :model="formData"
                :rules="rules">
                <bk-form-item
                  :label="t('敏感等级')"
                  label-width="160"
                  property="description">
                  <bk-select
                    v-model="formData.risk_level"
                    allow-create
                    class="bk-select"
                    filterable
                    :input-search="false"
                    multiple
                    multiple-mode="tag"
                    :placeholder="t('请选择')"
                    :search-placeholder="t('请输入关键字')">
                    <bk-option
                      v-for="(item, index) in riskLevelList"
                      :key="index"
                      :label="item.name"
                      :value="item.id" />
                  </bk-select>
                </bk-form-item>
              </audit-form>
            </div>
          </div>
        </div>
        <div class="field-operation" />
      </div>
      <template
        v-for="(fieldItem, fieldIndex) in renderData"
        :key="fieldIndex">
        <div class="field-row">
          <div class="field-select">
            <bk-checkbox
              v-model="fieldItem.isSelected" />
          </div>
          <div class="field-value">
            <field-input
              ref="fieldItemRef"
              v-model="fieldItem.id"
              required
              theme="background" />
          </div>
          <div class="field-value">
            <field-input
              ref="fieldItemRef"
              v-model="fieldItem.resource_name"
              required
              theme="background" />
          </div>
          <div class="field-value">
            <field-select
              ref="fieldItemRef"
              :default-value="fieldItem.parent_resource || ''"
              :field-name="fieldItem.parent_resource"
              :options="[]"
              required
              theme="background" />
          </div>
          <div class="field-value">
            <field-select
              ref="fieldItemRef"
              :default-value="fieldItem.risk_level || ''"
              :field-name="fieldItem.risk_level"
              :options="[]"
              required
              theme="background" />
          </div>
          <div class="field-operation">
            <div class="icon-group">
              <audit-icon
                style="margin-right: 10px; cursor: pointer;"
                type="add-fill" />
              <audit-icon
                style="cursor: pointer;"
                type="reduce-fill" />
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import FieldInput from '../../../../field-input.vue';
  import fieldSelect from '../../../../field-select.vue';

  interface ResourceFieldType {
    id: string,
    resource_name: string,
    parent_resource: string,
    risk_level: string,
    isSelected: false,
  }

  const { t } = useI18n();
  const isSelectedAll = ref(false);
  const parentResourceList = ref([{
    name: '1',
    id: 1,
  }]);
  const riskLevelList = ref([{
    name: '1',
    id: 1,
  }]);
  const formData  = ref({
    parent_resource: '',
    risk_level: '',
  });
  const rules = ref({});
  const renderData = ref<ResourceFieldType[]>([{
    id: '',
    resource_name: '',
    parent_resource: '',
    risk_level: '',
    isSelected: false,
  }]);
</script>
<style lang="postcss" scoped>
.add-batch-resource {
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

  .field-value {
    display: flex;
    width: 160px;
    overflow: hidden;
    border-left: 1px solid #dcdee5;
    align-items: center;
  }

  .field-header-row {
    display: flex;
    height: 42px;
    font-size: 12px;
    line-height: 40px;
    color: #313238;
    background: #f0f1f5;

    .field-value {
      padding-left: 16px;
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
