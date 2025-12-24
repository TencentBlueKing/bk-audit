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
              type="card"
              @change="handleMethodChange">
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
              :id="item.id"
              :key="index"
              :name="item.name" />
          </bk-select>
        </bk-form-item>
        <div
          v-if="formData.api_config.auth_config.method === 'bk_app_auth'"
          class="auth-box">
          <bk-form-item
            :label="t('应用ID(bk_app_code)')"
            label-width="160"
            property="api_config.auth_config.config.bk_app_code"
            required>
            <bk-input v-model="formData.api_config.auth_config.config.bk_app_code" />
          </bk-form-item>
          <bk-form-item
            :label="t('密钥(bk_app_secret)')"
            label-width="160"
            property="api_config.auth_config.config.bk_app_secret"
            required>
            <bk-input
              v-model="formData.api_config.auth_config.config.bk_app_secret"
              type="password" />
          </bk-form-item>
        </div>
        <div class="item-headers">
          <span>Headers</span>
          <div
            v-for="(headersItem, index) in formData.api_config.headers"
            :key="index"
            class="headers-config">
            <span class="rules-header-key-span">
              <bk-input
                v-model="headersItem.key"
                class="config-input value"
                :class="(handleRulesHeadersKey(headersItem.key) &&
                  !isHeadersPass &&
                  isHeadersNoPassIndex.includes(index) )? 'rules-header-key' : '' "
                :placeholder="t('请输入 Key')"
                @change="handleHeadersKeyChange" />
              <span
                v-if="handleRulesHeadersKey(headersItem.key)
                  && !isHeadersPass &&
                  isHeadersNoPassIndex.includes(index)"
                class="rules-header-key-text">{{ t('请输入 Key') }}</span>
            </span>
            <bk-input
              v-model="headersItem.value"
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
          <bk-checkbox
            v-model="isParams"
            class="item-params-checkbox">
            {{ t('参数设置') }}
          </bk-checkbox>
          <params-config
            v-if="isParams"
            ref="paramsConfigRef"
            :api-variable-position="apiVariablePosition"
            :input-variable="formData.input_variable" />
          <div class="item-params-add">
            <bk-button
              class="ml10"
              outline
              theme="primary"
              @click="handlerOpenDeDugRef">
              {{ t('接口调试') }}
            </bk-button>
            <span v-if="isDoneDeBug">
              <audit-icon
                :class="isSuccess ? 'corret-fill' : `delete-fill`"
                :type="isSuccess ? 'corret-fill' : `delete-fill`" />
              <span class="corret-fill-text">{{ t(isSuccess ? '调试成功' : '调试失败') }}</span>
            </span>
          </div>
        </div>
      </audit-form>
    </template>
  </card-part-vue>
  <result-config
    v-if="(isSuccess && isDoneDeBug) || isEditMode"
    ref="resultConfigRef"
    :is-edit-mode="isEditMode"
    :result-data="resultData" />
  <de-dug
    ref="deDugRef"
    :api-config="formData.api_config"
    :auth-list="authList"
    :is-params="isParams"
    @de-bug-done="handleDeBugDone" />
