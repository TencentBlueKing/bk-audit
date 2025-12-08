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
      :model="formData">
      <!-- 新建数据上报 -->
      <div class="content-section">
        <div class="log-create-header">
          <div class="log-create-header-title">
            {{ t('新建数据上报') }}
          </div>
          <div class="log-create-header-line" />
          <div class="log-create-header-desc">
            {{ t('基于权限模型或数据接入数据，可上传或数据至审计中心，以供后续分析与风险追踪；因不同方式流程有差异，请先选择上报方式') }}
          </div>
        </div>
        <bk-form-item
          :label="t('认证授权')"
          property="enabled">
          <div class="auth-wrapper">
            <div class="auth-item">
              <span class="auth-label">Token：</span>
              <div class="auth-content">
                <auth-button
                  v-if="!data.enabled"
                  action-id="edit_system"
                  outline
                  :resource="route.params.systemId"
                  style="margin-left: 19px;"
                  theme="primary">
                  {{ t('点击创建后，立即生成token') }}
                </auth-button>
                <template
                  v-else>
                  <bk-loading
                    class="token"
                    :loading="isGeting"
                    style="background: none;">
                    <template v-if="isGeting || isTokenLoading">
                      <span
                        class="token-text"
                        style="color: #3a84ff;">
                        <audit-icon
                          class="rotate-loading"
                          svg
                          type="loading" />
                        {{ t('生成中') }}
                      </span>
                    </template>
                    <template v-else>
                      <template v-if="isHide">
                        <span
                          v-bk-tooltips="{content: token.token, placement: 'top', extCls:'token-tooltips'}"
                          class="token-text">{{ token.token }}</span>
                      </template>
                      <span v-else>
                        <span
                          v-for="i in 7"
                          :key="i"
                          class="encryption" />
                      </span>
                      <span
                        class="operation-icon">
                        <auth-component
                          action-id="edit_system"
                          :resource="route.params.systemId">
                          <audit-icon
                            :type="isHide?'view':'hide'"
                            @click.stop="handleGetToken" />
                        </auth-component>
                        <auth-component
                          action-id="edit_system"
                          :resource="route.params.systemId">
                          <audit-icon
                            v-bk-tooltips="t('复制')"
                            class="ml12"
                            type="copy"
                            @click.stop="handleTokenCopy" />
                        </auth-component>
                      </span>
                    </template>
                  </bk-loading>
                </template>
              </div>
            </div>
            <div class="auth-item">
              <div
                class="auth-label"
                style="height: 36px;">
                <span>EndPoint：</span>
              </div>
              <div
                v-bk-tooltips="{content: data.hosts.map((item: string)=>item).join('\n'), placement: 'bottom'}"
                class="auth-content-endpoint">
                <template
                  v-for="item in data.hosts.slice(0,3)"
                  :key="item">
                  <div
                    class="auth-desc">
                    {{ item }}
                  </div>
                </template>
              </div>
              <div
                v-if="data.hosts"
                class="point-icon">
                <audit-icon
                  v-bk-tooltips="t('复制')"
                  class="ml12"
                  type="copy"
                  @click.stop="() => execCopy(data.hosts.map((item: string)=>item).join('\n'))" />
              </div>
            </div>
          </div>
        </bk-form-item>
      </div>

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
          required
          :rules="[
            {
              message: t('请先阅读上报日志须知'),
              trigger: 'change',
              validator: (value: any) => {
                return !!value.read_requirement && !!value.read_standard;
              },
            },
          ]">
          <div class="log-create-notice">
            <bk-radio
              v-model="formData.notice.read_requirement"
              label="true">
              {{ t('我已阅读') }}
              <a
                :href="configData?.audit_doc_config?.audit_access_guide"
                target="_blank">{{ t('《审计中心接入要求》') }}</a>
            </bk-radio>
            <div>
              <bk-radio
                v-model="formData.notice.read_standard"
                label="true">
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
      <bk-button class="ml8">
        {{ t('取消') }}
      </bk-button>
    </div>
  </div>
  <data-inspection v-else />
