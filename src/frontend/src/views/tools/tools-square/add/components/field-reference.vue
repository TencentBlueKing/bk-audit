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
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showEditSql"
    class="field-reference-sideslider"
    show-header-slot
    :title="t('配置数据下钻')"
    width="1100">
    <template #header>
      <div class="flex mr24 custom-title">
        <span> {{ t('配置数据下钻') }}</span>
        <div class="line" />
        <span style="font-size: 12px; color: #979ba5;">
          {{ t('引用已配置工具，对当前字段进行解释或下钻；比如：字段为 username，可配置根据 oa 查询用户 hr 详细信息的工具，即可在字段位置直接下探查看。') }}
        </span>
      </div>
    </template>
    <audit-form
      ref="formRef"
      class="field-reference-form"
      form-type="vertical"
      :model="formData">
      <bk-form-item
        error-display-type="tooltips"
        :label="t('选择工具')"
        label-width="160"
        property="tool"
        required>
        <div style="display: flex;">
          <bk-select
            v-model="formData.tool"
            filterable
            :input-search="false"
            :placeholder="t('请选择')"
            :search-placeholder="t('请输入关键字')"
            style="flex: 1;">
            <bk-option
              v-for="(item, index) in [{ id: '1', name: '工具1' }]"
              :key="index"
              :label="item.name"
              :value="item.id" />
          </bk-select>
          <bk-button
            class="ml16"
            text
            theme="primary">
            {{ t('去使用') }}
          </bk-button>
        </div>
      </bk-form-item>
      <bk-form-item
        error-display-type="tooltips"
        :label="t('字段值引用')"
        label-width="160"
        property="tool"
        required>
        <div class="field-list">
          <div
            v-for="(item, index) in formData.toolInputData"
            :key="index"
            class="field-item">
            <div class="field-key">
              <bk-input
                v-model="item.raw_name"
                disabled
                style="flex: 1;" />
            </div>
            <div class="field-reference-type">
              <bk-dropdown trigger="click">
                <bk-button>{{ item.reference_type }}</bk-button>
                <template #content>
                  <bk-dropdown-menu>
                    <bk-dropdown-item
                      v-for="TypeItem in referenceTypeList"
                      :key="TypeItem.id"
                      @click="handleClick(TypeItem.id)">
                      {{ TypeItem.name }}
                    </bk-dropdown-item>
                  </bk-dropdown-menu>
                </template>
              </bk-dropdown>
            </div>
            <div class="field-value">
              <select-map-value
                ref="selectMapValueRef"
                :alternative-field-list="outputData"
                :data="item"
                :value="item.reference_value"
                @change="value => handleSelectMapValueChange(value)" />
            </div>
            <div style="margin-left: 10px; color: #979ba5;">
              {{ t('的值作为输入') }}
            </div>
          </div>
        </div>
      </bk-form-item>
    </audit-form>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import SelectMapValue from '../components/select-map-value.vue';

  const { t } = useI18n();
  const showEditSql = defineModel<boolean>('showFieldReference', {
    required: true,
  });

  const referenceTypeList = ref([{
    id: 'reference',
    name: t('直接引用'),
  }, {
    id: 'default',
    name: t('使用默认值'),
  }]);

  const formData = ref({
    tool: '',
    toolInputData: [{
      raw_name: 'username',
      reference_type: 'reference',
      reference_value: [{
        value: '1',
        name: '1',
      }],
    }, {
      raw_name: 'user_age',
      reference_type: 'reference',
      reference_value: [{
        value: '2',
        name: '2',
      }],
    }],
  });

  const outputData = ref([{
    raw_name: 'username',
    display_name: '用户名',
  }]);

  const handleClick = (item: string) => {
    console.log(item);
  };

  const handleSelectMapValueChange = (value: Record<string, any>) => {
    console.log(value);
  };
</script>
<style scoped lang="postcss">
.field-reference-sideslider {
  .custom-title {
    align-items: center;

    .line {
      width: 1px;
      height: 12px;
      margin: auto 10px;
      background-color: #ccc;
    }
  }

  .field-reference-form {
    padding: 16px 40px;

    .field-list {
      display: flex;
      padding: 16px;
      background: #f5f7fa;
      flex-direction: column;

      .field-item {
        display: flex;
        align-items: center;
        margin: 5px 0;

        .field-reference-type {
          width: 100px;
          margin: 0 10px;
        }

        .field-key,
        .field-value {
          flex: 1 1 220px;
        }

        .field-value {
          border: 1px solid #c4c6cc;
        }
      }
    }
  }
}
</style>
