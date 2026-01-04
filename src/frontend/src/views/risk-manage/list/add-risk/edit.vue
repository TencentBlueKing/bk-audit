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
  <div class="config">
    <card-part-vue
      :is-open="false"
      :show-icon="false"
      :title="t('基础配置')">
      <template #content>
        <div class="flex-center">
          <audit-form
            ref="formRef"
            class="example"
            form-type="vertical"
            :model="formData"
            :rules="rules">
            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                property="strategy_id"
                required>
                <template #label>
                  <span
                    v-bk-tooltips="t('手动创建风险单，事件字段来源于审计策略配置')"
                    class="dashed-underline">{{ t("审计策略") }}</span>
                </template>
                <bk-select
                  v-model="formData.strategy_id"
                  class="bk-select"
                  filterable
                  @select="handleSelect">
                  <bk-option
                    v-for="item in strategyList.results"
                    :id="item.strategy_id"
                    :key="item.strategy_id"
                    :disabled="item.status !== 'running'"
                    :name="`${item.strategy_name} (${item.strategy_id})`"
                    :popover-options="{ boundary: 'parent'}">
                    <bk-popover
                      v-if="item.status !== 'running'"
                      max-width="800px"
                      placement="top"
                      theme="light">
                      <div style="width: 100%;height: 100%; color: #c4c6cc;">
                        {{ `${item.strategy_name} (${item.strategy_id})` }}
                      </div>
                      <template #content>
                        <div>
                          {{ t('该策略已停用，暂不支持创建风险单') }}
                        </div>
                      </template>
                    </bk-popover>
                    <span v-else>

                      {{ `${item.strategy_name} (${item.strategy_id})` }}
                    </span>
                  </bk-option>
                </bk-select>
              </bk-form-item>

              <bk-form-item
                class="base-item"
                :label="t('事件发生时间')"
                property="event_time"
                required>
                <bk-date-picker
                  v-model="formData.event_time"
                  append-to-body
                  clearable
                  type="datetime" />
              </bk-form-item>
            </div>
          </audit-form>
        </div>
      </template>
    </card-part-vue>
    <card-part-vue
      :is-open="false"
      :show-icon="false"
      :title="t('事件数据')">
      <template #content>
        <div v-if="eventList.length === 0">
          {{ t('暂无数据') }}
        </div>
        <div
          v-else
          class="event-table">
          <div class="table-heard">
            <div class="table-index border-right">
              #
            </div>
            <div class="table-label border-right">
              <span class="table-text">{{ t('字段名称') }}</span>
            </div>
            <div class="table-type border-right">
              <span class="table-text">
                {{ t('表单类型') }}
              </span>
            </div>
            <div class="table-value">
              <span class="table-text">{{ t('字段值') }}
              </span>
            </div>
          </div>
          <div
            v-for="(item, index) in eventList"
            :key="index"
            class="table-list">
            <div class="table-index border-right">
              {{ index + 1 }}
            </div>
            <div
              class="table-label border-right field-type-box">
              <!-- <span
                v-if="item?.field_type"
                class="field-type">{{ item?.field_type }}</span> -->
              <span
                v-bk-tooltips="{
                  content: item?.description,
                  disabled: item?.description === '',
                  placement: 'top'
                }"
                class="table-text"
                :class="item?.description !== '' ? 'dashed-underline' : '' ">
                <tool-tip-text
                  :data="`${item?.field_name}(${item?.display_name})`"
                  :line="1"
                  placement="top"
                  style="
                  padding: 0;
                  vertical-align: middle;
                  "
                  theme="light" />
              </span>
            </div>
            <div class="table-type border-right">
              <!-- {{ item.typeValue }} {{ item.field_type }} -->
              <bk-select
                v-model="item.typeValue"
                behavior="simplicity"
                class="field-type-list"
                :filterable="false"
                style=" height: 100%;background-color: #fff;">
                <!-- <template #trigger="{ selected }">
                  <div class="trigger">
                    {{ selected[0]?.label }}
                    <audit-icon
                      class="table-info-fill"
                      type="angle-line-down" />
                  </div>
                </template> -->
                <bk-option
                  v-for="type in item.fieldTypeList"
                  :id="type.typeValue"
                  :key="type.typeValue"
                  :name="type.label" />
              </bk-select>
            </div>
            <div class="table-value">
              <field-com
                ref="fieldComRef"
                :type="item.typeValue"
                :value="item.valueText"
                @update="(val: any) => handlerUpdate(val, item)" />
            </div>
          </div>
        </div>
      </template>
    </card-part-vue>
  </div>
