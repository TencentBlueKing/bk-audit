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
  <div class="log-create-wrapper">
    <div class="log-create-header">
      <div class="log-create-header-title">
        新建数据上报
      </div>
      <div class="log-create-header-line" />
      <div class="log-create-header-desc">
        基于权限模型或数据接入数据，可上传或数据至审计中心，以供后续分析与风险追踪；因不同方式流程有差异，请先选择上报方式
      </div>
    </div>

    <audit-form
      class="log-form"
      :data="formData">
      <bk-form-item :label="t('是否已有日志数据')">
        <bk-radio-group v-model="formData.reportMethod">
          <bk-radio
            v-for="item in reportMethodRadioList
              .filter(item => showBkbase.enabled || item.id !== 'bkbase')"
            :key="item.id"
            :label="item.id">
            {{ t(item.name) }}
          </bk-radio>
        </bk-radio-group>
      </bk-form-item>

      <template v-if="formData.reportMethod === 'newlog'">
        <bk-form-item
          :label="t('数据上报方式')">
          <bk-loading :loading="loading">
            <bk-radio-group v-model="formData.logType">
              <bk-radio-button label="collector">
                {{ t('日志采集接入') }}
                <span class="recommend-text">{{ t('推荐') }}</span>
              </bk-radio-button>
              <bk-radio-button
                v-bk-tooltips="{
                  content: t('仅可创建一个'),
                  disabled: !data.enabled
                }"
                :disabled="data.enabled"
                label="apiPush">
                {{ t('API PUSH 接入') }}
              </bk-radio-button>
            </bk-radio-group>
          </bk-loading>
        </bk-form-item>

        <bk-form-item>
          <div class="log-create-guide">
            <p class="guide-text">
              <span class="guide-text-icon" />
              {{ guideInfo.p1 }}
            </p>
            <p class="guide-text">
              <span class="guide-text-icon" />
              {{ guideInfo.p2 }}
            </p>
            <div class="guide-steps-wrapper">
              <div class="guide-steps-title">
                <span class="guide-text-icon" />
                <span class="guide-steps-title-text">{{ t('步骤预览') }}</span>
              </div>
              <bk-steps
                class="guide-steps"
                :cur-step="currentStep"
                direction="vertical"
                line-type="solid"
                :steps="guideInfo.steps" />
            </div>
          </div>
        </bk-form-item>
      </template>

      <template v-else>
        <bk-form-item>
          <div class="log-create-guide">
            <div class="guide-steps-wrapper">
              <div class="guide-steps-title">
                <span class="guide-steps-title-text">{{ t('步骤预览') }}</span>
              </div>
              <bk-steps
                class="guide-steps"
                :cur-step="currentStep"
                direction="vertical"
                line-type="solid"
                :steps="hasDataSteps" />
            </div>
          </div>
        </bk-form-item>
      </template>
    </audit-form>

    <div class="footer-actions">
      <bk-button
        theme="primary"
        @click="handleNextStep">
        {{ t('下一步') }}
      </bk-button>
      <bk-button
       
        @click="handleCancel" style="margin-left: var(--bk-theme-space-8)">
        {{ t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import useFeature from '@hooks/use-feature';

  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'change', step: number, formData: Record<string, any>): void;
  }

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const { feature: showBkbase } = useFeature('bkbase_data_source');

  const formData = ref({
    logType: 'collector',
    reportMethod: 'newlog',
  });

  const currentStep = ref(-1);
  const reportMethodRadioList = ref([
    {
      id: 'newlog',
      name: t('无，新建日志采集'),
    },
    {
      id: 'bkbase',
      name: t('有，使用计算平台已有数据'),
    },
  ]);

  const guideInfo = computed(() => ({
    p1: formData.value.logType === 'collector' ? t('可创建多个日志采集，所有日志采集将在清洗后合流成一份日志。')
      : t('仅可创建 1 个，获取 Token 和 EndPoint 用于后续 SDK 的日志上报。'),
    p2: formData.value.logType === 'collector' ? t('若您的系统已生成标准化日志文件，建议采用日志采集方式。我们支持通过新建（物理环境、容器环境）或引用计算平台现有数据上传日志。')
      : t('若您的系统需实时上报关键操作，或日志分散在不同模块，建议采用 API 推送方式。我们提供 SDK 和文档，支持日志上报接入。'),
    steps: formData.value.logType === 'collector' ? [
      {
        title: t('记录日志'),
        description: t('根据《审计中心日志标准》规范要求使用 SDK 或 Log 记录日志'),
      },
      {
        title: t('采集配置'),
        description: t('新建后选择物理或容器环境配置相关采集的基础信息与日志过滤'),
      },
      {
        title: t('采集下发'),
        description: t('确认采集目标的采集状态，确认状态成功之后进入下一步'),
      },
      {
        title: t('字段清洗'),
        description: t('根据上报数据，配置字段映射，输出标准化日志'),
      },
      {
        title: t('数据验证'),
        description: t('可选，验证是否上报成功，是否清洗正常等'),
      },
    ] : [
      {
        title: t('获取密钥'),
        description: t('使用获取到的 Token 和 EndPoint'),
      },
      {
        title: t('记录上报'),
        description: t('根据审计要求的标准日志，使用 SDK 或通过 Log 记录日志'),
      },
      {
        title: t('上报日志'),
        description: t('使用 SDK 上报日志'),
      },
    ],
  }));

  const hasDataSteps = [{
    title: t('选择数据'),
    description: t('选择在计算平台已有的数据'),
  }, {
    title: t('字段清洗'),
    description: t('根据上报数据，配置字段映射后生成标准化日志'),
  }, {
    title: t('数据验证'),
    description: t('可选，验证是否上报成功、是否清洗正常等'),
  }];

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
      // 新建日志上报 系统叫systemId 在params中
      system_id: route.params.systemId,
    },
    manual: true,
  });


  const handleNextStep = () => {
    emits('change', 2, formData.value);
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
.log-create-wrapper {
  min-height: calc(100vh - 60px);
  padding: var(--bk-theme-space-16) var(--bk-theme-space-24);
  background: var(--bk-theme-surface-default);
}

.log-create-header {
  display: flex;
  align-items: center;

  .log-create-header-line {
    width: 1px;
    height: 12px;
    margin: 0 var(--bk-theme-space-12);
    background: var(--bk-theme-text-weak);
  }

  .log-create-header-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--bk-theme-text-strong);
  }

  .log-create-header-desc {
    font-size: 12px;
    color: var(--bk-theme-text-weak);
    vertical-align: middle;
  }
}