</template>
<script setup lang="ts">
  import { computed, inject, onBeforeUnmount, type Ref, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import ConfigModel from '@model/root/config';

  import {
    execCopy,
  } from '@utils/assist';

  import useRequest from '@/hooks/use-request';
  import dataInspection from '@/views/system-manage/log-create/components/data-inspection/index.vue';

  const { t } = useI18n();

  const route = useRoute();
  const isHide = ref(false);
  const isGeting = ref(false);
  const isCreating = ref(false);
  const hasGetToken = ref(false);
  const isTokenLoading = ref(false);
  const timer = ref();
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

  const selectSdkTypeList = ref([
    {
      label: 'PYTHON_SDK',
      name: 'Python SDk',
      url: 'https://github.com/TencentBlueKing/bk-audit-python-sdk',
    },
    {
      label: 'JAVA_SDK',
      name: 'Java SDk',
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

  // 获取token
  const {
    run: fetchApiPush,
    data: token,
  }  = useRequest(CollectorManageService.fetchApiPush, {
    defaultValue: {},
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
    },
  });

  const handleToken = () => {
    isHide.value = true;
    isGeting.value = true;
    createApiPush({
      system_id: route.params.systemId,
    });
    // data.value.enabled = true;
    timer.value = setInterval(() => getToken(), 2000);
  };

  const getToken = () => {
    fetchApiPush({
      system_id: route.params.systemId,
    }).finally(() => {
      if (token.value.token) {
        isGeting.value = false;
        clearInterval(timer.value);
      }
    });
  };

  // 第一次生成token 后续无需再生成
  const handleGetToken = () => {
    if (!hasGetToken.value) {
      isTokenLoading.value = true;
      fetchApiPush({
        system_id: route.params.systemId,
      }).finally(() => {
        hasGetToken.value = true;
        isHide.value = !isHide.value;
        isTokenLoading.value = false;
      });
    } else {
      isHide.value = !isHide.value;
    }
  };

  // 复制同理，第一次生成token后续无需再生成
  const handleTokenCopy = () => {
    if (!hasGetToken.value) {
      isTokenLoading.value = true;
      fetchApiPush({
        system_id: route.params.systemId,
      }).finally(() => {
        hasGetToken.value = true;
        isTokenLoading.value = false;
        execCopy(token.value.token, t('复制成功'));
      });
    } else {
      execCopy(token.value.token, t('复制成功'));
    }
  };

  const handleCreate = () => {
    isCreating.value = true;
    formRef.value.validate().then(() => {
      handleToken();
    })
      .finally(() => {
        isCreating.value = false;
        currentStep.value = 2;
      });
  };

  onBeforeUnmount(() => {
    clearInterval(timer.value);
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

  .auth-wrapper {
    display: flex;
    flex-direction: column;
    gap: 8px;

    .auth-item {
      position: relative;
      display: flex;
      padding: 14px 16px;
      align-items: center;
      background-color: #f5f7fa;
      border-radius: 4px;
      gap: 10px;

      .auth-label {
        display: flex;
        align-items: flex-start;
        font-size: 12px;
        color: #63656e;
      }

      .auth-content {
        display: flex;
        align-items: center;

        .token {
          display: flex;
          margin-left: 19px;
          cursor: pointer;

          .token-text {
            display: inline-block;
            width: 251px;
            overflow: hidden;
            text-overflow: ellipsis;
          }

          .encryption {
            display: inline-block;
            width: 5px;
            height: 5px;
            margin-right: 5px;
            background-color: #63656e;
            border-radius: 50%;
          }

          .operation-icon {
            display: none;
            padding: 0 12px;
            font-size: 14px;
            color: #979ba5;

            .ml12 {
              margin-left: 12px;
            }
          }
        }

        .token:hover {
          .operation-icon {
            display: inline-block;
          }
        }
      }

      .auth-content-endpoint {
        display: flex;
        flex-direction: column;
        gap: 4px;

        .auth-desc {
          font-size: 12px;
          line-height: 16px;
          color: #63656e;
        }
      }

      .point-icon {
        position: absolute;
        top: 0;
        right: 8px;
        font-size: 14px;
        color: #3a84ff;
      }
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
