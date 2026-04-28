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
  <div class="user-landing">
    <div class="user-landing-container">
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
          {{ t('场景配置用于管理审计策略、报表、工具，处理规则等审计核心能力') }}
          <span
            class="link-text"
            @click="handleLearnMore">
            {{ t('了解更多') }}
            <audit-icon
              class="right-icon"
              type="right" />
          </span>
        </p>

        <!-- 场景列表卡片 -->
        <div class="landing-content">
          <div class="section-header">
            <span>{{ t('你已有') }}</span>
            <span class="scene-count">{{ sceneList.length }}</span>
            <span>{{ t('个场景的使用权限，可为其申请配置权限') }}</span>
            <bk-icon
              class="info-icon"
              type="info-circle" />
          </div>

          <div
            v-if="sceneList.length > 0"
            class="scene-list">
            <div
              v-for="item in sceneList"
              :key="item.scene_id"
              class="scene-item">
              <div class="scene-info">
                <div class="scene-name-row">
                  <span class="scene-name">{{ item.name }}</span>
                  <audit-icon
                    v-if="item.managers && item.managers.length > 0"
                    class="admin-icon"
                    type="person-fill" />
                  <span class="admin-name">{{ item.managers?.[0] || '' }}</span>
                </div>
                <div class="scene-desc">
                  {{ item.description || t('暂无描述') }}
                </div>
                <div
                  v-if="item._applyStatus === 'pending'"
                  class="apply-status">
                  <bk-icon
                    type="time" />
                  {{ t('申请中') }}·{{ t('查看 TSM 审批') }}
                  <span class="apply-count">[{{ item._applyCount || 0 }}]</span>
                </div>
              </div>
            </div>
          </div>
          <div
            v-else
            class="list-empty">
            {{ t('暂无已启用的场景') }}
          </div>

          <!-- 底部申请区域 -->
          <div class="create-section">
            <div class="create-title">
              {{ t('需要创建新的业务场景？') }}
            </div>
            <div class="create-desc">
              {{ t('请通过企业微信联系') }}
              <span
                class="contact-link"
                @click="contactHelper">
                <img
                  alt=""
                  class="qw-icon"
                  src="@/images/qw.svg">
                iegsc_helper（{{ t('IEG安全助手') }}）
              </span>
              {{ t('申请创建审计场景') }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RootManageService from '@service/root-manage';
  import SceneManageService from '@service/scene-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  import landingImg from '@/images/landing.png';

  interface SceneItem {
    uid: string;
    scene_id: number;
    name: string;
    description: string;
    status: string;
    managers: string[];
    users: string[];
    _applyStatus?: string;
    _applyCount?: number;
  }

  const { t } = useI18n();

  const sceneList = ref<SceneItem[]>([]);

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });
  const {
    run: fetchSceneList,
  } = useRequest(SceneManageService.fetchSceneList, {
    defaultValue: { results: [] as any[], page: 0, num_pages: 0, total: 0 },
    onSuccess: (data) => {
      sceneList.value = data.results;
    },
  });

  onMounted(() => {
    fetchSceneList({
      page_size: 100,
      status: 'enabled',
    });
  });

  const handleLearnMore = () => {
    window.open(configData.value.help_info.bkaudit_wiki, '_blank');
  };


  const contactHelper = () => {
    window.open(`wxwork://message?uin=${configData.value.iegsec_helper}`, '_blank');
  };
</script>

<style scoped lang="postcss">
.user-landing {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 104px);
  padding: 56px 40px;
  background: linear-gradient(180deg, #f5f7fa 0%, #fafbfd 100%);
}

.user-landing-container {
  display: flex;
  width: 100%;
  max-width: 1400px;
  gap: 80px;
  align-items: center;
}

.landing-illustration {
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

.landing-title {
  margin: 0 0 12px;
  font-size: 36px;
  font-weight: 700;
  line-height: 1.3;
  color: #21293b;
}

.landing-subtitle {
  margin: 0 0 28px;
  font-size: 14px;
  line-height: 1.6;
  color: #979ba5;
}

.link-text {
  color: #3b7eff;
  cursor: pointer;

  .right-icon {
    font-size: 16px;
    vertical-align: middle;
  }
}

.landing-content {
  padding: 24px 28px 20px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 16px rgb(59 126 255 / 8%);
}

.section-header {
  display: flex;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.5;
  color: #63656e;
  align-items: center;
  gap: 4px;

  .scene-count {
    font-weight: 700;
    color: #21293b;
  }

  .info-icon {
    font-size: 15px;
    color: #ff6ec7;
  }
}

.scene-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 456px;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c4c6cc;
    border-radius: 2px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }
}

.scene-item {
  display: flex;
  padding: 14px 16px;
  background: #fafbfd;
  border-radius: 8px;
  transition: all .2s;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;

  &:hover {
    background: #f5f7fa;
  }
}

.scene-info {
  flex: 1;
  min-width: 0;
}

.scene-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;

  .scene-name {
    font-size: 14px;
    font-weight: 600;
    color: #21293b;
  }

  .admin-icon {
    font-size: 13px;
    color: #3b7eff;
  }

  .admin-name {
    font-size: 12px;
    color: #979ba5;
  }
}

.scene-desc {
  max-width: 420px;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.5;
  color: #c4c6cc;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.apply-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  color: #ff9c01;

  :deep(.bk-icon) {
    font-size: 12px;
  }

  .apply-count {
    color: #3b7eff;
    cursor: pointer;
  }
}

.apply-btn {
  flex-shrink: 0;
  align-self: center;
}

.list-empty {
  padding: 32px 0 16px;
  font-size: 13px;
  color: #979ba5;
  text-align: center;
}

.create-section {
  padding-top: 16px;
  margin-top: 20px;
  border-top: 1px solid #eaebf0;
}

.create-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #21293b;
}

.create-desc {
  display: inline-flex;
  font-size: 13px;
  line-height: 1.65;
  color: #63656e;
  align-items: center;
  flex-wrap: wrap;

  .contact-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: #3b7eff;
    cursor: pointer;
  }

  .qw-icon {
    width: 17px;
    height: 17px;
    flex-shrink: 0;
  }
}
</style>
