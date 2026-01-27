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
  <div
    v-if="currentStep === 1"
    class="log-create-api-push">
    <bk-form
      ref="formRef"
      class="api-form"
      :model="formData"
      :rules="formRules">
      <!-- 记录上报日志 -->
      <div class="content-section">
        <div class="log-create-header">
          <div class="log-create-header-title">
            {{ t('记录上报日志') }}
          </div>
          <div class="log-create-header-line" />
          <div class="log-create-header-desc">
            {{ t('根据规范要求，使用SDK记录并上报日志') }}
          </div>
        </div>
        <bk-form-item
          :label="t('选择SDK')"
          property="sdk"
          required>
          <div class="sdk-support">
            <span class="sdk-support-desc">{{ t('请根据你要接入系统的代码语言，选择对应 SDK，若无符合您需求的 SDK，请联系系统负责人') }}</span>
            <bk-radio-group v-model="formData.sdk">
              <bk-radio-button
                v-for="item in selectSdkTypeList"
                :key="item.label"
                :label="item.label">
                {{ item.name }}
              </bk-radio-button>
            </bk-radio-group>
            <div class="sdk-support-footer">
              <span>{{ t('前往SDk') }}：</span>
              <a
                :href="selectedSdkUrl"
                target="_blank">{{ selectedSdkUrl }}</a>
            </div>
          </div>
        </bk-form-item>
      </div>

      <!-- 上报日志须知 -->
      <div class="content-section">
        <bk-form-item
          :label="t('上报日志须知')"
          property="notice"
          required>
          <div class="log-create-notice">
            <bk-radio
              v-model="formData.notice.read_requirement"
              label="true"
              @change="handleNoticeChange">
              {{ t('我已阅读') }}
              <a
                :href="configData?.audit_doc_config?.audit_access_guide"
                target="_blank">{{ t('《审计中心接入要求》') }}</a>
            </bk-radio>
            <div>
              <bk-radio
                v-model="formData.notice.read_standard"
                label="true"
                @change="handleNoticeChange">
                {{ t('我已了解') }}
                <a
                  :href="configData?.audit_doc_config?.audit_operation_log_record_standards"
                  target="_blank">{{ t('《审计中心操作日志记录标准》') }}</a>
              </bk-radio>
            </div>
          </div>
        </bk-form-item>
      </div>
    </bk-form>

    <div class="footer-actions">
      <auth-button
        v-if="!data.enabled"
        action-id="edit_system"
        :loading="isCreating"
        :resource="route.params.systemId"
        style="margin-left: 19px;"
        theme="primary"
        @click="handleCreate">
        {{ t('创建') }}
      </auth-button>
      <bk-button
        class="ml8"
        @click="handlePrevious">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </div>
  </div>
  <data-inspection v-else />
</template>
<script setup lang="ts">
  import { computed, inject, nextTick, onMounted, type Ref, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@/hooks/use-request';
  import dataInspection from '@/views/system-manage/log-create/components/data-inspection/index.vue';

  const { t } = useI18n();

  const route = useRoute();
  const router = useRouter();
  const isCreating = ref(false);
  const currentStep = ref(1);
  const formRef = ref();
  const formData = ref({
    enabled: false,
    sdk: 'PYTHON_SDK',
    notice: {
      read_requirement: '',
      read_standard: '',
    },
  });

  const formRules = {
    notice: [
      {
        message: t('请先阅读上报日志须知'),
        trigger: 'change',
        validator: (value: any) => !!value.read_requirement && !!value.read_standard,
      },
    ],
  };

  const selectSdkTypeList = ref([
    {
      label: 'PYTHON_SDK',
      name: 'PYTHON SDk',
      url: 'https://github.com/TencentBlueKing/bk-audit-python-sdk',
    },
    {
      label: 'JAVA_SDK',
      name: 'JAVA SDk',
      url: 'https://github.com/TencentBlueKing/bk-audit-java-sdk',
    },
    {
      label: 'GO_SDK',
      name: 'Go SDk',
      url: 'https://github.com/TencentBlueKing/bk-audit-go-sdk',
    },
  ]);

  const configData = inject<Ref<ConfigModel>>('configData');

  // 根据选中的 SDK 类型获取对应的 URL
  const selectedSdkUrl = computed(() => {
    const selectedSdk = selectSdkTypeList.value.find(item => item.label === formData.value.sdk);
    return selectedSdk?.url || 'https://github.com/TencentBlueKing/bk-audit-sdk';
  });

  // 获取启用状态&上报host （无需单独鉴权）
  const {
    // loading,
    data,
  }  = useRequest(CollectorManageService.fetchApiPushHost, {
    defaultValue: {
      enabled: true,
      hosts: [],
    },
    defaultParams: {
      system_id: route.params.systemId,
    },
    manual: true,
  });

  // 生成token
  const {
    run: createApiPush,
  }  = useRequest(CollectorManageService.createApiPush, {
    defaultValue: {},
    onSuccess: (res) => {
      data.value.enabled = res;
      // 用于创建表单校验
      formData.value.enabled = res;

      isCreating.value = false;
      currentStep.value = 2;
    },
  });

  // 手动触发 notice 表单项校验
  const handleNoticeChange = () => {
    formRef.value?.validate('notice');
  };

  const handlePrevious = () => {
    router.push({
      name: 'logCreate',
      params: {
        systemId: route.params.systemId,
      },
      query: {
        type: 'logCreate',
      },
    });
  };
  const handleCancel = () => {
    router.push({
      name: 'systemDetail',
      params: {
        id: route.params.systemId,
      },
      query: {
        contentType: 'dataReport',
      },
    });
  };
  const handleCreate = () => {
    formRef.value.validate().then(() => {
      isCreating.value = true;
      createApiPush({
        system_id: route.params.systemId,
      });
    });
  };
  onMounted(() => {
    // 加入route参数
    nextTick(() => {
      router.replace({
        name: route.name!,
        params: {
          ...route.params,
        },
        query: {
          ...route.query,
          routeTitleTp: t('SDK 接入'),
        },
      });
    });
  });
</script>
<style scoped lang="postcss">
.log-create-api-push {
  padding: 16px 24px;
  background: #fff;

  .api-form {
    width: 66%;

    :deep(.bk-radio-label) {
      font-size: 12px;
    }
  }
}

.content-section {
  .log-create-header {
    display: flex;
    align-items: center;
    margin-bottom: 24px;

    .log-create-header-line {
      width: 1px;
      height: 12px;
      margin: 0 10px;
      background: #979ba5;
    }

    .log-create-header-title {
      font-size: 14px;
      font-weight: 600;
      color: #313238;
    }

    .log-create-header-desc {
      font-size: 12px;
      color: #979ba5;
      vertical-align: middle;
    }
  }

  .sdk-support {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .sdk-support-desc {
      font-size: 12px;
      color: #979ba5;
    }

    .sdk-support-footer {
      padding: 0 12px;
      margin-top: 6px;
      font-size: 12px;
      color: #4d4f56;
      background-color: #f5f7fa;
    }
  }

  .log-create-notice {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
}

.footer-actions {
  display: flex;
  margin-top: 32px;
  gap: 8px;
}
</style>