.log-form {
  margin-top: var(--bk-theme-space-32);

  :deep(.bk-radio-label) {
    font-size: 12px;
  }

  .recommend-text {
    padding: var(--bk-theme-space-2) var(--bk-theme-space-4);
    font-size: 10px;
    color: var(--bk-theme-surface-default);background: var(--bk-theme-color-warn-2);
    border-radius: var(--bk-theme-tag-radius);
  }

  .log-create-guide {
    padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
    background-color: var(--bk-theme-surface-subtle);
    border-radius: var(--bk-theme-tag-radius);

    .guide-text {
      display: flex;
      font-size: 12px;
      line-height: 20px;
      color: var(--bk-theme-text-weak);
      align-items: center;
      gap: var(--bk-theme-space-8);
    }

    .guide-text-icon {
      display: inline-block;
      width: 6px;
      height: 6px;
      background-color: var(--bk-theme-text-weak);
      border-radius: 50%;
    }

    .guide-steps-wrapper {
      display: flex;
      margin-top: var(--bk-theme-space-12);
      gap: var(--bk-theme-space-16);

      .guide-steps-title {
        display: inline-block;
        width: 68px;
        font-size: 12px;
        line-height: 20px;
        color: var(--bk-theme-text-default);

        .guide-steps-title-text {
          margin-left: var(--bk-theme-space-8);
        }
      }

      .guide-steps {
        :deep(.bk-step) {
          padding-left: 0;

          &::before {
            display: none;
          }

          &:last-child {
            .bk-step-description {
              padding-bottom: 0;
            }
          }
        }

        :deep(.bk-step-title) {
          font-size: 14px;
          line-height: 22px;
          color: var(--bk-theme-text-default);
        }

        :deep(.bk-step-description) {
          max-width: 400px;
          padding-bottom: var(--bk-theme-space-24);
          margin-top: var(--bk-theme-space-6);
          font-size: 12px;
          line-height: 16px;
          color: var(--bk-theme-text-weak);
        }
      }
    }
  }
}

.footer-actions {
  display: flex;
  margin-top: var(--bk-theme-space-32);
  gap: var(--bk-theme-space-8);
}
</style>
