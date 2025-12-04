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
  <card-part-vue :title="t('查询输入设置')">
    <template #content>
      <audit-form
        ref="formRef"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <div class="flex-item">
          <bk-form-item
            :label="t('URL')"
            label-width="160"
            property="api_config.url"
            required
            style="width: 50%;">
            <bk-input v-model="formData.api_config.url" />
          </bk-form-item>
          <bk-form-item
            :label="t('请求方式')"
            label-width="160"
            property="api_config.method"
            required
            style="margin-left: 30px;">
            <bk-radio-group
              v-model="formData.api_config.method"
              type="card">
              <bk-radio-button label="GET" />
              <bk-radio-button label="POST" />
            </bk-radio-group>
          </bk-form-item>
        </div>
        <bk-form-item
          :label="t('认证方式')"
          label-width="160"
          property="api_config.auth_config.method"
          required
          style="width: 50%;">
          <bk-select
            v-model="formData.api_config.auth_config.method"
            auto-focus
            class="bk-select">
            <bk-option
              v-for="(item, index) in authList"
              :id="item.value"
              :key="index"
              :disabled="item.disabled"
              :name="item.label" />
          </bk-select>
        </bk-form-item>
        <div class="auth-box">
          <bk-form-item
            :label="t('应用ID(bk_app_code)')"
            label-width="160"
            property="api_config.auth_config.config.bk_app_code"
            required>
            <bk-input v-model="formData.api_config.auth_config.config.bk_app_code" />
          </bk-form-item>
          <bk-form-item
            :label="t('安全(bk_app_secret)')"
            label-width="160"
            property="api_config.auth_config.config.bk_app_secret"
            required>
            <bk-input v-model="formData.api_config.auth_config.config.bk_app_secret" />
          </bk-form-item>
        </div>
        <div class="item-headers">
          <span>Headers</span>
          <div
            v-for="(headersItem, index) in formData.api_config.headers"
            :key="index"
            class="headers-config">
            <bk-input
              v-model="headersItem.value"
              class="config-input value"
              :placeholder="t('请输入 Key')" />
            <bk-input
              v-model="headersItem.key"
              class="config-input key"
              :placeholder="t('请输入 Value')" />
            <bk-input
              v-model="headersItem.description"
              class="config-input description"
              :placeholder="t('请输入 Headers 说明')" />
            <audit-icon
              class="headers-reduce-fill"
              type="reduce-fill"
              @click="handleDeleteHeaders(index)" />
          </div>
          <div
            class="item-headers-add"
            @click="handleAddHeaders">
            <audit-icon
              class="headers-plus-circle"
              type="plus-circle" />
            <span class="plus-circle-text">{{ t('添加 Headers') }}</span>
          </div>
        </div>
        <div class="item-params">
          <bk-checkbox v-model="formData.params">
            {{ t('参数设置') }}
          </bk-checkbox>
          <params-config
            v-if="formData.params"
            :input-variable="formData.input_variable" />
          <div class="item-params-add">
            <bk-button
              class="ml10"
              outline
              theme="primary"
              @click="handlerOpenDeDugRef">
              {{ t('接口调试') }}
            </bk-button>
            <span>
              <audit-icon
                :class="isSuccess ? 'delete-fill' : `corret-fill`"
                :type="isSuccess ? 'delete-fill' : `corret-fill`" />
              <span class="corret-fill-text">{{ t(isSuccess ? '调试失败' : '调试成功') }}</span>
            </span>
          </div>
        </div>
      </audit-form>
    </template>
  </card-part-vue>
  <result-config
    :output-config="formData.output_config"
    :result-data="resultData" />
  <de-dug
    ref="deDugRef"
    :api-config="formData.api_config"
    :input-variable="formData.input_variable"
    :is-params="formData.params" />
