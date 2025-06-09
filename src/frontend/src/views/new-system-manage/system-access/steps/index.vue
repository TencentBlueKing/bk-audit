<template>
  <div class="step">
    <div class="step-head">
      <div class="head-left">
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
      <component :is="stepComponents[curStep - 1]" />
    </div>

    <div class="step-footer">
      <div class="footer-btn">
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
    </div>
  </div>
</template>

<script setup lang="tsx">
  import { InfoBox } from 'bkui-vue';
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  //   import { useRoute, useRouter } from 'vue-router';
  import Step1 from './step1/index.vue';
  import Step2 from './step2/index.vue';
  import Step3 from './step3/index.vue';

  const { t } = useI18n();
  //   const router = useRouter();
  //   const route = useRoute();
  //   console.log(route, );

  const curStep = ref(1);
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

  const stepComponents = [Step1, Step2, Step3];
  // step 提交
  const handlerStep1Submit = () => {
    InfoBox({
      type: 'warning',
      title: '确认接入该系统?',
      contentAlign: 'left',
      content: (
        <div>
          <div>
            <span>系统：</span>
            <span style="color: #313238;">配置平台（CMDB）</span>
          </div>
          <div style="background: #F5F6FA; border-radius: 2px;padding:16px;margin-top: 10px;font-size: 12px;color: #4D4F56;line-height: 22px;letter-spacing: 0;">
            当前系统为从“审计中心”接入，在审计中心所做的变更将会完全同步至权限中心，请确认后操作
          </div>
        </div>
      ),
      cancelText: '取消',
      confirmText: '确定接入',
      onConfirm() {
        console.log('删除成功');
      },
      onCancel() {
        console.log('删除失败');
      },
    });
  };
  // 取消
  const handlerCancel = () => {
    InfoBox({
      title: '确认取消当前操作?',
      content: '已填写的内容将会丢失，请谨慎操作！',
      cancelText: '留着当前页',
      confirmText: '确认取消',
      onConfirm() {
        console.log('删除成功');
      },
      onCancel() {
        console.log('删除失败');
      },
    });
  };

</script>

<style scoped lang="postcss">
.step {
  position: relative;
  width: 100vw;
  height: 100vh;
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
