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
              <li>{{ t('自定义报表和工具满足您的分析需求') }}</li>
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
                <span class="helper-text">iegsc_helper {{ t('IEG安全助手') }}</span>
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
  import { onMounted } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  import landingImg from '@/images/landing.png?inline';

  const { t } = useI18n();
  const router = useRouter();

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

  onMounted(() => {
    const userRole = JSON.parse(sessionStorage.getItem('userRole') || '[]');
    // 如果是 saas_admin\scene_admin 直接跳转到场景列表页
    if (userRole.includes('saas_admin') || userRole.includes('scene_admin')) {
      router.push({ name: 'sceneInfo' });
      return;
    }
  });
</script>

<style scoped lang="postcss">
.landing-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 104px);
  padding: var(--bk-theme-space-32) var(--bk-theme-space-32);
  background: linear-gradient(180deg, var(--bk-theme-surface-subtle) 0%, var(--bk-theme-table-header-bg) 100%);
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
  padding: 36px 36px var(--bk-theme-space-32);
  background-color: var(--bk-theme-surface-default);
  border-radius: var(--bk-theme-card-radius);
  box-shadow: 0 2px 16px rgb(59 126 255 / 8%);
}

.landing-title {
  margin: 0 0 var(--bk-theme-space-16);
  font-size: 36px;
  font-weight: 700;
  line-height: 1.35;color: var(--bk-theme-text-strong);
}

.landing-subtitle {
  margin: 0 0 var(--bk-theme-space-32);
  font-size: 16px;
  line-height: 1.6;
  color: var(--bk-theme-text-weak);
}

.section {
  margin-bottom: var(--bk-theme-space-32);

  &:last-child {
    margin-bottom: 0;
  }
}

.section-title {
  margin-bottom: var(--bk-theme-space-16);
  font-size: 17px;
  font-weight: 700;
  line-height: 1.5;color: var(--bk-theme-text-strong);
}

.feature-list {
  padding-left: var(--bk-theme-space-16);
  margin: 0 0 var(--bk-theme-space-16);
  list-style: none;

  li {
    position: relative;
    padding-left: var(--bk-theme-space-16);
    margin-bottom: var(--bk-theme-space-12);
    font-size: 15px;
    line-height: 1.65;
    color: var(--bk-theme-text-default);

    &::before {
      position: absolute;
      top: 50%;
      left: 0;
      width: 4px;
      height: 15px;background: var(--bk-theme-color-brand-2);
      border-radius: var(--bk-theme-tag-radius);
      content: '';
      transform: translateY(-50%);
    }

    &:last-child {
      margin-bottom: 0;
    }
  }
}

.action-row {
  display: flex;
  align-items: center;
  gap: var(--bk-theme-space-12);
  flex-wrap: wrap;
  cursor: pointer;

  .right-icon {
    margin-left: -var(--bk-theme-space-12);
    font-size: 24px;color: var(--bk-theme-color-brand-2)}
}

.link-text {
  font-size: 15px;color: var(--bk-theme-color-brand-2);
  cursor: pointer;
}

.permission-desc {
  position: relative;
  display: inline-block;
  font-size: 15px;
  line-height: 1.7;
  color: var(--bk-theme-text-default);

  span {
    display: inline-flex;color: var(--bk-theme-color-brand-2);
    vertical-align: middle;
    cursor: pointer;
    align-items: center;
    gap: var(--bk-theme-space-4);
  }

  .qw-icon {
    width: 18px;
    height: 18px;
    margin-top: -var(--bk-theme-space-4);
  }

  .helper-text {
    margin-top: -var(--bk-theme-space-4);
    vertical-align: middle;
  }
}


</style>
