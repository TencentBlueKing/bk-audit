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
  <div :class="haveSameName ? `have-same-name params-box`: 'params-box'">
    <bk-form-item
      label-width="160">
      <div class="render-field">
        <div class="field-header-row">
          <div
            class="field-value is-required"
            style="flex: 0 0 150px;">
            {{ t('参数名') }}
          </div>
          <div
            class="field-value"
            style="flex: 0 0 100px;">
            {{ t('显示名') }}
          </div>
          <div
            class="field-value"
            style="flex: 0 0 150px;">
            {{ t('传参方式') }}
          </div>
          <div
            class="field-value">
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
          <div
            class="field-value"
            style="flex: 0 0 250px;">
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
        :model="formData"
        :rules="rules">
        <template
          v-for="(item, index) in paramList"
          :key="index">
          <div class="field-row">
            <div
              class="field-value"
              style="flex: 0 0 150px;">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input
                  v-if="item.field_category !== 'time_range_select'"
                  v-model="item.var_name"
                  :class="(handelVarNameRules(item, index)
                    && isVarNameNOPass
                    && isVarNameNoPassIndex.includes(index)) ? `var-name-rules` : ''" />
                <div
                  v-else
                  :class="(handelVarNameRules(item, index)
                    && isVarNameNOPass &&
                    isVarNameNoPassIndex.includes(index))? `var-split-rules` : ''">
                  <div
                    class="var-split">
                    <bk-input
                      v-model="item.split_config.start_field" />
                    <span>
                      <bk-tag theme="info">
                        {{ t('开始时间') }}
                      </bk-tag>
                    </span>
                  </div>
                  <div style="display: flex;">
                    <bk-input
                      v-model="item.split_config.end_field" />
                    <span>
                      <bk-tag theme="warning">
                        {{ t('结束时间') }}
                      </bk-tag>
                    </span>
                  </div>
                </div>
              </bk-form-item>
            </div>
            <!-- 显示名 -->
            <div
              class="field-value"
              style="flex: 0 0 100px;">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input
                  v-model="item.display_name" />
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
                  v-model="item.position"
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
              class="field-value">
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
                  :allow-empty-values="[false]"
                  class="bk-select"
                  size="small">
                  <bk-option
                    v-for="(requiredItem, requiredIndex) in requiredList"
                    :id="requiredItem.value"
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
                  v-model="item.field_category"
                  :allow-empty-values="[false]"
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
              class="field-value"
              style="flex: 0 0 250px;">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input
                  v-if="item.field_category == 'number_input'"
                  v-model="item.default_value"
                  clearable
                  type="number" />
                <audit-user-selector
                  v-else-if="item.field_category === 'person_select'"
                  v-model="item.default_value" />
                <date-picker
                  v-else-if="item.field_category === 'time_range_select' || item.field_category === 'time-ranger'"
                  v-model="item.time_range"
                  style="width: 100%" />

                <bk-date-picker
                  v-else-if="item.field_category === 'time_select' || item.field_category === 'time-picker'"
                  v-model="item.default_value"
                  append-to-body
                  clearable
                  style="width: 100%"
                  type="datetime" />
                <bk-input
                  v-else
                  v-model="item.default_value"
                  clearable />
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
                  v-model="item.is_show"
                  :allow-empty-values="[false]"
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
                  @click="handelDeleteItem(index)" />
              </bk-form-item>
            </div>
          </div>
        </template>
      </audit-form>
    </bk-form-item>
  </div>
  <div
    v-if="haveSameName"
    class="have-same-name-text">
    {{ t('存在重复的参数名') }}
  </div>
  <div
    v-if="isVarNameNOPass && !haveSameName"
    class="have-same-name-text">
    {{ t('参数名存在空值') }}
  </div>