</template>
<script setup lang='tsx'>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CardPartVue from '../card-part.vue';

  import deDug from './debug-sideslider.vue';
  import paramsConfig from './params-config.vue';
  import resultConfig from './result/index.vue';


  const { t } = useI18n();
  const deDugRef = ref();
  const formData = ref({
    params: true,
    api_config: {
      url: 'www.baidu.com',
      method: 'GET',
      headers: [
        {
          key: 'xxx',
          value: 'xxx',
          description: 'xxx',
        },
      ],
      auth_config: {
        config: {
          bk_app_code: 'xxx',
          bk_app_secret: 'xxx',
        },
        method: 'bk_app_auth',
      },
    },
    input_variable: [
      {
        is_show: true,
        position: 'query',
        raw_name: 'time_range',
        required: true,
        description: '',
        display_name: 'time_range',
        split_config: {
          end_field: 'end_f',
          start_field: 'start_f',
        },
        default_value: null,
        field_category: 'time_range_select',
      },
      {
        is_show: true,
        position: 'body',
        raw_name: 'xxx',
        required: true,
        description: 'xxx',
        display_name: 'xxx',
        default_value: 'asdadasd',
        field_category: 'input',
      },
      {
        choices: [],
        is_show: true,
        position: 'query',
        raw_name: 'asdasd',
        required: true,
        description: 'asda',
        display_name: 'adssad',
        default_value: null,
        field_category: 'multiselect',
      },
    ],
    output_config: {
      groups: [
        {
          name: 'name1',
          output_fields: [
            {
              raw_name: 'key1',
              json_path: 'key1.key1',
              description: 'name1',
              display_name: 'name1',
              drill_config: null,
              field_config: {
                field_type: 'table',
                output_fields: [
                  {
                    raw_name: 'k1',
                    json_path: 'k1.key1',
                    description: 'name1',
                    display_name: 'k1',
                    drill_config: null,
                    enum_mappings: null,
                  },
                ],
              },
              enum_mappings: null,
            },
          ],
        },
        {
          name: 'name2',
          output_fields: [
            {
              raw_name: 'k2',
              json_path: 'kn2',
              description: '',
              display_name: 'n2',
              drill_config: null,
              field_config: {
                field_type: 'kv',
              },
              enum_mappings: null,
            },
          ],
        },
      ],
      enable_grouping: true,
    },
  });
  const rules = ref({
  });
  const authList = ref([
    {
      label: '无',
      value: 'none',
      disabled: false,
    },
    {
      label: '蓝鲸应用认证',
      value: 'bk_app_auth',
      disabled: false,
    },
  ]);
  const isSuccess = ref(false);
  const  resultData =  {
    result: true,
    code: 0,
    data: {
      page: 1,
      num_pages: 6895,
      total: 110314,
      results: [
        {
          risk_id: '20251201143641057057',
          event_content: '',
          strategy_id: 3,
          event_time: '2025-12-01 14:36:29',
          event_end_time: '2025-12-01 14:36:30',
          operator: [
            'v_yyhoyang',
          ],
          status: 'await_deal',
          current_operator: [
            'admin',
          ],
          notice_users: [
            'v_yyhoyang',
            'v_zzlgzhong',
          ],
          event_data: {},
          tags: [],
          risk_label: 'normal',
          experiences: 0,
          last_operate_time: '2025-12-01 14:36:41',
          title: 'raja 测试 doris 事件合流-实时策略[风险单标题]',
          permission: {
            edit_risk_v2: true,
          },
        },
        {
          risk_id: '20251201143641141076',
          event_content: '',
          strategy_id: 3,
          event_time: '2025-12-01 14:36:29',
          event_end_time: '2025-12-01 14:36:30',
          operator: [
            'v_yyhoyang',
          ],
          status: 'await_deal',
          current_operator: [
            'admin',
          ],
          notice_users: [
            'v_yyhoyang',
            'v_zzlgzhong',
          ],
          event_data: {},
          tags: [],
          risk_label: 'normal',
          experiences: 0,
          last_operate_time: '2025-12-01 14:36:41',
          title: 'raja 测试 doris 事件合流-实时策略[风险单标题]',
          permission: {
            edit_risk_v2: true,
          },
        },
      ],
      addd: [
        {
          risk_id: '20251201143641057057',
          event_content: '',
          strategy_id: 3,
          event_time: '2025-12-01 14:36:29',
          event_end_time: '2025-12-01 14:36:30',
          operator: [
            'v_yyhoyang',
          ],
          status: 'await_deal',
          current_operator: [
            'admin',
          ],
          notice_users: [
            'v_yyhoyang',
            'v_zzlgzhong',
          ],
          event_data: {},
          tags: [],
          risk_label: 'normal',
          experiences: 0,
          last_operate_time: '2025-12-01 14:36:41',
          title: 'raja 测试 doris 事件合流-实时策略[风险单标题]',
          permission: {
            edit_risk_v2: true,
          },
        },
        {
          risk_id: '20251201143641141076',
          event_content: '',
          strategy_id: 3,
          event_time: '2025-12-01 14:36:29',
          event_end_time: '2025-12-01 14:36:30',
          operator: [
            'v_yyhoyang',
          ],
          status: 'await_deal',
          current_operator: [
            'admin',
          ],
          notice_users: [
            'v_yyhoyang',
            'v_zzlgzhong',
          ],
          event_data: {},
          tags: [],
          risk_label: 'normal',
          experiences: 0,
          last_operate_time: '2025-12-01 14:36:41',
          title: 'raja 测试 doris 事件合流-实时策略[风险单标题]',
          permission: {
            edit_risk_v2: true,
          },
        },
      ],
    },
    message: null,
    request_id: '4033e443d3d026af4199706b24881ee8',
    trace_id: null,
  };
  const handlerOpenDeDugRef = () => {
    deDugRef.value?.show();
  };

  // 添加 headers
  const handleAddHeaders = () => {
    formData.value.api_config.headers.push({
      key: '',
      value: '',
      description: '',
    });
  };

  // 删除 headers
  const handleDeleteHeaders = (index: number) => {
    if (formData.value.api_config.headers.length === 1) {
      return;
    }
    formData.value.api_config.headers.splice(index, 1);
  };
