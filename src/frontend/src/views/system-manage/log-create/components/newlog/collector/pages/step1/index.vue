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
  <smart-action
    class="step1-action"
    :offset-target="getSmartActionOffsetTarget">
    <div class="step1-content">
      <audit-form
        ref="formRef"
        class="collector-form"
        :model="localFormData">
        <div class="content-section">
          <div class="section-header">
            <span class="section-title">{{ t('前置：记录日志') }}</span>
          </div>

          <bk-form-item
            :label="t('记录日志方式')"
            property="record_log_type"
            required>
            <bk-radio-group v-model="localFormData.record_log_type">
              <bk-radio-button
                label="SDK"
                style="width: 150px;">
                {{ t('SDK接入') }}
                <span class="recommend-text">{{ t('推荐') }}</span>
              </bk-radio-button>
              <bk-radio-button
                disabled
                label="LOG"
                style="width: 150px;">
                {{ t('Log接入') }}
              </bk-radio-button>
            </bk-radio-group>
            <div class="description-box">
              <span class="description-text">{{ t('使用审计中心提供的SDK，快速接入审计中心。') }}</span>
            </div>
          </bk-form-item>

          <bk-form-item
            :label="t('选择SDK')"
            property="select_sdk_type"
            required>
            <div class="sdk-support">
              <span class="sdk-support-desc">{{ t('请根据你要接入系统的代码语言，选择对应 SDK，若无符合您需求的 SDK，请联系系统负责人') }}</span>
              <bk-radio-group v-model="localFormData.select_sdk_type">
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
                v-model="localFormData.notice.read_requirement"
                :label="Boolean(true)">
                {{ t('我已阅读') }}
                <a
                  href="https://github.com/TencentBlueKing/bk-audit-sdk"
                  target="_blank">{{ t('《审计中心接入要求》') }}</a>
              </bk-radio>
              <div>
                <bk-radio
                  v-model="localFormData.notice.read_standard"
                  :label="Boolean(true)">
                  {{ t('我已了解') }}
                  <a
                    href="https://github.com/TencentBlueKing/bk-audit-sdk"
                    target="_blank">{{ t('《审计中心操作日志记录标准》') }}</a>
                </bk-radio>
              </div>
            </div>
          </bk-form-item>

          <bk-form-item
            :label="t('是否已上报')"
            property="is_reported"
            required
            :rules="[
              {
                message: t('请先选择是否已上报'),
                trigger: 'change',
                validator: (value: boolean) => !!value,
              },
            ]">
            <bk-radio
              v-model="localFormData.is_reported"
              :label="Boolean(true)">
              {{ t('已按照标准记录日志') }}
            </bk-radio>
          </bk-form-item>
        </div>
      </audit-form>
    </div>
    <template #action>
      <bk-button
        theme="primary"
        @click="handleStartCreate">
        {{ t('开始新建日志采集') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  // import MetaManageService from '@service/meta-manage';
  // import useRequest from '@/hooks/use-request';
  import { useRoute, useRouter } from 'vue-router';

  interface Props {
    formData: Record<string, any>
  }
  interface Emits {
    (e: 'next', step: number, data: Record<string, any>): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const formRef = ref();
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();

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
    }]);

  const getSmartActionOffsetTarget = () => document.querySelector('.step1-action');

  const localFormData = ref({ ...props.formData });

  const isEditMode = route.name === 'logCollectorEdit';

  if (isEditMode) {
    localFormData.value.notice.read_requirement = true;
    localFormData.value.notice.read_standard = true;
    localFormData.value.is_reported = true;
  }

  // 根据选中的 SDK 类型获取对应的 URL
  const selectedSdkUrl = computed(() => {
    const selectedSdk = selectSdkTypeList.value.find(item => item.label === localFormData.value.select_sdk_type);
    return selectedSdk?.url || 'https://github.com/TencentBlueKing/bk-audit-sdk';
  });

  // 获取字段类型
  // useRequest(MetaManageService.fetchGlobalChoices, {
  //   defaultValue: {},
  //   manual: true,
  //   onSuccess(result) {
  //     console.log('fetchGlobalChoices', result);
  //   },
  // });

  const handleStartCreate = () => {
    formRef.value.validate()
      .then(() => {
        emit('next', 2, localFormData.value);
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
</script>
<style scoped lang="postcss">
.step1-action {
  height: 100%;
}

.step1-content {
  .content-section {
    .section-header {
      display: flex;
      align-items: center;
      margin-bottom: 16px;

      .section-title {
        font-size: 14px;
        font-weight: 600;
        color: #313238;
      }

      .section-divider {
        width: 1px;
        height: 12px;
        margin: 0 10px;
        background: #979ba5;
      }

      .section-desc {
        font-size: 12px;
        color: #979ba5;
      }
    }
  }

  .bkbase-form {
    width: 66%;
  }

  .select-tip {
    position: absolute;
    top: 50%;
    right: 8px;
    z-index: 10;
    transform: translateY(-50%);

    .tip-number {
      display: inline-flex;
      width: 20px;
      height: 20px;
      font-size: 12px;
      color: #fff;
      background: #6366f1;
      border-radius: 50%;
      align-items: center;
      justify-content: center;
    }
  }
}

.collector-form {
  width: 66%;

  .recommend-text {
    padding: 2px 4px;
    font-size: 10px;
    color: #fff;
    background: #f59500;
    border-radius: 2px;
  }

  .description-box {
    width: 300px;
    padding: 0 8px;
    margin-top: 8px;
    font-size: 12px;
    color: #979ba5;
    background: #f5f7fa;
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
</style>
