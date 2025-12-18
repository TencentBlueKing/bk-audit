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
  <audit-form
    ref="formRef"
    class="storage-base-info"
    form-type="vertical"
    :model="formData"
    :rules="rules">
    <div class="form-item-row">
      <bk-form-item
        class="form-item-col is-required"
        :label="t('存储名称')"
        property="cluster_name">
        <bk-input
          v-model="formData.cluster_name"
          :disabled="isEdit"
          :placeholder="t('请输入存储名称')" />
      </bk-form-item>
      <bk-form-item
        class="form-item-col is-required"
        :label="t('存储别名')"
        property="bkbase_cluster_en_name">
        <bk-input
          v-model="formData.bkbase_cluster_en_name"
          :placeholder="t('请输入存储别名')"
          :readonly="isEdit" />
      </bk-form-item>
    </div>
    <div class="form-item-row">
      <bk-form-item
        class="form-item-col is-required"
        :label="t('类型')"
        property="source_type">
        <bk-loading :loading="isGlobalDataLoading">
          <bk-select
            v-model="formData.source_type"
            :clearable="false"
            :placeholder="t('请选择类型')">
            <bk-option
              v-for="item in globalData.es_source_type"
              :key="item.id"
              :label="item.name"
              :value="item.id" />
          </bk-select>
        </bk-loading>
      </bk-form-item>
      <bk-form-item
        class="form-item-col is-required"
        :label="t('ES 地址')"
        property="domain_name">
        <bk-input
          v-model="formData.domain_name"
          :placeholder="t('请输入 ES 地址（IP）')"
          :readonly="isEdit" />
      </bk-form-item>
    </div>
    <div class="form-item-row">
      <bk-form-item
        class="form-item-col"
        :label="t('端口')"
        property="port"
        required>
        <bk-input
          v-model="formData.port"
          :placeholder="t('请输入端口')"
          :readonly="isEdit" />
      </bk-form-item>
      <bk-form-item
        class="form-item-col"
        :label="t('协议')"
        property="schema"
        required>
        <bk-select
          v-model="formData.schema"
          :clearable="false"
          :placeholder="t('请选择协议')">
          <bk-option
            label="HTTP"
            value="http" />
          <bk-option
            label="HTTPS"
            value="https" />
        </bk-select>
      </bk-form-item>
    </div>
    <div class="form-item-row">
      <bk-form-item
        class="form-item-col is-required"
        :label="t('用户名')"
        property="auth_info.username">
        <bk-input
          v-model="formData.auth_info.username"
          :placeholder="t('请输入用户名')" />
      </bk-form-item>
      <bk-form-item
        class="form-item-col is-required"
        :label="t('密码')"
        property="auth_info.password">
        <bk-input
          v-model="formData.auth_info.password"
          :placeholder="t('请输入密码')"
          type="password" />
      </bk-form-item>
    </div>
    <div>
      <bk-button
        :disabled="isConnectivityDetectePassed"
        :loading="isConnectivityDetectLoading"
        theme="primary"
        @click="handleConnectivityDetect">
        {{ t('连通性测试') }}
      </bk-button>
    </div>
    <template v-if="!isConnectivityDetectLoading">
      <connect-detect-result v-if="isConnectivityDetectePassed">
        <audit-icon
          class="ml8 mr8"
          svg
          type="completed" />
        <span>{{ t('连接成功') }}</span>
      </connect-detect-result>
      <template v-if="!isConnectivityDetecteMissed">
        <connect-detect-result v-if="!isConnectivityDetectePassed || isConnectivityDetectFailed">
          <audit-icon
            class="ml8 mr8"
            style="color: #ea3636;"
            svg
            type="delete-fill" />
          <span>{{ t('连接失败，请检查数据是否正确') }}</span>
        </connect-detect-result>
      </template>
      <connect-detect-result v-if="isShowMissMessage">
        <audit-icon
          class="ml8 mr8"
          style="color: #ea3636;"
          svg
          type="delete-fill" />
        <span>{{ t('提交数据前请先连通性测试') }}</span>
      </connect-detect-result>
    </template>
  </audit-form>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';
  import StorageManageService from '@service/storage-manage';

  import GlobalsModel from '@model/meta/globals';

  import useRequest from '@hooks/use-request';

  import ConnectDetectResult from '../../connect-detect-result/index.vue';

  interface Props {
    modelValue: {
      cluster_name: string,
      bkbase_cluster_en_name: string,
      domain_name: string,
      source_type: string,
      port: number,
      schema: string,
      auth_info: {
        username: string,
        password: string,
      },
    },
    isEdit: boolean,
  }
  interface Emits {
    (e: 'update:connectivityDetect', isPassed: boolean):void;
    (e: 'update:modelValue', value: Props['modelValue']): void,
  }

  const props = withDefaults(defineProps<Props>(), {
    isEdit: false,
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const rules = {
    cluster_name: [{
      validator: (value: string) => !!value,
      trigger: 'blur',
      message: t('存储名称不能为空'),
    }],
    'auth_info.username': [{
      validator: (value: string) => !!value,
      trigger: 'blur',
      message: t('用户名不能为空'),
    }],
    'auth_info.password': [{
      validator: (value: string) => !!value,
      trigger: 'blur',
      message: t('密码不能为空'),
    }],
    domain_name: [{
      validator: (value: string) => !!value,
      trigger: 'blur',
      message: t('ES 地址不能为空'),
    }],
    source_type: [{
      validator: (value: string) => !!value,
      trigger: 'blur',
      message: t('类型不能为空'),
    }],
    bkbase_cluster_en_name: [
      {
        validator: (value: string) => !!value,
        trigger: 'blur',
        message: t('存储别名不能为空'),
      },
      {
        validator: (value: string) => /^[A-Za-z0-9_]+$/.test(value),
        message: t('存储别名仅支持：A-Za-z0-9_'),
        trigger: 'blur',
      },
    ],
  };

  const formData = ref({} as Props['modelValue']);

  const formRef = ref();

  // 编辑状态已做过连通性测试
  const isConnectivityDetecteMissed = ref(true);
  const isShowMissMessage = ref(false);

  const {
    loading: isGlobalDataLoading,
    data: globalData,
  } = useRequest(MetaManageService.fetchGlobals, {
    defaultValue: new GlobalsModel(),
    manual: true,
  });

  const {
    data: isConnectivityDetectePassed,
    loading: isConnectivityDetectLoading,
    error: isConnectivityDetectFailed,
    run: startConnectivityDetect,
  } = useRequest(StorageManageService.connectivityDetect, {
    defaultValue: false,
  });

  // 同步值
  watch(() => props.modelValue, (modelValue) => {
    if (modelValue === formData.value) {
      return;
    }
    formData.value = _.cloneDeep(modelValue);
  }, {
    immediate: true,
  });

  // 连通性测试成功更新值
  watch(isConnectivityDetectePassed, (isPassed) => {
    emit('update:connectivityDetect', isPassed);
    if (isPassed) {
      emit('update:modelValue', formData.value);
    }
  });

  // 数据有改动需要重新测试
  watch(formData, () => {
    isConnectivityDetectePassed.value = false;
    isConnectivityDetectFailed.value = false;
    isConnectivityDetecteMissed.value = true;
    isShowMissMessage.value = false;
  }, {
    deep: true,
  });

  // 连通性测试
  const handleConnectivityDetect = () => {
    formRef.value.validate()
      .then(() => {
        isConnectivityDetecteMissed.value = false;
        isShowMissMessage.value = false;
        startConnectivityDetect({
          ...formData.value,
        });
      });
  };

  defineExpose({
    getData() {
      return formRef.value.validate()
        .then(() => {
          // 没有连通性测试
          if (isConnectivityDetecteMissed.value) {
            isShowMissMessage.value = true;
            return Promise.reject('没有连通性测试');
          }
          if (isConnectivityDetectePassed.value) {
            return {
              ...formData.value,
            };
          }
          // 连通性测试失败
          return Promise.reject('连通性测试失败');
        });
    },
  });
</script>

