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
  <div class="simple-model">
    <div class="render-field">
      <div class="field-header-row">
        <div class="field-value">
          {{ t("字段名") }}

          <bk-popover
            hide-ignore-reference
            placement="right"
            theme="light"
            trigger="click">
            <audit-icon
              style="
                margin-left: 4px;
                font-size: 16px;
                color: #3a84ff;
                cursor: pointer;
              "
              type="jump-link" />
            <template #content>
              <raw-name-batch />
            </template>
          </bk-popover>
        </div>
        <div class="field-value">
          {{ t("显示名") }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 350px">
          {{ t("字段说明") }}
        </div>
        <div class="field-value">
          {{ t('字段下钻') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 50px">
          {{ t("") }}
        </div>
      </div>
      <audit-form
        ref="tableInputFormRef"
        form-type="vertical"
        :model="formData">
        <template
          v-for="(item, index) in formData.config.output_fields"
          :key="index">
          <div class="field-row">
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-popover
                  hide-ignore-reference
                  placement="right"
                  theme="light"
                  trigger="click">
                  <div class="item-text">
                    {{ t("请选择字段或批量选择") }}
                  </div>

                  <template #content>
                    <raw-name-select />
                  </template>
                </bk-popover>
              </bk-form-item>
            </div>
            <!-- 显示名 -->
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input v-model="item.display_name" />
              </bk-form-item>
            </div>
            <!-- 字段说明 -->
            <div
              class="field-value"
              style="flex: 0 0 350px">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input v-model="item.description" />
              </bk-form-item>
            </div>
            <!-- 字段下钻 -->
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <div
                  class="field-value-div"
                  @click="() => handleClick(index, item.drill_config)">
                  <template v-if="item.drill_config.tool.uid">
                    <audit-icon
                      style=" margin-right: 5px;font-size: 16px;"
                      svg
                      :type="iconMap[
                        getToolNameAndType(item.drill_config.tool.uid).type as keyof typeof iconMap
                      ]" />
                    {{ getToolNameAndType(item.drill_config.tool.uid).name }}
                    <audit-icon
                      class="remove-btn"
                      type="delete-fill"
                      @click.stop="handleRemove(index)" />
                    <audit-icon
                      v-if="!(item.drill_config.tool.version
                        >= (toolMaxVersionMap[item.drill_config.tool.uid] || 1))"
                      v-bk-tooltips="{
                        content: t('该工具已更新，请确认'),
                      }"
                      class="renew-tips"
                      type="info-fill" />
                  </template>
                  <span
                    v-else
                    style="color: #c4c6cc;">
                    {{ t('请配置') }}
                  </span>
                </div>
              </bk-form-item>
            </div>


            <div
              class="field-value"
              style="flex: 0 0 50px">
              <audit-icon
                style="
                margin-left: 4px;
                font-size: 16px;
                color: #b8babf;
                cursor: pointer;
              "
                type="add-fill" />
              <audit-icon
                style="
                margin-left: 4px;
                font-size: 16px;
                color: #b8babf;
                cursor: pointer;
              "
                type="reduce-fill

" />
            </div>
          </div>
        </template>
      </audit-form>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RawNameBatch from './raw-name-batch.vue';
  import RawNameSelect from './raw-name-select.vue';

  interface FormData {
    area?: string;
    source?: string;
    bkVersion?: string;
    radioGroupValue?: string;
    users?: string[];
    name: string;
    tags: string[];
    description: string;
    tool_type: string;
    data_search_config_type: string;
    config: {
      referenced_tables: Array<{
        table_name: string | null;
        alias: string | null;
        permission: {
          result: boolean;
        };
      }>;
      input_variable: Array<{
        raw_name: string;
        display_name: string;
        description: string;
        required: boolean;
        field_category: string;
        default_value: string | Array<string>;
        choices: Array<{
          key: string,
          name: string
        }>
      }>
      output_fields: Array<{
        raw_name: string;
        display_name: string;
        description: string;
        drill_config: {
          tool: {
            uid: string;
            version: number;
          };
          config: Array<{
            source_field: string;
            target_value_type: string;
            target_value: string;
          }>
        };
      }>
      sql: string;
      uid: string;
    };
  }
  const { t } = useI18n();

  const toolMaxVersionMap = ref<Record<string, number>>({});


  const formData = ref({
    config: {
      output_fields: [{
        raw_name: '',
        display_name: '',
        description: '',
        drill_config: {
          tool: {
            uid: '',
            version: 1,
          },
          config: [],
        },
      },
      ],
      sql: '',
      uid: '',
    },
  });

  const iconMap = {
    data_search: 'sqlxiao',
    api: 'apixiao',
    bk_vision: 'bkvisonxiao',
  };

  const getToolNameAndType = (uid: string) => {
    console.log(uid);
    return {
      name: '',
      type: '',
    };
  };
  const handleClick = (index: number, drillConfig?: FormData['config']['output_fields'][0]['drill_config']) => {
    console.log(index, drillConfig);
  };

  // 删除值
  const handleRemove = (index: number) => {
    formData.value.config.output_fields[index] = {
      ...formData.value.config.output_fields[index],
      drill_config: {
        tool: { uid: '', version: 1 },
        config: [],
      },
    };
  };
</script>
<style lang="postcss" scoped>
.simple-model {
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
          right: 28px;
          z-index: 1;
          display: none;
          font-size: 12px;
          color: #c4c6cc;
          transition: all .15s;

          &:hover {
            color: #979ba5;
          }
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
      border-top: 1px solid #dcdee5;
    }
  }
}

.item-text {
  width: 100%;
  height: 100%;

  /* text-align: center; */
  margin-left: 10px;
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0;
  color: #c4c6cc;
  cursor: pointer;
}
</style>