</script>

<style lang="postcss" scoped>
.flex-item {
  display: flex;
  align-items: center;
  width: 100%;
}

.auth-box {
  width: 50%;
  height: 100%;
  padding: 10px 20px;
  margin-top: 10px;
  background: #f5f7fa;
  border-radius: 2px;
}

.item-headers {
  padding-top: 10px;
}

.headers-config {
  display: flex;
  align-items: center;
  width: 100%;
  margin-top: 10px;

  .config-input {
    margin-right: 10px;
  }

  .value {
    width: 25%;
  }

  .key {
    width: 20%;
  }

  .description {
    width: 35%;
  }

  .headers-reduce-fill {
    font-size: 16px;
    color: #c4c6cc;
    cursor: pointer;
  }
}

.item-headers-add {
  margin-top: 10px;
  color: #3a84ff;
  cursor: pointer;

  .headers-plus-circle {
    font-size: 14px;
  }

  .plus-circle-text {
    margin-left: 5px;
    font-size: 12px;
  }
}

.item-params {
  margin-top: 10px;
  cursor: pointer;

  .headers-plus-circle {
    font-size: 14px;
  }

  .plus-circle-text {
    margin-left: 5px;
    font-size: 12px;
  }
}

.item-params-add {
  padding-bottom: 10px;
  margin-top: 10px;
}

.corret-fill {
  margin-left: 17px;
  font-size: 14px;
  color: #2caf5e;
  cursor: none;
}

.delete-fill {
  margin-left: 17px;
  font-size: 14px;
  color: #ea3636;
  cursor: none;
}

.corret-fill-text {
  margin-left: 5px;
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0;
  color: #4d4f56;
  cursor: none;
}
</style>