</template>

  <script lang="ts" setup>
  import { nextTick, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import useRequest from '@hooks/use-request';

  import CardPartVue from '../../../tools/tools-square/add/components/card-part.vue';

  import fieldCom from './field-components.vue';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';
  import { convertGMTTimeToStandard, convertToTimestamp } from '@/utils/assist/timestamp-conversion';

  interface Exposes{
    getEditData: () => void;
    handlerReturnData: (data: any) => void;
    validate: () => void;
  }
  interface Emits {
    (e: 'validateSuccess'): void
    (e: 'getselectedRiskValue', data: any): void
  }

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const formData = ref({
    strategy_id: '',
    event_time: new Date(),
  });
  const rules = ref();
  const formRef = ref();
  const fieldComRef = ref();
  const selectedValue = ref('');
  const eventList = ref<Array<Record<string, any>>>([]);
  const selectedRiskValue = ref();
  const handleSelect = (value: string) => {
    selectedValue.value = value;
    // eslint-disable-next-line max-len
    selectedRiskValue.value = strategyList.value.results.find((item: Record<string, any>) => item.strategy_id === value);
    eventList.value = selectedRiskValue.value?.event_data_field_configs.map((item: Record<string, any>) => {
      let typeValueDefault = 'input';
      if (item.field_type === 'string') {
        typeValueDefault = 'input';
      }
      if (item.field_type === 'timestamp') {
        typeValueDefault = 'date-picker';
      }
      if (item.field_type === 'text') {
        typeValueDefault = 'textarea';
      }
      if (item.field_type === 'double' || item.field_type === 'float' || item.field_type === 'int' || item.field_type === 'long') {
        typeValueDefault = 'number-input';
      }
      return {
        ...item,
        typeValue: typeValueDefault,
        value: '',
        fieldTypeList: comTypeList(item.field_type),
      };
    }).filter((e: Record<string, any>) => e.is_show);
  };
  const typeList = ref([
    {
      label: t('输入框'),
      value: 'input',
      typeValue: 'input',
    },
    {
      label: t('时间选择器'),
      value: 'date-picker',
      typeValue: 'date-picker',
    },
    {
      label: t('数字输入框'),
      value: 'number-input',
      typeValue: 'number-input',
    },
    {
      label: t('人员选择器'),
      value: 'user-selector',
      typeValue: 'user-selector',
    },
    {
      label: t('文本框'),
      value: 'textarea',
      typeValue: 'textarea',
    },
  ]);

  const comTypeList = (type: string) => {
    if (type === 'string') { // 字符串
      return typeList.value.filter((item: Record<string, any>) => item.value === 'input' || item.value === 'user-selector' || item.value === 'date-picker');
    } if (type === 'double' || type === 'float' || type === 'int' || type === 'long') { // 数字
      return typeList.value.filter((item: Record<string, any>) => item.value === 'number-input' || item.value === 'date-picker');
    } if (type === 'text') { // 文本
      return typeList.value.filter((item: Record<string, any>) => item.value === 'textarea');
    } if (type === 'timestamp') { // 时间
      return typeList.value.filter((item: Record<string, any>) => item.value === 'date-picker');
    }
    return typeList.value;
  };

  // 策略列表
  const {
    data: strategyList,
    run: fetchStrategyList,
  } = useRequest(StrategyManageService.fetchStrategyList, {
    defaultParams: {
      strategy_type: 'rule',
    },
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 1,
    },
    manual: true,
  });

  const handlerUpdate = (value: any, item: any) => {
    // 当 long double float int 类型时，需要转换时间格式
    let valueText: string | number | null = null;
    if ((item.field_type === 'long' || item.field_type === 'double' || item.field_type === 'float' || item.field_type === 'int')
      && item.typeValue === 'date-picker') {
      valueText = convertToTimestamp(value);
    } else if (item.typeValue === 'user-selector') {
      valueText = value.join(',');
    } else {
      valueText = value;
    }
    eventList.value.forEach((eventItem: any) => {
      if (eventItem.field_name === item.field_name  && eventItem.display_name === item.display_name) {
        // eslint-disable-next-line no-param-reassign
        eventItem.valueText = value;
        // eslint-disable-next-line no-param-reassign
        eventItem.value = valueText;
      }
    });
  };

  // 表单验证
  const validate = () => {
    formRef.value.validate().then(() => {
      emits('validateSuccess');
    });
  };

  onMounted(() => {
  });

  defineExpose<Exposes>({
    // 获取编辑数据
    getEditData() {
      return {
        formData: { ...formData.value, event_time: convertGMTTimeToStandard(formData.value.event_time)  },
        eventData: eventList.value,
        selectedRiskValue: selectedRiskValue.value,
      };
    },
    // 回显数据
    handlerReturnData(data: any) {
      nextTick(() => {
        selectedValue.value = data.formData.strategy_id;
        formData.value = data.formData;
        eventList.value = data.eventData;
        fetchStrategyList().then((res) => {
          selectedRiskValue.value = res.results.find((item: any) => item.strategy_id === data.formData.strategy_id);
        });
      });
    },
    validate() {
      validate();
    },
  });
  </script>

  <style lang="postcss" scoped>
    .config {
      width: 96%;
      margin-top: 20px;
      margin-left: 2%;

      /* background-color: #f5f7fa; */
      overflow: hidden;

      .base-form-item {
        display: flex;
        justify-content: space-between;

        .base-item {
          width: 48%;
        }
      }

      .dashed-underline {
        padding-bottom: 2px;

        /* 可选，增加文字和虚线间距 */
        border-bottom: 1px dashed #c4c6cc;
      }
    }

    .event-table {
      width: 96%;
      margin-top: 20px;
      margin-left: 2%;
      border: 1px solid #dcdee5;

      .border-right {
        border-right: 1px solid #dcdee5;
      }

      .field-type-box {
        display: flex;
      }

      .table-text {
        padding: 0 10px;
        line-height: 42px;
      }

      .table-heard {
        display: flex;
        height: 42px;
        line-height: 42px;
        background: #f5f7fa;
        border-bottom: 1px solid #dcdee5;
      }

      .table-list {
        display: flex;
        height: 42px;
        line-height: 42px;
        border-bottom: 1px solid #dcdee5;
      }

      .table-index {
        width: 32px;
        text-align: center;
      }

      .table-label {
        width: 270px;
      }

      .table-type {
        width: 140px;
      }

      .table-value {
        display: flex;
        width: 250px;
        height: auto;
        line-height: normal;
        flex: 1;
        align-items: center;
        justify-content: center;
      }

      .table-info-fill {
        font-size: 12px;
        color: #c4c6cc;
      }

      .event-type {
        height: 22px;
        padding: 5px 10px;
        margin-left: 10px;
        font-size: 12px;
        color: #1768ef;
        background: #e1ecff;
        border-radius: 12px;
      }

      .trigger {
        display: flex;
        margin-right: 10px;
        margin-left: 10px;
        font-size: 12px;
        line-height: 0px;
        letter-spacing: 0;
        color: #63656e;
        cursor: pointer;
        align-items: center;
        justify-content: space-between;
      }
    }

    .field-type {
      height: 20px;
      padding: 1px 5px;
      margin-top: 12px;
      margin-left: 5px;
      font-size: 12px;
      line-height: normal;
      color: #1768ef;
      background: #e1ecff;
      border-radius: 10px;
      align-items: center;
      justify-content: center;
    }

    .field-type-list {
      :deep(.bk-input) {
        border: none !important;
      }
    }
  </style>
