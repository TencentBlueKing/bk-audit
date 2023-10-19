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
  <skeleton-loading
    :loading="loading"
    name="systemDetailApiPush">
    <div
      class="api-push-card">
      <div class="title">
        {{ t('API 推送') }}
        <span class="tag">push</span>
      </div>
      <div
        class="content"
        :class="{checked:checked}"
        @click="handleTaillog">
        <div class="api-icon">
          <audit-icon type="api" />
        </div>
        <div style="line-height: 20px;">
          <div class="flex">
            <span class="label">Token:  </span>
            <span>
              <auth-button
                v-if="!data.enabled"
                action-id="edit_system"
                :resource="route.params.id"
                style="margin-left: 19px;"
                text
                theme="primary"
                @click.stop="handleToken">
                {{ t('立即生成') }}
              </auth-button>
              <template
                v-else>
                <bk-loading
                  class="token"
                  :loading="isTokenLoading"
                  style="background: none;">
                  <template v-if="isGeting">
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
                        :resource="route.params.id">
                        <audit-icon
                          :type="isHide?'view':'hide'"
                          @click.stop="handleGetToken" />
                      </auth-component>
                      <auth-component
                        action-id="edit_system"
                        :resource="route.params.id">
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
            </span>
          </div>
          <div class="flex">
            <span class="label">EndPoint:  </span>
            <div class="flex point">
              <div
                v-bk-tooltips="{content: data.hosts.map((item: string)=>item).join('\n'), placement: 'bottom'}"
                class="ml5">
                <span
                  v-for="item in data.hosts.slice(0,3)"
                  :key="item"
                  class="point-item">
                  {{ item }}
                </span>
              </div>
              <div
                v-if="data.hosts"
                class="point-icon">
                <audit-icon
                  v-bk-tooltips="t('复制')"
                  class="ml12"
                  type="copy"
                  @click.stop="execCopy(data.hosts.map((item: string)=>item).join('\n'))" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </skeleton-loading>
</template>
<script setup lang="ts">
  import {
    onBeforeUnmount,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import useRequest from '@hooks/use-request';

  import {
    execCopy,
  } from '@utils/assist';

  interface Emits {
    (e: 'changeChecked', value: {id: string, name: string}): void
  }
  interface Exposes {
    handleCancelCheck: ()=>void
  }

  const emit = defineEmits<Emits>();
  const route = useRoute();
  const { t } = useI18n();

  const isHide = ref(false);
  const checked = ref(false);
  const hasGetToken = ref(false);
  const isTokenLoading = ref(false);
  const isGeting = ref(false);
  const timer = ref();

  // 获取启用状态&上报host （无需单独鉴权）
  const {
    loading,
    data,
  }  = useRequest(CollectorManageService.fetchApiPushHost, {
    defaultValue: {
      enabled: true,
      hosts: [],
    },
    defaultParams: {
      system_id: route.params.id,
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
    },
  });

  // 第一次生成token 后续无需再生成
  const handleGetToken = () => {
    if (!hasGetToken.value) {
      isTokenLoading.value = true;
      fetchApiPush({
        system_id: route.params.id,
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
        system_id: route.params.id,
      }).finally(() => {
        hasGetToken.value = true;
        isTokenLoading.value = false;
        execCopy(token.value.token, t('复制成功'));
      });
    } else {
      execCopy(token.value.token, t('复制成功'));
    }
  };

  // 立即生成
  const handleToken = () => {
    isHide.value = true;
    isGeting.value = true;
    createApiPush({
      system_id: route.params.id,
    });
    data.value.enabled = true;
    timer.value = setInterval(() => getToken(), 2000);
  };

  const getToken = () => {
    fetchApiPush({
      system_id: route.params.id,
    }).finally(() => {
      if (token.value.token) {
        isGeting.value = false;
        clearInterval(timer.value);
      }
    });
  };

  const handleTaillog = () => {
    checked.value = true;
    emit('changeChecked',  { id: 'api', name: 'API' });
  };

  onBeforeUnmount(() => {
    clearInterval(timer.value);
  });

  defineExpose<Exposes>({
    handleCancelCheck() {
      checked.value = false;
    },
  });
</script>
<style lang="postcss">
.api-push-card {
  padding: 16px 24px;
  cursor: pointer;
  background-color: #fff;
  border-radius: 2px;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%);

  .title {
    font-size: 14px;
    line-height: 22px;
    color: #313238;

    .tag {
      display: inline-block;
      height: 16px;
      padding: 0 4px;
      font-size: 12px;
      line-height: 16px;
      color: #fff;
      background: #979ba5;
      border-radius: 2px;
    }
  }

  .content {
    display: flex;
    padding: 5px 8px;
    padding-right: 12px;
    margin-top: 16px;
    line-height: 28px;
    color: #63656e;
    background: #f5f7fa;
    border: 1px solid #f5f7fa;
    border-radius: 2px;

    .bk-loading-mask {
      background: #f5f7fa !important;
      opacity: 100% !important;
    }

    .api-icon {
      width: 40px;
      height: 40px;
      margin-right: 12px;
      font-size: 22px;
      line-height: 37px;
      color: #979ba5;
      text-align: center;
      background-color: white;
      flex: 0 0 40px;
    }

    .label {
      color: #979ba5;
    }

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

    .ml5 {
      margin-left: 5px;
    }

    .point {
      max-height: 60px;
      margin-top: 2px;
      line-height: 19px;
      cursor: pointer;

      .point-item {
        display: block;
        max-width: 286px;
        overflow: hidden;
        text-overflow: ellipsis;
        word-break: break-all;
        white-space: nowrap;
      }
    }

    .point-icon {
      font-size: 14px;
      color: #979ba5;
      opacity: 0%;
    }

    .point:hover .point-icon {
      display: inline-block;
      opacity: 100%;
    }
  }

  .content:hover {
    cursor: pointer;
    background-color: #f0f1f5;

    .bk-loading-mask {
      background-color: #f0f1f5 !important;
      opacity: 100% !important;
    }
  }

  .checked {
    position: relative;
    background: rgb(225 236 255 / 60%) !important;
    border: 1px solid #3a84ff;
    border-radius: 2px;
  }

  .checked::after {
    position: absolute;
    top: 40%;
    right: -7px;
    border-color: #3a84ff #3a84ff transparent transparent;
    border-style: solid;
    border-width: 6px;
    content: "";
    transform: rotate(45deg);
  }
}

.token-tooltips {
  width: 286px;
  word-wrap: break-word;
}

</style>