</template>
<script setup lang='tsx'>
  import { onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    inputVariable: any;
  }

  interface Exposes {
    getData: () => void;
    validatePass: () => boolean;
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const formData = ref();
  const rules = ref();
  const paramList = ref([
    {
      is_show: 'true',
      position: 'query',
      raw_name: '',
      var_name: '',
      required: 'true',
      description: '',
      display_name: '',
      split_config: {
        end_field: '',
        start_field: '',
      },
      default_value: '',
      time_range: [],
      field_category: 'input',
    },
  ]);
  const requiredList = ref([{
    id: '1',
    value: 'true',
    label: t('是'),
  }, {
    id: '2',
    value: 'false',
    label: t('否'),
  }]);
  const paramsTypeList = ref([{
                                value: 'query',
                                label: 'query',
                              }, {
                                value: 'body',
                                label: 'body',
                              },
                              {
                                value: 'path',
                                label: 'path',
                              }]);
  const frontendTypeList = ref([{
    value: 'input',
    label: '输入框',
  }, {
    value: 'number_input',
    label: '数字输入框',
  }, {
    value: 'person_select',
    label: '人员选择器',
  }, {
    value: 'time_range_select',
    label: '时间范围选择器',
  }, {
    value: 'time_select',
    label: '时间选择器',
  },
  ]);
  const isVarNameNOPass = ref(false);
  const isVarNameNoPassIndex = ref<number[]>([]);
  const haveSameName = ref(false);
  const isViewsList = ref([{
    id: '1',
    value: 'true',
    label: t('可见'),
  }, {
    id: '2',
    value: 'false',
    label: t('不可见'),
  }]);
  // 添加一项
  const handelAddItem = () => {
    isVarNameNoPassIndex.value = [];
    isVarNameNOPass.value = false;
    paramList.value.push({
      is_show: 'true',
      position: 'query',
      raw_name: '',
      var_name: '',
      required: 'true',
      description: '',
      display_name: '',
      split_config: {
        end_field: '',
        start_field: '',
      },
      time_range: [],
      default_value: '',
      field_category: 'input',
    });
  };
  // 删除一项
  const handelDeleteItem = (index: number) => {
    isVarNameNoPassIndex.value = [];
    isVarNameNOPass.value = false;
    paramList.value.splice(index, 1);
  };

  const handleRequiredClick = (item: Record<string, any>) => {
    paramList.value = paramList.value.map((listItem: any) => {
      // eslint-disable-next-line no-param-reassign
      listItem.required = item.value;
      return listItem;
    });
  };
  const handleViewsClick = (item: Record<string, any>) => {
    paramList.value = paramList.value.map((listItem: any) => {
      // eslint-disable-next-line no-param-reassign
      listItem.is_show = item.value;
      return listItem;
    });
  };

  // 规则样式
  const handelVarNameRules = (item: Record<string, any>, index: number) => {
    isVarNameNoPassIndex.value = [];
    if (item.field_category !== 'time_range_select') {
      if (item.var_name === '') {
        isVarNameNoPassIndex.value.push(index);
      }
      return item.var_name === '';
    }
    if (item.split_config.end_field === '' || item.split_config.start_field === '') {
      isVarNameNoPassIndex.value.push(index);
    }
    return item.split_config.end_field === '' || item.split_config.start_field === '';
  };

  watch(() => paramList.value, () => {
    isVarNameNOPass.value = false;
    isVarNameNoPassIndex.value = [];
    haveSameName.value = false;
  }, { deep: true, immediate: true });

  onMounted(() => {
    // 编辑复现
    if (props.inputVariable && props.inputVariable.length > 0) {
      paramList.value = props.inputVariable.map((item: any) => {
        const defaultValue = item.default_value;
        const timeRange = item.time_range;
        if (item.field_category === 'time_range_select' || item.field_category === 'time-ranger') {
          return {
            ...item,
            time_range: defaultValue || [],
            default_value: [],
          };
        }
        return {
          ...item,
          time_range: timeRange,
          default_value: defaultValue,
        };
      });
    }
  });
  defineExpose<Exposes>({
    getData() {
      const data = paramList.value.map((item: any) => ({
        ...item,
        raw_name: (item.field_category === 'time_range_select' || item.field_category === 'time-ranger')
          ? (item.split_config.end_field + item.split_config.start_field  + item.position)
          : (item.var_name + item.position),
        default_value: (item.field_category === 'time_range_select' || item.field_category === 'time-ranger') ?  item.time_range : item.default_value,
      }));
      return data;
    },
    validatePass() {
      // 判断参数名是否有空值
      const isEmptyArr = paramList.value.map((item: any) => {
        if (item.field_category === 'time_range_select' || item.field_category === 'time-ranger') {
          return item.split_config.end_field === '' || item.split_config.start_field === '';
        }
        return item.var_name === '';
      });
      const haveEmptyVarName = isEmptyArr.some((isEmpty: boolean) => isEmpty);
      // 收集所有字段名用于重复性检查
      const allFieldNames: string[] = [];
      if (!haveEmptyVarName) {
        paramList.value.forEach((item: any) => {
          if (item.field_category === 'time_range_select' || item.field_category === 'time-ranger') {
            if (item.split_config.start_field) allFieldNames.push(item.split_config.start_field);
            if (item.split_config.end_field) allFieldNames.push(item.split_config.end_field);
          } else if (item.var_name) {
            allFieldNames.push(item.var_name);
          }
        });
      }

      // 检查是否存在重复的字段名
      // eslint-disable-next-line max-len
      const haveSameVarName = allFieldNames.some((name: string, index: number) => allFieldNames.indexOf(name) !== index);

      haveSameName.value = haveSameVarName;
      isVarNameNOPass.value = haveEmptyVarName || haveSameVarName;
      return isVarNameNOPass.value;
    },
  });

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

.var-name-rules {
  border: 1px solid red !important;
}

.var-split-rules {
  border: 1px solid red !important;
}

.var-split {
  display: flex;
  border-bottom: 1px solid  #dcdee5;
}

.params-box {
  :deep(.bk-form-item) {
    margin-bottom: 0;
  }
}

.have-same-name {
  border: 1px solid red !important;
}

.have-same-name-text {
  font-size: 12px;
  color: red;
}
</style>
