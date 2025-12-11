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
  <bk-sideslider
    v-model:isShow="isShow"
    quick-close
    :title="t('接口调试')"
    transfer
    :width="600">
    <div class="info">
      <div class="title">
        {{ t('请求信息') }}
      </div>
      <div class="info-concent">
        <div class="left">
          <div class="info-concent-item">
            URL:
          </div>
          <div class="info-concent-item">
            {{ t('请求方式') }}:
          </div>
          <div class="info-concent-item">
            {{ t('认证方式') }}:
          </div>
          <div class="info-concent-item">
            {{ t('Headers') }}:
          </div>
        </div>
        <div class="right">
          <div class="info-concent-item">
            {{ apiConfig.url }}
          </div>
          <div class="info-concent-item">
            {{ apiConfig.method }}
          </div>
          <div class="info-concent-item">
            {{ apiConfig.auth_config.method }}
          </div>
          <div class="info-concent-item item-headers">
            <div
              v-for="(item, index) in apiConfig.headers"
              :key="index">
              <div class="item-headers-item">
                {{ item.key || "--" }}: {{ item.value || "--" }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div

      class="params">
      <div
        v-if="isParams"
        class="title">
        {{ t('接口参数') }}
      </div>
      <bk-form
        v-if="isParams"
        class="example"
        form-type="vertical"
        :model="formModel"
        :rules="rules">
        <bk-form-item
          v-for="(item, index) in list"
          :key="index"
          :label="item.display_name"
          :property="item.display_name"
          :required="item.required">
          <template #label>
            <bk-popover
              placement="top"
              theme="dark">
              <span class="dashed-underline">{{ t(item.display_name) }}</span>
              <template #content>
                <div>{{ t(item.description) }}</div>
              </template>
            </bk-popover>
          </template>
          <bk-input
            v-if="item.field_category == 'number_input'"
            v-model="formModel[item.display_name]"
            clearable
            type="number" />
          <audit-user-selector
            v-else-if="item.field_category === 'person_select'"
            v-model="formModel[item.display_name]" />
          <date-picker
            v-else-if="item.field_category === 'time_range_select' || item.field_category === 'time-ranger'"
            v-model="formModel[item.display_name]"
            style="width: 100%" />

          <bk-date-picker
            v-else-if="item.field_category === 'time_select' || item.field_category === 'time-picker'"
            v-model="formModel[item.display_name]"
            append-to-body
            clearable
            style="width: 100%"
            type="datetime" />
          <bk-input
            v-else
            v-model="formModel[item.display_name]"
            clearable />
        </bk-form-item>
      </bk-form>
      <bk-button
        theme="primary"
        @click="handleDebug">
        {{ t('调试') }}
      </bk-button>
    </div>
    <div class="info">
      <div class="title">
        {{ t('响应结果') }}
      </div>
      <div class="result">
        <pre
          v-if="!isErr"
          class="json-result">{{ result }}</pre>
        <div
          v-else
          class="err">
          <audit-icon
            class="alert"
            type="alert" />
          <span>{{ t('工具目前仅支持解析Json格式的数据') }}</span>
        </div>
      </div>
    </div>
  </bk-sideslider>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import { DateRange } from '@blueking/date-picker';

  import { formatDate } from '@utils/assist/timestamp-conversion';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface FormItem {
    display_name: string;
    description: string;
    required: boolean;
    field_category: string;
    default_value?: any;
    time_range?: any;
    var_name: string;
    raw_name: string;
  }
  interface Props {
    apiConfig: Record<string, any>,
    isParams: boolean,
  }
  interface Exposes {
    init: (data: FormItem[]) => void;
  }

  interface Emits {
    (e: 'deBugDone', id: string, is: boolean): void
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const isErr = ref(false);
  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const isShow = ref(false);
  const formModel = ref<Record<string, any>>({});
  const rules = ref({});

  const list = ref<FormItem[]>([]);

  const result = ref();

  const {
    run: fetchToolsDebug,
  } = useRequest(ToolManageService.fetchToolsDebug, {
    defaultValue: {},
    onSuccess: () => {
    },
  });

  // 调试
  const handleDebug = () => {
    const config = {
      api_config: props.apiConfig,
      input_variable: props.isParams ?  list.value : [],
      output_config: {
        enable_grouping: true,
        groups: [],
      },
    };
    const params = list.value.map((i) => {
      if (i.field_category === 'time_range_select' || i.field_category === 'time-ranger') {
        let val = [];
        const date = new DateRange(i.default_value, 'YYYY-MM-DD HH:mm:ss', window.timezone);
        val = [date.startDisplayText, date.endDisplayText];
        return {
          raw_name: i.raw_name,
          value: val,
        };
      }
      if (i.field_category === 'time_select' || i.field_category === 'time-picker') {
        return {
          raw_name: i.raw_name,
          value: formatDate(i.default_value),
        };
      }

      return {
        raw_name: i.raw_name,
        value: i.default_value,
      };
    });

    fetchToolsDebug({
      tool_type: 'api',
      config,
      params: props.isParams ?  {
        tool_variables: props.isParams ?  params : [],
      } : {},
    }).then((res) => {
      if (res.data.status_code === 200) {
        messageSuccess('调试成功');
        isErr.value = false;
        result.value = JSON.stringify(res.data.result);
        emits('deBugDone', JSON.stringify(res.data.result), true);
      } else {
        isErr.value = true;
        emits('deBugDone', '', false);
      }
    });
  };

  const initWithData = (data: FormItem[]) => {
    isShow.value = true;
    list.value = data;
    formModel.value = data.reduce((obj: Record<string, any>, item: Record<string, any>) => {
      // eslint-disable-next-line no-param-reassign
      obj[item.display_name] = item.field_category === 'time_range_select' ? item.time_range :  item.default_value;
      return obj;
    }, {});
  };

  defineExpose<Exposes>({
    init(data: FormItem[]) {
      initWithData(data);
    },
  });

</script>

<style lang="postcss" scoped>
.info {
  padding: 20px;

  .info-concent {
    display: flex;
    padding: 10px;
    margin-top: 10px;
    font-size: 12px;
    line-height: 20px;
    letter-spacing: 0;
    color: #4d4f56;
    background-color: #f5f7fa;

    .info-concent-item {
      margin-bottom: 10px;
    }

    .left {
      width: 80px;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      text-align: right;
    }

    .right {
      margin-left: 10px;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      text-align: left;
      flex: 1;
    }

    .lable {
      margin-bottom: 10px;
    }

    .value {
      margin-bottom: 10px;
    }
  }
}

.title {
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
  letter-spacing: 0;
  color: #4d4f56;
}

.example {
  padding-top: 20px;
}

.params {
  padding: 20px;
}

.result {
  margin-top: 10px;

  .json-result {
    padding: 15px;
    margin: 0;
    font-family: Monaco, Menlo, 'Ubuntu Mono', monospace;
    font-size: 12px;
    line-height: 1.5;
    color: #4d4f56;
    word-break: break-all;
    white-space: pre-wrap;
    background-color: #f5f7fa;
    border-radius: 4px;
  }
}

.err {
  height: 32px;
  padding-right: 10px;
  padding-left: 10px;
  margin-top: 5px;
  line-height: 32px;
  background: #ffebeb;
  border-radius: 2px;

  .alert {
    margin-right: 5px;
    font-size: 14px;
    color: #ea3636;
  }
}

.data-structure {
  padding: 16px;
  background: #f8f9fa;
  border: 1px solid #dcdee5;
  border-radius: 4px;

  .data-header {
    padding-bottom: 8px;
    margin-bottom: 16px;
    border-bottom: 1px solid #dcdee5;

    .tool-type {
      font-size: 14px;
      font-weight: 600;
      color: #313238;
    }
  }

  .data-content {
    .data-section {
      margin-bottom: 20px;

      .section-title {
        padding-left: 8px;
        margin-bottom: 8px;
        font-size: 13px;
        font-weight: 600;
        color: #63656e;
        border-left: 3px solid #3a84ff;
      }

      .data-row {
        display: flex;
        padding: 6px 8px;
        margin-bottom: 8px;
        background: white;
        border-radius: 2px;
        align-items: flex-start;

        .label {
          min-width: 80px;
          font-size: 12px;
          font-weight: 500;
          color: #63656e;
        }

        .value {
          margin-left: 12px;
          font-size: 12px;
          font-weight: 600;
          color: #313238;
        }

        .sql-code {
          padding: 4px 8px;
          font-family: Monaco, Menlo, 'Ubuntu Mono', monospace;
          font-size: 11px;
          color: #313238;
          word-break: break-all;
          white-space: pre-wrap;
          background: #f0f1f5;
          border-radius: 2px;
          flex: 1;
        }
      }
    }

    .results-preview {
      .result-item {
        display: flex;
        padding: 8px;
        margin-bottom: 8px;
        background: white;
        border: 1px solid #dcdee5;
        border-radius: 2px;
        align-items: flex-start;

        .result-index {
          min-width: 30px;
          margin-right: 8px;
          font-size: 11px;
          font-weight: 500;
          color: #979ba5;
        }

        .result-content {
          margin: 0;
          font-family: Monaco, Menlo, 'Ubuntu Mono', monospace;
          font-size: 11px;
          color: #313238;
          word-break: break-all;
          white-space: pre-wrap;
          flex: 1;
        }
      }

      .more-results {
        padding: 8px;
        font-size: 11px;
        color: #979ba5;
        text-align: center;
        background: #f0f1f5;
        border-radius: 2px;
      }
    }
  }
}

.no-data {
  padding: 40px;
  font-size: 14px;
  color: #979ba5;
  text-align: center;
  background: #f8f9fa;
  border: 1px dashed #dcdee5;
  border-radius: 4px;
}
</style>
