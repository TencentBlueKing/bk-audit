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
  <bk-dialog
    class="ip-selector-dialog bk-theme-form--inline"
    :is-show="isShow"
    :title="t('配置选项')"
    width="640"
    @closed="handleCancle"
    @confirm="handleConfirm">
    <div class="render-field">
      <div class="field-header-row">
        <div class="field-value is-required">
          {{ t('显示文本') }}
        </div>
        <div class="field-value is-required">
          {{ t('实际值') }}
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
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0"
                :property="`renderData[${index}].name`"
                required
                :rules="[
                  { message: '不能为空', trigger: 'change', validator: (value: string) => !!value},
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
                label-width="0"
                :property="`renderData[${index}].key`"
                required
                :rules="[
                  { message: '不能为空', trigger: 'change', validator: (value: string) => !!value},
                  { message: 'ID重复，请修改', trigger: 'change', validator: (value: string) => {
                    // 检查当前表单中是否有重复
                    const duplicatesInForm = formData.renderData.filter(
                      (item, idx) => item.key === value && idx !== index
                    );
                    if (duplicatesInForm.length > 0) {
                      return false;
                    }
                    return true;
                  }}
                ]">
                <bk-input
                  ref="fieldItemRef"
                  v-model="item.key" />
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
              </div>
            </div>
          </div>
        </template>
      </audit-form>
    </div>
  </bk-dialog>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface EnumItem  {
    key: string,
    name: string
  }

  interface Exposes {
    show(currentChoices: Array<EnumItem>): void,
  }
  interface Emits {
    (e: 'updateChoices', value: Array<EnumItem>): void;
  }

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const tableFormRef = ref();
  const isShow = ref(false);

  const formData  = ref<{
    renderData: Array<EnumItem>,
  }>({
    renderData: [{
      key: '',
      name: '',
    }],
  });

  const handleAdd = (index: number) => {
    // 在对应index后添加新字段
    formData.value.renderData.splice(index + 1, 0, {
      key: '',
      name: '',
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

  // 取消
  const handleCancle = () => {
    isShow.value = false;
    formData.value.renderData = [{
      key: '',
      name: '',
    }];
  };

  const handleConfirm = () => {
    tableFormRef.value.validate().then(() => {
      emits('updateChoices', formData.value.renderData);
      isShow.value = false;
    });
  };

  defineExpose<Exposes>({
    show(currentChoices: Array<EnumItem>) {
      isShow.value = true;
      if (currentChoices.length) {
        formData.value.renderData = _.cloneDeep(currentChoices);
      }
    },
  });
</script>
<style scoped lang="postcss">
.render-field {
  display: flex;
  overflow: hidden;
  border: 1px solid var(--bk-theme-border-default);
  border-radius: var(--bk-theme-tag-radius);
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-operation {
    width: 100px;
    padding-left: var(--bk-theme-space-16);
    background: var(--bk-theme-table-header-bg);
    border-left: 1px solid var(--bk-theme-border-default);

    .icon-group {
      font-size: 16px;
      color: var(--bk-theme-text-weak);

      .icon-item {
        margin-right: var(--bk-theme-space-12);
        cursor: pointer;

        &:hover:not(.delete-icon-disabled) {
          color: var(--bk-theme-text-default);
        }
      }

      .delete-icon-disabled {
        color: var(--bk-theme-border-default);
        cursor: not-allowed;
      }
    }
  }

  :deep(.field-value) {
    display: flex;
    flex: 1;
    overflow: hidden;
    border-left: 1px solid var(--bk-theme-border-default);
    align-items: center;

    .bk-form-item.is-error {
      .bk-input--text {background-color: var(--bk-theme-fill-danger);
      }
    }

    .bk-form-item {
      width: 100%;

      .bk-input {
        height: 42px;
        border: none;
      }

      .bk-input.is-focused:not(.is-readonly) {
        border: 1px solid var(--bk-theme-color-brand-2);
        outline: 0;
       
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
    color: var(--bk-theme-text-strong);
    background: var(--bk-theme-surface-muted);

    .field-value {
      padding-left: var(--bk-theme-space-8);
    }

    .field-value.is-required {
      &::after {
        margin-left: var(--bk-theme-space-4);
        color: red;
        content: '*';
      }
    }

    .field-operation {
      background: var(--bk-theme-surface-muted);
    }
  }

  .field-row {
    display: flex;
    overflow: hidden;
    font-size: 12px;
    line-height: 42px;
    color: var(--bk-theme-text-default);
    border-top: 1px solid var(--bk-theme-border-default);
  }
}
</style>