</template>
<script setup lang='tsx'>
  import { computed, nextTick, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import resultDataModel from '@model/tool/api';

  import useRequest from '@hooks/use-request';

  import CardPartVue from '../card-part.vue';

  import deDug from './debug-sideslider.vue';
  import paramsConfig from './params-config.vue';
  import { buildTree } from './result/build-tree';
  import resultConfig from './result/index.vue';


  interface Props {
    isEditMode: boolean;
  }

  interface Exposes {
    getFields: () => void;
    setConfigs: (data: any) => void;
    getDebugResult: () => void;
  }

  defineProps<Props>();
  const { t } = useI18n();
  const deDugRef = ref();
  const formRef = ref();
  const resultConfigRef = ref();
  const paramsConfigRef = ref();
  const isParams = ref(true);
  const formData = ref({
    api_config: {
      url: '',
      method: 'GET',
      headers: [] as Array<{ key: string; value: string; description: string }>,
      auth_config: {
        config: {
          bk_app_code: '',
          bk_app_secret: '',
        },
        method: 'bk_app_auth',
      },
    },
    input_variable: [
      {
        is_show: 'true',
        position: 'query',
        raw_name: '',
        required: 'true',
        description: '',
        display_name: '',
        split_config: {
          end_field: '',
          start_field: '',
        },
        default_value: null,
        field_category: 'input',
      },
    ],
    output_config: {
      groups: [
        {
          name: '',
          output_fields: [
            {
              raw_name: '',
              json_path: '',
              description: '',
              display_name: '',
              drill_config: null,
              field_config: {
                field_type: '',
                output_fields: [
                  {
                    raw_name: '',
                    json_path: '',
                    description: '',
                    display_name: '',
                    drill_config: null,
                    enum_mappings: null,
                  },
                ],
              },
              enum_mappings: null,
            },
          ],
        },
      ],
      enable_grouping: true,
    },
  });
  const rules = ref({});
  const authList = ref<Array<{
    id: string,
    name: string
  }>>([]);
  const apiVariablePositionList = ref<Array<{
    id: string,
    name: string,
    lable: string
  }>>([]);
  const apiVariablePosition =  computed(() => {
    if (formData.value.api_config.method === 'GET') {
      return apiVariablePositionList.value.filter((item: any) => item.id !== 'body');
    }
    return apiVariablePositionList.value;
  });
  // 获取字段类型
  const {
    run: fetchGlobalChoices,
  } = useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    onSuccess(result) {
      if (result) {
        authList.value = result.api_auth_method;
        apiVariablePositionList.value = result.api_variable_position.map((item: any) => ({
          id: item.id,
          name: item.name,
          lable: item.id[0].toUpperCase() + item.id.slice(1),
        }));
      }
    },
  });

  const isSuccess = ref(false);
  const isDoneDeBug = ref(false);
  const resultData = ref<Array<resultDataModel> | string>('');
  const isHeadersPass = ref(true);
  const isHeadersNoPassIndex = ref<number[]>([]);
  const handlerOpenDeDugRef = () => {
    isHeadersPass.value = true;
    isHeadersNoPassIndex.value = [];
    // 判断 formData.value.api_config.headers中的key是否为空 isHeadersNoPassIndex 存储不为空的数组下标index
    if (formData.value.api_config.headers.some((item: any) => item.key === '')) {
      isHeadersPass.value = false;
      formData.value.api_config.headers.forEach((item: any, index: number) => {
        if (item.key === '') {
          isHeadersNoPassIndex.value.push(index);
        }
      });
      return;
    }
    if (paramsConfigRef.value?.validatePass()) {
      return;
    }
    formRef.value.validate().then(() => {
      const paramsConfig =  paramsConfigRef.value?.getData() || [];
      deDugRef.value?.init(paramsConfig);
    });
  };

  // 方法改变默认值
  const handleMethodChange = (value: string) => {
    paramsConfigRef.value?.changeMethod(value);
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
    formData.value.api_config.headers.splice(index, 1);
  };

  // 调试
  const handleDeBugDone = (res: any, isSucc: boolean) => {
    resultData.value = '';
    nextTick(() => {
      resultData.value = res;
      isSuccess.value = isSucc;
      isDoneDeBug.value = true;
    });
  };

  const initResultConfig = (data: any) => {
    resultData.value = data.output_config.result_schema?.tree_data;
    resultConfigRef.value.setConfigs(data.output_config);
  };

  // 检查是否为空
  const handleRulesHeadersKey = (key: string) => key === '';
  const handleHeadersKeyChange = () => {
    isHeadersPass.value = true;
    isHeadersNoPassIndex.value = [];
  };
  onMounted(() => {
    fetchGlobalChoices();
  });
  defineExpose<Exposes>({
    // 提交获取字段
    getFields() {
      formData.value.input_variable = paramsConfigRef.value?.getData();
      // 处理resultData.value的类型转换
      const resultDataString = typeof resultData.value === 'string'
        ? resultData.value
        : JSON.stringify(resultData.value);

      formData.value.output_config = {
        ...resultConfigRef.value?.handleGetResultConfig(),
        result_schema: {
          tree_data: Array.isArray(JSON.parse(resultDataString))
            ? resultDataString :  JSON.stringify(buildTree(JSON.parse(resultDataString))),
        },
      };
      return formData.value;
    },
    setConfigs(data: any) {
      isParams.value = false;
      nextTick(() => {
        formData.value.api_config = data.api_config;
        isParams.value = data.input_variable?.length > 0;
        formData.value.input_variable = data.input_variable;
        formData.value.output_config = data.output_config;
        if (formData.value.api_config.auth_config.method === 'none') {
          formData.value.api_config.auth_config.config = {
            bk_app_code: '',
            bk_app_secret: '',
          };
        }
        initResultConfig(data);
      });
    },
    getDebugResult() {
      return {
        isDoneDeBug: isDoneDeBug.value,
        isSuccess: isSuccess.value,
      };
    },
  });

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
  padding-top: 24px;
}

.headers-config {
  display: flex;
  width: 100%;
  padding-bottom: 10px;
  margin-top: 10px;
  align-items: center;

  .config-input {
    margin-right: 10px;
  }

  .value {
    width: 98%;
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
  margin-top: 24px;
  cursor: pointer;

  .item-params-checkbox {
    padding-bottom: 10px;
  }

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
  margin-top: 12px;
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
  color: red;
  cursor: none;
}

.rules-header-key-span {
  display: inline-block;
  width: 20%;
  vertical-align: top;
}

.rules-header-key {
  border: 1px solid red;
}

.rules-header-key-text {
  /* vertical-align: bottom; */
  position: absolute;
  color: red;
}
</style>
