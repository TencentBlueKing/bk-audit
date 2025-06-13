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
  <div class="step">
    <div class="step-head">
      <div
        class="head-left"
        @click="handlerBack">
        <audit-icon
          class="back-icon"
          type="back" />
        <span class="back-icon-text">{{ t("接入新系统") }}</span>
      </div>

      <div class="cur-step">
        <bk-steps
          :cur-step="curStep"
          size="small"
          :steps="stepsTitle" />
      </div>

      <div class="head-right">
        <audit-icon
          class="help-fill-icon"
          type="help-fill" />
        <span class="head-right-text">{{ t("系统接入指引") }}</span>
      </div>
    </div>

    <div class="step-content">
      <component
        :is="stepComponents(curStep)"
        ref="stepRef"
        @handler-validates="handlerValidates" />
    </div>

    <div class="step-footer">
      <div class="footer-btn">
        <div v-if=" Number(curStep) === 1">
          <bk-button
            theme="primary"
            @click="handlerStep1Submit">
            {{ t("提交并下一步") }}
          </bk-button>
          <bk-button
            class="ml10"
            @click="handlerCancel">
            {{ t("取消") }}
          </bk-button>
        </div>
        <div v-if=" Number(curStep) === 3">
          <bk-button
            @click="handlerStep3Cancel">
            {{ t("上一步") }}
          </bk-button>
          <bk-button
            class="ml10"
            theme="primary"

            @click="handlerStep3Submit">
            {{ t("完成并下一步") }}
          </bk-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="tsx">
  import { InfoBox } from 'bkui-vue';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import Step1 from './step1/index.vue';
  import Step2 from './step2/index.vue';
  import Step3 from './step3/index.vue';
  import Step4 from './step4/index.vue';

  import useRequest from '@/hooks/use-request';

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();

  // 将 curStep 定义为计算属性，确保始终返回数字类型
  const curStep = computed<number>(() => {
    const step = Number(route.query.step);
    return isNaN(step) ? 1 : step;
  });

  const stepRef = ref();

  const stepsTitle = ref([
    {
      title: t('注册系统信息'),
    },
    {
      title: t('注册权限模型'),
    },
    {
      title: t('上报日志数据'),
    },
  ]);

  // 创建系统
  const {
    run: fetchSystemCreated,
  } = useRequest(MetaManageService.fetchSystemCreated, {
    defaultValue: [],
    onSuccess: (data) => {
      router.replace({
        query: {
          ...route.query,
          step: 1.5,
        },
        params: {
          id: data.system_id,
        },
      });
      // 更新路由参数
      router.replace({
        query: {
          ...route.query,
          step: 1.5,
        },
        params: {
          id: data.system_id,
        },
      });
    },
  });
  const stepComponents = (step: number | string) => {
    const steps = [Step1, Step2, Step3, Step4];
    // 确保step在1-4范围内，超出则返回最后一个组件
    const numStep = typeof step === 'string' ? Number(step) : step;
    const index = Math.min(Math.max(Math.floor(numStep), 1), steps.length) - 1;
    return steps[index];
  };

  // step 提交
  const handlerStep1Submit = () => {
    stepRef.value.handlerFormData();
  };
  interface FormData {
    name: string;
    instance_id: string;
    [key: string]: any;
  }

  const handlerValidates: (...args: unknown[]) => void = (data: unknown) => {
    if (typeof data !== 'object' || data === null) return;
    const formData = data as FormData;
    InfoBox({
      type: 'warning',
      title: t('确认接入该系统?'),
      contentAlign: 'left',
      content: (
        <div>
          <div>
            <span>{t('系统')}：</span>
            <span style="color: #313238;">{`${formData.name}(${formData.instance_id})`}</span>
          </div>
          <div style="background: #F5F6FA; border-radius: 2px;padding:16px;margin-top: 10px;font-size: 12px;color: #4D4F56;line-height: 22px;letter-spacing: 0;">
            {t('当前系统为从“审计中心”接入，在审计中心所做的变更将会完全同步至权限中心，请确认后操作')}
          </div>
        </div>
      ),
      cancelText: t('取消'),
      confirmText: t('确定接入'),
      onConfirm() {
        fetchSystemCreated(formData);
      },
      onCancel() {},
    });
  };
  const handlerStep3Cancel = () => {
    router.replace({
      query: {
        ...route.query,
        step: 1,
      },
    });
  };
  const handlerStep3Submit = () => {
    router.replace({
      query: {
        ...route.query,
        step: 4,
      },
    });
  };
  // 取消
  const handlerCancel = () => {
    InfoBox({
      title: t('确认取消当前操作?'),
      content: t('已填写的内容将会丢失，请谨慎操作！'),
      cancelText: t('留着当前页'),
      confirmText: t('确认取消'),
      onConfirm() {
        console.log('删除成功');
      },
      onCancel() {
        console.log('删除失败');
      },
    });
  };
  const handlerBack = () => {
    router.push({
      name: 'systemAccess',
    });
  };
</script>

<style scoped lang="postcss">
.step {
  position: relative;
  width: 100vw;
  height: 100vh;

  /* max-height: 85vh; */
  overflow: auto;
  background-color: #f5f7fa;

  .step-head {
    position: relative;
    width: 100%;
    height: 52px;
    background-color: #fff;
    box-shadow: 0 3px 4px 0 #0000000a;

    .head-left {
      position: absolute;
      display: flex;
      height: 100%;
      margin-left: 25px;
      align-items: center;

      .back-icon {
        font-size: 16px;
        color: #3a84ff;
        cursor: pointer;
      }

      .back-icon-text {
        margin-left: 5px;
        font-size: 16px;
        letter-spacing: 0;
        color: #313238;
      }
    }

    .cur-step {
      position: absolute;
      top: 50%;
      left: 50%;
      width: 40%;
      transform: translate(-50%,-50%  );
    }

    .head-right {
      position: absolute;
      top: 50%;
      right: 30px;
      cursor: pointer;
      transform: translateY(-50%);

      .help-fill-icon {
        font-size: 16px;
        color: #3a84ff;
      }

      .head-right-text {
        margin-left: 5px;
        font-size: 14px;
        color: #3a84ff;
      }
    }
  }

  .step-footer {
    position: fixed;
    bottom: 0;
    width: 100vw;
    height: 48px;
    background: #fff;
    border: 1px solid #dcdee5;

    .footer-btn {
      position: absolute;
      top: 50%;
      left: 20%;
      transform: translateY(-50%);

      .ml10 {
        margin-left: 10px;
      }
    }
  }
}
</style>
