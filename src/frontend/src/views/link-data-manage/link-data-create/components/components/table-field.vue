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
  <div
    v-for="(field, index) in linkFields"
    :key="index"
    class="table-fields">
    <div class="left-fields">
      <bk-form-item
        class="no-label"
        label-width="0"
        style="margin-bottom: 8px;">
        <select-verify
          ref="selectVerifyRef"
          :default-value="field.left_field.field_name"
          theme="background">
          <bk-select
            v-model="field.left_field.field_name"
            filterable
            :placeholder="t('请选择匹配字段')"
            @change="(value: string) => selectField(value, field.left_field, 'left')">
            <template #prefix>
              <span style="padding: 0 14px; color: #63656e; border-right: 1px solid #c4c6cc;">{{ t('字段') }}</span>
            </template>
            <bk-option
              v-for="item in leftFieldsList"
              :key="item.value"
              :label="item.label"
              :value="item.value" />
          </bk-select>
        </select-verify>
      </bk-form-item>
    </div>
    <div style="width: 46px; margin-bottom: 8px; text-align: center;">
      =
    </div>
    <div class="right-fields">
      <bk-form-item
        class="no-label"
        label-width="0"
        style="margin-bottom: 8px;">
        <select-verify
          ref="selectVerifyRef"
          :default-value="field.right_field.field_name"
          theme="background">
          <bk-select
            v-model="field.right_field.field_name"
            filterable
            :placeholder="t('请选择匹配字段')"
            @change="(value: string) => selectField(value, field.right_field, 'right')">
            <template #prefix>
              <span style="padding: 0 14px; color: #63656e; border-right: 1px solid #c4c6cc;">{{ t('字段') }}</span>
            </template>
            <bk-option
              v-for="item in rightFieldsList"
              :key="item.value"
              :label="item.label"
              :value="item.value" />
          </bk-select>
        </select-verify>
      </bk-form-item>
    </div>
    <div class="icon-group">
      <audit-icon
        style="margin-right: 10px;"
        type="add-fill"
        @click="handleAdd" />
      <audit-icon
        v-if="index !== 0"
        type="reduce-fill"
        @click="() => handleDelete(index)" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import SelectVerify from './select-verify.vue';

  interface FieldItem {
    field_type: string;
    label: string;
    value: string;
  }

  interface Exposes {
    getValue: () => Promise<any>;
    clearFields: () => void;
  }

  interface Props {
    leftTableRtId: string | Array<string>
    rightTableRtId: string | Array<string>
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const selectVerifyRef = ref();

  const linkFields = defineModel<Array<{
    left_field: {
      field_name: string,
      display_name: string,
    };
    right_field: {
      field_name: string,
      display_name: string,
    };
  }>>('linkFields', {
    required: true,
  });

  const leftFieldsList = ref<Array<FieldItem>>([]);
  const rightFieldsList = ref<Array<FieldItem>>([]);

  const selectField = (value: string, field: {
    field_name: string,
    display_name: string,
  }, type: 'left' | 'right') => {
    if (type === 'left') {
      const resultItem = leftFieldsList.value.find(item => item.value === value);
      // eslint-disable-next-line no-param-reassign
      field.display_name = resultItem ? resultItem.label : '';
    } else {
      const resultItem = rightFieldsList.value.find(item => item.value === value);
      // eslint-disable-next-line no-param-reassign
      field.display_name = resultItem ? resultItem.label : '';
    }
  };

  const getLeftTableFields = (id: string) => {
    StrategyManageService.fetchTableRtFields({
      table_id: id,
    }).then((data) => {
      leftFieldsList.value = data;
      linkFields.value = linkFields.value.map(item => ({
        right_field: item.right_field,
        left_field: leftFieldsList.value.find(fieldItem => fieldItem.value === item.left_field.field_name)
          ? item.left_field
          : {
            field_name: '',
            display_name: '',
          },
      }));
    });
  };

  const getRightTableFields = (id: string) => {
    StrategyManageService.fetchTableRtFields({
      table_id: id,
    }).then((data) => {
      rightFieldsList.value = data;
      linkFields.value = linkFields.value.map(item => ({
        left_field: item.left_field,
        right_field: rightFieldsList.value.find(fieldItem => fieldItem.value === item.right_field.field_name)
          ? item.right_field
          : {
            field_name: '',
            display_name: '',
          },
      }));
    });
  };

  // 新增
  const handleAdd = () => {
    linkFields.value?.push({
      left_field: {
        field_name: '',
        display_name: '',
      },
      right_field: {
        field_name: '',
        display_name: '',
      },
    });
  };

  // 删除
  const handleDelete = (index: number) => {
    linkFields.value?.splice(index, 1);
  };

  // 获取左边表字段
  watch(() => props.leftTableRtId, (data) => {
    // 获取表字段
    if (data && data.length) {
      const id = Array.isArray(data) ? data[data.length - 1] : data;
      getLeftTableFields(id);
    } else {
      leftFieldsList.value = [];
    }
  }, {
    immediate: true,
  });

  // 获取右边表字段
  watch(() => props.rightTableRtId, (data) => {
    // 获取表字段
    if (data && data.length) {
      const id = Array.isArray(data) ? data[data.length - 1] : data;
      getRightTableFields(id);
    } else {
      rightFieldsList.value = [];
    }
  }, {
    immediate: true,
  });

  defineExpose<Exposes>({
    clearFields() {
      if (!selectVerifyRef.value) return;
      (selectVerifyRef.value as { clearFields: () => void }[]).map(item => item.clearFields());
    },
    getValue() {
      return Promise.all((selectVerifyRef.value as { getValue: () => any }[])?.map(item => item.getValue()));
    },
  });
</script>
<style scoped lang="postcss">
.table-fields {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto;
  gap: 8px;
  align-items: center;

  .icon-group {
    width: 36px;
    margin-bottom: 8px;
    color: #c4c6cc;
    cursor: pointer;
  }
}
</style>
