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
    :width="600"
    @close="handleClose">
    <div class="info">
      <div class="title">
        {{ t('请求信息') }}
      </div>
      <div class="info-concent">
        <!-- <div class="left"> -->
        <div class="info-concent-item">
          <div class="info-concent-item-left">
            URL:
          </div>
          <div class="info-concent-item-value">
            {{ apiConfig.url }}
          </div>
        </div>
        <div class="info-concent-item">
          <div class="info-concent-item-left">
            {{ t('请求方法') }}:
          </div>
          <div class="info-concent-item-value">
            {{ apiConfig.method }}
          </div>
        </div>
        <div class="info-concent-item">
          <div class="info-concent-item-left">
            {{ t('认证方式') }}:
          </div>
          <div class="info-concent-item-value">
            {{ getMethodText(apiConfig.auth_config.method) }}
          </div>
        </div>
        <div class="info-concent-item">
          <div class="info-concent-item-left">
            {{ t('请求头') }}:
          </div>
          <div class="info-concent-item-value">
            <div v-if="apiConfig.headers.length === 0">
              --
            </div>
            <div v-else>
              <div
                v-for="(item, index) in apiConfig.headers"
                :key="index">
                <div class="item-headers-item">
                  {{ item.key || "--" }} = {{ item.value || "--" }}
                </div>
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
        ref="formRef"
        class="example"
        form-type="vertical"
        :model="formModel"
        :rules="rules">
        <span
          v-for="(item, index) in list"
          :key="index">
          <bk-form-item
            v-if="handleIsShow(item.is_show)"
            :property="item.raw_name"
            :required="item.required === 'true'">
            <template
              #label>
              <bk-popover
                v-if="item.description !== ''"
                placement="top"
                theme="dark">
                <span class="dashed-underline">{{ item.display_name === '' ? item.var_name
                  : `${item.display_name}(${item.var_name})` }}</span>
                <template #content>
                  <div>{{ t(item.description) }}</div>
                </template>
              </bk-popover>
              <span v-if="item.description ===''">{{ item.display_name === '' ? item.var_name
                : `${item.display_name}(${item.var_name})` }}</span>
            </template>
            <span>
              <bk-input
                v-if="item.field_category == 'number_input'"
                v-model="formModel[item.raw_name]"
                clearable
                type="number" />
              <audit-user-selector
                v-else-if="item.field_category === 'person_select'"
                v-model="formModel[item.raw_name]" />
              <div
                v-else-if="item.field_category === 'time_range_select' || item.field_category === 'time-ranger'"
                @mouseenter.stop="handleMouseEnterTimeRange(item.raw_name)"
                @mouseleave.stop="handleMouseLeaveTimeRange">

                <date-picker
                  v-model="formModel[item.raw_name]"
                  style="width: 100%" />
                <audit-icon
                  v-show="MouseEnterTimeRange === item.raw_name && formModel[item.raw_name].length > 0"
                  class="delete-fill-btn"
                  type="delete-fill"
                  @click.stop="handleDeleteTimeRange(item.raw_name)" />
              </div>

              <bk-date-picker
                v-else-if="item.field_category === 'time_select' || item.field_category === 'time-picker'"
                v-model="formModel[item.raw_name]"
                append-to-body
                clearable
                style="width: 100%"
                type="datetime" />
              <bk-input
                v-else
                v-model="formModel[item.raw_name]"
                clearable />
            </span>
          </bk-form-item>
        </span>
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
      <div
        v-if="!isErr && (isNoSuccess || isNOJson)"
        class="err">
        <audit-icon
          class="alert"
          type="alert" />
        <span>{{ t( isNOJson ? '工具目前仅支持解析Json格式的数据' : '工具调试接口失败') }}</span>
      </div>
      <scroll-faker
        v-if="isDebug"
        style="height: 53vh">
        <div
          class="result">
          <pre
            v-if="result"
            class="json-result">
          <json-viewer
          copyable
          expand-depth="99"
          theme="jv-light"
          :value="JSON.parse(result)" /></pre>
        </div>
      </scroll-faker>
      <bk-exception
        v-if="isErr && (!isNoSuccess && !isNOJson)"
        :description="t('数据查询失败')"
        type="500" />
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
    required:string;
    field_category: string;
    default_value?: any;
    time_range?: any;
    var_name: string;
    raw_name: string;
    is_show: boolean | string;
    position: string;
  }
  interface Props {
    apiConfig: Record<string, any>,
    isParams: boolean,
    authList:Array<{
      id: string,
      name: string
    }>,
    isSuccess: boolean
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
  const isNoSuccess = ref(false);
  const isDebug = ref(false);
  const isNOJson = ref(false);
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const formRef = ref();
  const isShow = ref(false);
  const formModel = ref<Record<string, any>>({});
  const rules = ref({});

  const list = ref<FormItem[]>([]);

  const result = ref();
  const MouseEnterTimeRange = ref<string| null>(null);

  const getMethodText = (method: string) => props.authList?.find(item => item.id === method)?.name;
  const handleMouseEnterTimeRange = (e: string) => {
    MouseEnterTimeRange.value = e;
  };
  const handleMouseLeaveTimeRange = () => {
    MouseEnterTimeRange.value = null;
  };

  // 时间组件删除
  const handleDeleteTimeRange = (rawName: string) => {
    formModel.value[rawName] = [];
  };
  const {
    run: fetchToolsDebug,
  } = useRequest(ToolManageService.fetchToolsDebug, {
    defaultValue: {},
    onSuccess: () => {
    },
  });

  const handleIsShow = (val: boolean | string) => val === true || val === 'true';
  // 处理表单字段值转换
  const processFieldValue = (field: FormItem) => {
    const value = formModel.value[field.raw_name];

    if (field.field_category === 'time_range_select' || field.field_category === 'time-ranger') {
      const date = new DateRange(value, 'YYYY-MM-DD HH:mm:ss', window.timezone);
      return [date.startDisplayText, date.endDisplayText];
    }

    if (field.field_category === 'time_select' || field.field_category === 'time-picker') {
      return formatDate(value);
    }
    if (field.field_category === 'person_select') {
      return value.join(',');
    }
    return value;
  };

  // 构建调试请求参数
  const buildDebugParams = () => list.value.map(field => ({
    raw_name: field.raw_name,
    value: processFieldValue(field),
  }));

  // 处理调试响应结果
  const handleDebugResponse = (res: any) => {
    if (res && res.data) {
      switch (res.data.err_type) {
      case 'non_json_response':
        isErr.value = false;
        isNoSuccess.value = false;
        isNOJson.value = true;
        result.value = JSON.stringify(res.data);
        emits('deBugDone', '', false);
        break;
      case 'request_error':
        isErr.value = true;
        isNoSuccess.value = false;
        isNOJson.value = false;
        emits('deBugDone', '', false);
        break;
      case 'none':
        if (res.data.status_code !== 200) {
          isErr.value = false;
          isNoSuccess.value = true;
          isNOJson.value = false;
          result.value = JSON.stringify(res.data.result);
          emits('deBugDone', '', false);
        } else {
          messageSuccess('调试成功');
          isErr.value = false;
          isNoSuccess.value = false;
          isNOJson.value = false;
          result.value = JSON.stringify(res.data.result);
          emits('deBugDone', JSON.stringify(res.data.result), true);
        }
        break;
      }
    } else {
      isErr.value = true;
      isNoSuccess.value = false;
      emits('deBugDone', '', false);
    }
  };

  // 执行调试请求
  const executeDebugRequest = () => {
    isDebug.value = true;
    result.value = null;

    const config = {
      api_config: props.apiConfig,
      input_variable: props.isParams ? list.value : [],
      output_config: {
        enable_grouping: true,
        groups: [],
      },
    };

    const params = buildDebugParams();

    fetchToolsDebug({
      tool_type: 'api',
      config,
      params: props.isParams ? {
        tool_variables: params,
      } : {},
    }).then(handleDebugResponse);
  };

  // 调试
  const handleDebug = () => {
    if (list.value.length === 0) {
      executeDebugRequest();
      return;
    }

    formRef.value.validate().then(executeDebugRequest);
  };

  const initWithData = (data: FormItem[]) => {
    isShow.value = true;
    list.value = JSON.parse(JSON.stringify(data));
    formModel.value = data.reduce((obj: Record<string, any>, item: Record<string, any>) => {
      // eslint-disable-next-line no-param-reassign
      obj[item.raw_name] = item.field_category === 'time_range_select' ? item.time_range :  item.default_value;
      return obj;
    }, {});
  };
  // 关闭初始化数据
  const handleClose = () => {
    if (props.isSuccess) {
      return;
    }
    isShow.value = false;
    list.value = [];
    formModel.value = {};
    isErr.value = false;
    isNoSuccess.value = false;
    result.value = '';
    isDebug.value = false;
    isNOJson.value = false;
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
    flex-direction: column;
    padding: 10px;
    margin-top: 10px;
    font-size: 12px;
    line-height: 20px;
    letter-spacing: 0;
    color: #4d4f56;
    background-color: #f5f7fa;

    .info-concent-item {
      display: flex;
      margin-bottom: 10px;

      .info-concent-item-left {
        width: 60px;
        margin-right: 8px;
        text-align: right;
      }

      .info-concent-item-value {
        word-break: break-all;
        white-space: normal;
        flex: 1;
        overflow-wrap: break-word;
      }
    }

  }
}

.title {
  padding-bottom: 10px;
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
    word-break: break-word;
    word-wrap: break-word;
    overflow-wrap: break-word;
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
          word-break: break-word;
          word-wrap: break-word;
          overflow-wrap: break-word;
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
          word-break: break-word;
          word-wrap: break-word;
          overflow-wrap: break-word;
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

.delete-fill-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1000;
  color: #c4c6cc;

  &:hover {
    color: #979ba5;
    cursor: pointer;
  }
}
</style>
<style  lang="postcss">
.jv-push {
  .open {
    background-color: transparent;  /* 透明背景 */
  }}
</style>
