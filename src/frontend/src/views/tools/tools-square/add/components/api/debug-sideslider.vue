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
        <div>URL: xxxxx</div>
        <div>{{ t('请求方式') }}: GET</div>
        <div>{{ t('认证方式') }}: 1111111111111111</div>
        <div>{{ t('Headers') }}: ASDDASDASDAD</div>
      </div>
    </div>
    <div class="params">
      <div class="title">
        {{ t('接口参数') }}
      </div>
      <bk-form
        class="example"
        form-type="vertical"
        :model="formModel"
        :rules="rules">
        <bk-form-item
          v-for="item in list"
          :key="item.display_name"
          :label="item.lable"
          :property="item.display_name"
          required>
          <bk-input
            v-model="formModel[item.display_name]"
            clearable
            placeholder="请输入" />
        </bk-form-item>
      </bk-form>
      <bk-button theme="primary">
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
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Exposes {
    show: () => void;
  }
  const { t } = useI18n();
  const isShow = ref(false);
  const formModel = ref({});
  const rules = ref({});
  const list = ref([
    {
      lable: '姓名',
      value: '张三',
      display_name: 'name',
    },
    {
      lable: '年龄',
      value: '18',
      display_name: 'age',
    },
  ]);

  const result = ref(`{
  "status": "success",
  "message": "操作成功",
  "data": {
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
}`);
  defineExpose<Exposes>({
    show() {
      isShow.value = true;
    },
  });

  onMounted(() => {
    formModel.value = list.value.reduce((obj, item) => {
      // eslint-disable-next-line no-param-reassign
      obj[item.display_name] = '';
      return obj;
    }, {});
    console.log('formModel', formModel.value);
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
