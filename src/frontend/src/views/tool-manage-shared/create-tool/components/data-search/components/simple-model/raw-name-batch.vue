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
  <div>
    <div class="dialog-content bk-theme-form--inline">
      <div class="dialog-content-left">
        <bk-input>
          <template #prefix>
            <audit-icon
              class="search1"
              type="search1" />
          </template>
        </bk-input>
        <div class="list">
          <div class="list-head">
            <div class="list-head-select" />
            <div class="list-head-left">
              {{ t('显示名') }}
            </div>
            <div class="list-head-right">
              {{ t('字段名') }}
            </div>
          </div>
          <div class="list-body">
            <bk-checkbox-group
              v-model="checkboxGroupValue"
              class="list-item-select">
              <bk-checkbox
                v-for="(item, index) in dataList"
                :key="index"
                class="list-item-radio"
                :label="item.name" />
            </bk-checkbox-group>
            <div class="list-item-right">
              <div
                v-for="(item, index) in dataList"
                :key="index"
                class="list-item-text">
                {{ item.value }}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="dialog-content-right">
        <div class="right-title">
          {{ t('字段设置') }}
        </div>
        <bk-checkbox
          v-model="isValue"
          class="right-checkbox">
          {{ t('同时作为查询结果的字段') }}
        </bk-checkbox>
        <div class="table">
          <div class="render-field">
            <div class="field-header-row">
              <div
                class="field-value"
                style="flex: 0 0 160px">
                {{ t("显示名") }}
              </div>
              <div
                class="field-value"
                style="flex: 0 0 160px">
                {{ t("字段说明") }}
              </div>
              <div
                class="field-value"
                style="flex: 0 0 160px">
                {{ t("聚合算法") }}
                <bk-popover
                  boundary="parent"
                  placement="top"
                  theme="light"
                  trigger="click">
                  <audit-icon
                    style="
                margin-left: 4px;
                font-size: 16px;
                color: #3a84ff;
                cursor: pointer;
              "
                    type="piliangbianji" />
                  <template #content>
                    <div class="algorithm">
                      <div
                        v-for="(val, index) in algorithm"
                        :key="index"
                        class="algorithm-item">
                        {{ val?.label }}
                      </div>
                    </div>
                  </template>
                </bk-popover>
              </div>
            </div>
            <audit-form
              ref="tableInputFormRef"
              form-type="vertical"
              :model="formData">
              <template
                v-for="(item, index) in formData"
                :key="index">
                <div class="field-row">
                  <!-- 显示名 -->
                  <div
                    class="field-value"
                    style="flex: 0 0 160px">
                    <bk-form-item
                      error-display-type="tooltips"
                      label=""
                      label-width="0">
                      <bk-input
                        v-model="item.display_name"
                        disabled />
                    </bk-form-item>
                  </div>
                  <!-- 字段说明 -->
                  <div
                    class="field-value"
                    style="flex: 0 0 160px">
                    <bk-form-item
                      error-display-type="tooltips"
                      label=""
                      label-width="0">
                      <bk-input v-model="item.description" />
                    </bk-form-item>
                  </div>

                  <!-- 聚合算法 -->
                  <div
                    class="field-value"
                    style="flex: 0 0 158px">
                    <bk-form-item
                      error-display-type="tooltips"
                      label=""
                      label-width="0">
                      <bk-select
                        v-model="item.selectedValue"
                        auto-focus
                        class="bk-select"
                        filterable
                        :popover-options="{ boundary: 'parent' }">
                        <bk-option
                          v-for="alVal in algorithm"
                          :id="alVal?.value"
                          :key="alVal?.id"
                          :disabled="alVal?.disabled"
                          :name="alVal?.label" />
                      </bk-select>
                    </bk-form-item>
                  </div>
                </div>
              </template>
            </audit-form>
          </div>
        </div>
      </div>
    </div>
    <div class="dialog-footer">
      <bk-button
       
        theme="primary"
        type="primary"
        @click="submit" style="margin-right: var(--bk-theme-space-8)">
        {{ t('确定') }}
      </bk-button>
      <bk-button
        type="default"
        @click="cancel">
        {{ t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  const isValue = ref(false);
  const checkboxGroupValue = ref();
  const { t } = useI18n();
  const algorithm = ref([
    {
      id: '1',
      label: 'sum',
      value: 'sum',
      disabled: false,
    },
  ]);
  const dataList = ref([
    {
      label: false,
      name: '用户名',
      value: 'username',
    }, {
      label: false,
      name: 'HAHA',
      value: 'AAA',
    },
    {
      label: false,
      name: '用户名111',
      value: 'username1111',
    },
  ]);
  const formData = ref([{
    raw_name: '',
    display_name: '',
    description: '',
    selectedValue: '',
  }]);

  const submit = () => {
    console.log('submit');
  };
  const cancel = () => {
    console.log('cancel');
  };
</script>

<style lang="postcss" scoped>
.dialog-content {
  display: flex;
  width: 800px;
  height: 400px;
  margin-top: 0;
  justify-content: space-between;

  .dialog-content-left {
    width: 270px;

    .list-head {
      display: flex;
      height: 40px;
      margin-top: var(--bk-theme-space-12);
      font-size: 12px;
      color: var(--bk-theme-text-weak);
      background-color: var(--bk-theme-table-header-bg);
      justify-content: space-between;
      align-items: center;

      .list-head-select {
        width: 50px;
        text-align: center;
      }

      .list-head-left {
        width: 150px;
        text-align: left;
      }

      .list-head-right {
        width: 70px;
        margin-right: var(--bk-theme-space-12);
        text-align: right;
      }
    }

    .list-body {
      display: flex;
      height: 300px;
      overflow: auto;

      .list-item-select {
        display: flex;
        width: 250px;
        height: 100%;
        flex-direction: column;

        :deep(.bk-radio.bk-radio) {
          margin-left: var(--bk-theme-space-16);
          font-size: 12px;
          color: var(--bk-theme-text-default);

        }

        :deep(.bk-radio-label) {
          font-size: 12px;
          color: var(--bk-theme-text-default);
        }

        .list-item-radio {
          margin-top: var(--bk-theme-space-12);
          margin-left: var(--bk-theme-space-32);
          font-size: 12px;
          color: var(--bk-theme-text-default);
        }
      }

      .list-item-right {
        display: flex;
        width: 150px;
        height: 100%;
        text-align: left;
        flex-direction: column;

        .list-item-text {
          height: 20px;
          margin-top: var(--bk-theme-space-12);
          margin-right: var(--bk-theme-space-4);
          font-size: 12px;
          color: var(--bk-theme-text-weak);
          text-align: right;

        }
      }
    }

  }

  .dialog-content-right {
    width: 530px;
    height: 100%;
    overflow: auto;
    background-color: var(--bk-theme-surface-subtle);

    .right-title {
      margin-top: var(--bk-theme-space-16);
      margin-left: var(--bk-theme-space-16);
      font-size: 12px;
      font-weight: 700;
      line-height: 20px;
      letter-spacing: 0;
      color: var(--bk-theme-text-strong);
    }

    .right-checkbox {
      margin-top: var(--bk-theme-space-12);
      margin-left: var(--bk-theme-space-16);
      font-size: 12px;
      line-height: 20px;
      letter-spacing: 0;
      color: var(--bk-theme-text-default);
    }

    .table {
      width: 480px;
      height: 300px;
      margin-top: var(--bk-theme-space-12);
      margin-left: var(--bk-theme-space-16);

    }
  }

}

.dialog-footer {
  display: flex;
  width: 100%;
  height: 42px;
  padding: 0 var(--bk-theme-space-16);
  margin-top: var(--bk-theme-space-12);
  margin-bottom: var(--bk-theme-space-12);
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0;
  color: var(--bk-theme-text-default);
  background: var(--bk-theme-table-header-bg);
  box-shadow: inset 0 1px 0 0 #0000001f;
  align-items: center;
  justify-content: flex-end;

}

.search1 {
  margin-top: var(--bk-theme-space-4);
  font-size: 20px;
  color: var(--bk-theme-text-weak);
}

.render-field {
  display: flex;
  min-width: 300px;
  overflow: hidden;
  border: 1px solid var(--bk-theme-border-default);
  border-radius: var(--bk-theme-tag-radius);
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-select {
    width: 40px;
    text-align: center;
    background: var(--bk-theme-table-header-bg);
  }

  .field-operation {
    width: 170px;
    padding-left: var(--bk-theme-space-16);
    background: var(--bk-theme-table-header-bg);
    border-left: 1px solid var(--bk-theme-border-default);
  }

  :deep(.field-value) {
    display: flex;
    flex: 1;

    /* width: 180px; */
    overflow: hidden;
    border-left: 1px solid var(--bk-theme-border-default);
    align-items: center;

    .field-value-div {
      display: flex;
      padding: 0 var(--bk-theme-space-8);
      cursor: pointer;
      align-items: center;

      &:hover {
        .remove-btn {
          display: block;
        }
      }

      .remove-btn {
        position: absolute;
        right: 28px;
        z-index: 1;
        display: none;
        font-size: 12px;
        color: var(--bk-theme-border-strong);
        transition: all .15s;

        &:hover {
          color: var(--bk-theme-text-weak);
        }
      }

      .renew-tips {
        position: absolute;
        right: 8px;
        font-size: 14px;
        color: var(--bk-theme-color-brand-2);
      }
    }

    .bk-form-item.is-error {
      .bk-input--text {background-color: var(--bk-theme-fill-danger);
      }
    }

    .bk-form-item {
      width: 100%;

      .bk-input,
      .bk-date-picker-editor,
      .bk-select-trigger,
      .bk-select-tag,
      .date-picker {
        height: 42px !important;
        border: none;
      }

      .icon-wrapper {
        top: 6px;
      }

      .bk-input.is-focused:not(.is-readonly) {
        border: 1px solid var(--bk-theme-color-brand-2);
        outline: 0;
       
      }

      .bk-form-error-tips {
        top: 12px;
      }
    }

    .add-enum {
      position: absolute;
      top: 14px;
      right: 28px;
      cursor: pointer;
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

    .field-select,
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

.algorithm {
  display: flex;
  flex-direction: column;
  width: 100px;

  .algorithm-item {
    width: 100px;
    color: var(--bk-theme-text-default);
    text-align: center;
    cursor: pointer;

    &:hover {
      color: var(--bk-theme-color-brand-2);
      background-color: var(--bk-theme-fill-selected)
    }
  }
}
</style>
