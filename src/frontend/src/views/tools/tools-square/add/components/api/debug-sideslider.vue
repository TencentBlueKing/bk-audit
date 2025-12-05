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
        <pre class="json-result">{{ result }}</pre>
        <div class="err">
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

  import useMessage from '@/hooks/use-message';


  interface Props {
    apiConfig: Record<string, any>,
    // inputVariable: Array<Record<string, any>>
    isParams: boolean,
  }
  interface Exposes {
    init: () => void;
  }

  interface Emits {
    (e: 'deBugDone', id: string): void
  }

  defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess, messageError } = useMessage();

  const isShow = ref(false);
  const formModel = ref({});
  const rules = ref({});
  const list = ref([]);

  const result = ref('');

  // 调试
  const handleDebug = () => {
    console.log('debug');
    messageSuccess('调试成功');
    messageError('调试失败');
    result.value = `{
  "status": "success",
  "message": "操作成功",
  "data": {

    "status": "success",
    "list": [ {
            "field_name": "event_tb_key",
            "display_name": "event_tb_key",
            "id": "event_tb_key:event_tb_key"
        },
        {
            "field_name": "mrms_openid",
            "display_name": "mrms_openid",
            "id": "mrms_openid:mrms_openid"
        },
        {
            "field_name": "风险ID",
            "display_name": "风险ID",
            "id": "风险ID:风险ID"
        }
      ],
    "person": {
      "name": "张明",
      "age": 28,
      "contact": {
        "email": "zhangming@email.com",
        "phone": "+86-138-0011-0022",
        "address": {
          "street": "人民路123号",
          "city": "北京市",
          "district": "朝阳区",
          "postalCode": "100020"
        }
      }
    }
  }
}`;
    emits('deBugDone', result.value, true);
  };
  defineExpose<Exposes>({
    init(data: Array<Record<string, any>>) {
      isShow.value = true;
      list.value = data;
      formModel.value = data.reduce((obj, item) => {
        // eslint-disable-next-line no-param-reassign
        obj[item.display_name] = item.field_category === 'time_range_select' ? item.time_range :  item.default_value;
        return obj;
      }, {});
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
</style>
