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
  <div class="landing-page">
    <div class="landing-container">
      <!-- 左侧插图 -->
      <div class="landing-illustration">
        <img
          alt="场景配置"
          :src="landingImg">
      </div>
      <!-- 右侧内容 -->
      <div class="landing-right">
        <h1 class="landing-title">
          {{ t('了解场景配置') }}
        </h1>
        <p class="landing-subtitle">
          {{ t('创建审计场景让审计中心为你的业务提供审计服务') }}
        </p>
        <div class="landing-content">
          <div class="section">
            <div class="section-title">
              {{ t('场景配置可以实现') }}
            </div>
            <ul class="feature-list">
              <li>{{ t('配置审计策略自动发现业务中的安全风险') }}</li>
              <li>{{ t('自定义巡表和工具满足您的分析需求') }}</li>
            </ul>
            <div
              class="action-row"
              @click="handleOpenWiki">
              <span
                class="link-text">
                {{ t('了解更多') }}
              </span>
              <audit-icon
                class="right-icon"
                type="right" />
            </div>
          </div>

          <div class="section">
            <div class="section-title">
              {{ t('怎么申请场景权限?') }}
            </div>
            <p class="permission-desc">
              {{ t('请通过企业微信联系') }}
              <span @click="contactHelper">
                <img
                  class="qw-icon"
                  src="@/images/qw.svg">
                iegsc_helper {{ t('IEG安全助手') }}
              </span>
              {{ t('申请创建审计场景') }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  import landingImg from '@/images/landing.png';

  const { t } = useI18n();

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  const handleOpenWiki = () => {
    window.open(configData.value.third_doc_url.scene_iwiki_url, '_blank');
  };

  const contactHelper = () => {
    window.open(`wxwork://message?uin=${configData.value.iegsec_helper}`, '_blank');
  };
</script>

<style scoped lang="postcss">
.landing-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 104px);
  padding: 60px 40px;
  background: linear-gradient(180deg, #f5f7fa 0%, #fafbfd 100%);
}

.landing-container {
  display: flex;
  width: 100%;
  max-width: 1280px;
  gap: 80px;
  align-items: center;
}

.landing-illustration {
  /* background: linear-gradient(180deg, #f0f6ff 0%, #e8f3fe 100%); */
  display: flex;
  width: 500px;
  height: 500px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;

  img {
    width: 380px;
    height: auto;
    object-fit: contain;
  }
}

.landing-right {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.landing-content {
  padding: 36px 36px 32px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 16px rgb(59 126 255 / 8%);
}

.landing-title {
  margin: 0 0 16px;
  font-size: 36px;
  font-weight: 700;
  line-height: 1.35;
  color: #21293b;
}

.landing-subtitle {
  margin: 0 0 44px;
  font-size: 16px;
  line-height: 1.6;
  color: #979ba5;
}

.section {
  margin-bottom: 36px;

  &:last-child {
    margin-bottom: 0;
  }
}

.section-title {
  margin-bottom: 16px;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.5;
  color: #21293b;
}

.feature-list {
  padding-left: 20px;
  margin: 0 0 20px;
  list-style: none;

  li {
    position: relative;
    padding-left: 18px;
    margin-bottom: 10px;
    font-size: 15px;
    line-height: 1.65;
    color: #63656e;

    &::before {
      position: absolute;
      top: 8px;
      left: 0;
      width: 4px;
      height: 15px;
      background: #3b7eff;
      border-radius: 2px;
      content: '';
    }

    &:last-child {
      margin-bottom: 0;
    }
  }
}

.action-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  cursor: pointer;

  .right-icon {
    margin-left: -10px;
    font-size: 24px;
    color: #3b7eff
  }
}

.link-text {
  font-size: 15px;
  color: #3b7eff;
  cursor: pointer;
}

.permission-desc {
  margin: 0 0 10px;
  font-size: 15px;
  line-height: 1.7;
  color: #63656e;

  span {
    display: inline-flex;
    color: #3b7eff;
    vertical-align: baseline;
    cursor: pointer;
    align-items: center;
    gap: 4px;
  }

  .qw-icon {
    width: 18px;
    height: 18px;
  }
}


</style>
