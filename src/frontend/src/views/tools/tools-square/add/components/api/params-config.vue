<!-- eslint-disable vue/no-template-shadow -->
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
  <bk-form-item
    label-width="160">
    <div class="render-field ">
      <div class="field-header-row">
        <div class="field-value is-required">
          {{ t('参数名') }}
        </div>
        <div class="field-value">
          {{ t('显示名') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 150px;">
          {{ t('传参方式') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 350px;">
          {{ t('参数说明') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 200px;">
          {{ t('是否必填') }}
          <bk-popover
            ref="requiredListRef"
            allow-html
            content="#hidden_pop_content"
            ext-cls="field-required-pop"
            placement="top"
            theme="light"
            trigger="click"
            width="100">
            <audit-icon
              style="margin-left: 4px; font-size: 16px;color: #3a84ff; cursor: pointer;"
              type="piliangbianji" />
          </bk-popover>
          <div style="display: none">
            <div id="hidden_pop_content">
              <div
                v-for="(item, index) in requiredList"
                :key="index"
                class="field-required-item"
                @click="handleRequiredClick(item)">
                {{ item.label }}
              </div>
            </div>
          </div>
        </div>
        <div
          class="field-value is-required"
          style="flex: 0 0 120px;">
          {{ t('前端类型') }}
        </div>
        <div class="field-value">
          {{ t('默认值') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 120px;">
          {{ t('是否可见') }}
          <bk-popover
            ref="requiredListRef"
            allow-html
            content="#hidden_pop_content2"
            ext-cls="field-required-pop"
            placement="top"
            theme="light"
            trigger="click"
            width="100">
            <audit-icon
              style="margin-left: 4px; font-size: 16px;color: #3a84ff; cursor: pointer;"
              type="piliangbianji" />
          </bk-popover>
          <div style="display: none">
            <div id="hidden_pop_content2">
              <div
                v-for="(item, index) in isViewsList"
                :key="index"
                class="field-required-item"
                @click="handleViewsClick(item)">
                {{ item.label }}
              </div>
            </div>
          </div>
        </div>
        <div
          class="field-value"
          style="flex: 0 0 80px;" />
      </div>
    </div>
    <audit-form
      ref="tableInputFormRef"
      form-type="vertical"
      :model="formData">
      <template
        v-for="(item, index) in paramList"
        :key="item.id">
        <div class="field-row">
          <div class="field-value">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <bk-input
                v-if="item.frontendType !== 'date-picker'"
                v-model="item.name" />
              <div v-else>
                <div style="display: flex; border-bottom: 1px solid  #dcdee5;">
                  <bk-input
                    v-model="item.startTime" /> <span><bk-tag theme="info"> {{ t('开始时间') }} </bk-tag></span>
                </div>
                <div style="display: flex;">
                  <bk-input
                    v-model="item.endTime" /> <span> <bk-tag theme="warning"> {{ t('结束时间') }} </bk-tag></span>
                </div>
              </div>
            </bk-form-item>
          </div>
          <!-- 显示名 -->
          <div class="field-value">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <bk-input
                v-model="item.dispalyName" />
            </bk-form-item>
          </div>
          <!-- 传参方式 -->
          <div
            class="field-value"
            style="flex: 0 0 150px;">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <bk-select
                v-model="item.type"
                class="bk-select"
                size="small">
                <bk-option
                  v-for="(paramsTypeItem, paramsTypeIndex) in paramsTypeList"
                  :id="paramsTypeItem.value"
                  :key="paramsTypeIndex"
                  :name="paramsTypeItem.label" />
              </bk-select>
            </bk-form-item>
          </div>
          <!-- 参数说明 -->
          <div
            class="field-value"
            style="flex: 0 0 350px;">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <bk-input
                v-model="item.description" />
            </bk-form-item>
          </div>
          <!-- 是否必填 -->
          <div
            class="field-value"
            style="flex: 0 0 200px;">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <bk-select
                v-model="item.required"
                class="bk-select"
                size="small">
                <bk-option
                  v-for="(requiredItem, requiredIndex) in requiredList"
                  :id="requiredItem.id"
                  :key="requiredIndex"
                  :name="requiredItem.label" />
              </bk-select>
            </bk-form-item>
          </div>
          <!-- 前端类型 -->
          <div
            class="field-value"
            style="flex: 0 0 120px;">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <bk-select
                v-model="item.frontendType"
                class="bk-select"
                :clearable="false"
                size="small">
                <bk-option
                  v-for="(frontendTypeItem, frontendTypeItemIndex) in frontendTypeList"
                  :id="frontendTypeItem.value"
                  :key="frontendTypeItemIndex"
                  :name="frontendTypeItem.label" />
              </bk-select>
            </bk-form-item>
          </div>
          <!-- 默认值 -->
          <div
            class="field-value">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <bk-input
                v-model="item.defaultValue" />
            </bk-form-item>
          </div>
          <!-- 是否可见 -->
          <div
            class="field-value"
            style="flex: 0 0 120px;">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <bk-select
                v-model="item.isViews"
                class="bk-select"
                size="small">
                <bk-option
                  v-for="(isViewItem, isViewItemIndex) in isViewsList"
                  :id="isViewItem.value"
                  :key="isViewItemIndex"
                  :name="isViewItem.label" />
              </bk-select>
            </bk-form-item>
          </div>
          <!-- 按钮 -->
          <div
            class="field-value"
            style="flex: 0 0 80px;">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0">
              <audit-icon
                class="add-fill field-icon"
                type="add-fill"
                @click="handelAddItem" />
              <audit-icon
                v-if="paramList.length > 1"
                class="reduce-fill field-icon"
                type="reduce-fill"
                @click="handelDelectItem(index)" />
            </bk-form-item>
          </div>
        </div>
      </template>
    </audit-form>
  </bk-form-item>
</template>
<script setup lang='tsx'>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  const { t } = useI18n();
  const formData = ref();
  const paramList = ref([
    {
      id: '1',
      name: 'name',
      dispalyName: '显示名',
      type: 'Params',
      description: '显示名',
      required: '1',
      frontendType: 'input',
      defaultValue: '222',
      isViews: '1',
      startTime: '',
      endTime: '',
    },
  ]);
  const requiredList = ref([{
    id: '1',
    label: t('是'),
  }, {
    id: '0',
    label: t('否'),
  }]);
  const paramsTypeList = ref([{
    value: 'Params',
    label: 'Params',
  }, {
    value: 'Body',
    label: 'Body',
  }]);
  const tableInputFormRef = ref();
  const frontendTypeList = ref([{
    value: 'input',
    label: '输入框',
  }, {
    value: 'number-input',
    label: '数字输入框',
  }, {
    value: 'select',
    label: '人员选择器',
  }, {
    value: 'date-picker',
    label: '时间范围选择器',
  }, {
    value: 'time-picker',
    label: '时间选择器',
  },
  ]);

  const isViewsList = ref([{
    value: '1',
    label: t('可见'),
  }, {
    value: '0',
    label: t('不可见'),
  }]);
  // 添加一项
  const handelAddItem = () => {
    paramList.value.push({
      id: Math.random().toString(36)
        .substr(2, 9),
      name: '',
      dispalyName: '',
      type: 'Params',
      description: '',
      required: '1',
      frontendType: 'input',
      defaultValue: '',
      isViews: '1',
      startTime: '',
      endTime: '',
    });
  };
  // 删除一项
  const handelDelectItem = (index: number) => {
    paramList.value.splice(index, 1);
  };

  const handleRequiredClick = (item: Record<string, any>) => {
    paramList.value = paramList.value.map((listItem: Record<string, any>) => {
      // eslint-disable-next-line no-param-reassign
      listItem.required = item.id;
      return listItem;
    });
  };
  const handleViewsClick = (item: Record<string, any>) => {
    paramList.value = paramList.value.map((listItem: Record<string, any>) => {
      // eslint-disable-next-line no-param-reassign
      listItem.isViews = item.value;
      return listItem;
    });
  };
</script>

<style lang="postcss" scoped>
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


}

:deep(.field-value) {
  display: flex;
  flex: 1;

  /* width: 180px; */
  overflow: hidden;
  border-left: 1px solid #dcdee5;
  align-items: center;

  .field-value-div {
    display: flex;
    padding: 0 8px;
    cursor: pointer;
    align-items: center;

    &:hover {
      .remove-btn {
        display: block;
      }
    }

    .remove-btn {
      position: absolute;
      top: 36%;
      right: 28px;
      z-index: 1;
      display: none;
      font-size: 12px;
      color: #c4c6cc;
      transition: all .15s;

      &:hover {
        color: #979ba5;
      }

      &.is-popconfirm-visible {
        display: block;
      }
    }

    .remove-mappings-btn {
      top: 40%;
      right: 8px;
    }

    .renew-tips {
      position: absolute;
      right: 8px;
      font-size: 14px;
      color: #3a84ff;
    }
  }

  .bk-form-item.is-error {
    .bk-input--text {
      background-color: #ffebeb;
    }
  }

  .bk-form-item {
    width: 100%;
    margin-bottom: 0;

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
      border: 1px solid #3a84ff;
      outline: 0;
      box-shadow: 0 0 3px #a3c5fd;
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
  color: #313238;
  background: #f0f1f5;

  .field-value {
    padding-left: 8px;
  }

  .field-value.is-required {
    &::after {
      margin-left: 4px;
      color: red;
      content: '*';
    }
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
  border-right: 1px solid #dcdee5;
  border-bottom: 1px solid #dcdee5;
}

.field-icon {
  margin-left: 20px;
  color: #c4c6cc;
}
</style>
