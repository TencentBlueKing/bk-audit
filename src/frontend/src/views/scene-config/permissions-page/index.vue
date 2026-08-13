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
  <div class="permissions-page">
    <div class="permissions-page-container">
      <!-- 左侧插图 -->
      <div class="landing-illustration">
        <img
          alt=""
          :src="landingImg">
      </div>
      <!-- 右侧内容 -->
      <div class="landing-right">
        <h1 class="landing-title">
          {{ t('暂无场景访问权限') }}
        </h1>

        <!-- 场景列表卡片 -->
        <div class="landing-content">
          <div class="section-header">
            <span>{{ t('你暂无该场景权限，可申请查看权限或管理权限') }}</span>
          </div>

          <div
            class="scene-list">
            <div
              v-for="item in sceneList"
              :key="item.scene_id"
              class="scene-item">
              <div class="scene-info">
                <div class="scene-name-row">
                  <span class="scene-name">{{ item.name }}({{ item.scene_id }})</span>
                  <template v-if="(item.managers || []).length > 0">
                    <audit-icon
                      class="admin-icon"
                      type="user" />
                    <span class="admin-name">
                      {{ (item.managers || []).slice(0, 3).join(' , ') }}
                    </span>
                    <span
                      v-if="(item.managers || []).length > 3"
                      v-bk-tooltips="{
                        content: (item.managers || []).slice(3).join(' , '),
                        placement: 'top',
                      }"
                      class="admin-more">
                      +{{ (item.managers || []).length - 3 }}
                    </span>
                  </template>
                </div>
                <div class="scene-desc">
                  {{ item.description || t('暂无描述') }}
                </div>
              </div>
              <div
                v-if="item.applyStatus === 'applying'"
                class="scene-action">
                <span class="status-applying">
                  <audit-icon
                    class="status-icon rotate-loading"
                    svg
                    type="loading" />
                  {{ t('申请中...') }}
                </span>
                <a
                  v-if="item.ticketUrl"
                  class="itsm-link"
                  :href="item.ticketUrl"
                  rel="noopener noreferrer"
                  target="_blank"
                  @click.stop>
                  {{ t('查看 ITSM 单据') }}
                  <audit-icon
                    class="link-icon"
                    type="jump-link" />
                </a>
              </div>
              <div
                v-else-if="item.applyStatus === 'rejected'"
                class="scene-action">
                <bk-popover
                  placement="top"
                  theme="dark"
                  trigger="hover">
                  <span class="status-rejected">
                    <audit-icon
                      class="status-icon"
                      type="delete-fill" />
                    <span class="status-text">{{ t('已拒绝') }}</span>
                  </span>
                  <template #content>
                    <div class="status-tip">
                      <div class="status-tip-reason">
                        {{ item.rejectReason || t('暂无') }}
                      </div>
                      <a
                        v-if="item.ticketUrl"
                        class="itsm-link"
                        :href="item.ticketUrl"
                        rel="noopener noreferrer"
                        target="_blank"
                        @click.stop>
                        {{ t('查看 ITSM 单据') }}
                        <audit-icon
                          class="link-icon"
                          type="jump-link" />
                      </a>
                    </div>
                  </template>
                </bk-popover>
                <bk-button
                  v-if="!isReapplying"
                  class="apply-btn"
                  @click="handleReapply">
                  {{ t('重新申请') }}
                </bk-button>
              </div>
              <div
                v-else-if="item.applyStatus === 'passed'"
                class="scene-action">
                <bk-popover
                  placement="top"
                  theme="dark"
                  trigger="hover">
                  <span class="status-passed">
                    <audit-icon
                      class="status-icon"
                      type="completed" />
                    <span class="status-text">{{ t('已通过') }}</span>
                  </span>
                  <template #content>
                    <div class="status-tip">
                      <a
                        v-if="item.ticketUrl"
                        class="itsm-link"
                        :href="item.ticketUrl"
                        rel="noopener noreferrer"
                        target="_blank"
                        @click.stop>
                        {{ t('查看 ITSM 单据') }}
                        <audit-icon
                          class="link-icon"
                          type="jump-link" />
                      </a>
                      <span
                        v-else
                        class="status-tip-reason">
                        {{ t('暂无') }}
                      </span>
                    </div>
                  </template>
                </bk-popover>
                <bk-button
                  class="enter-btn"
                  theme="primary"
                  @click="handleEnterScene(item)">
                  {{ t('进入场景配置') }}
                </bk-button>
              </div>
            </div>
          </div>

          <template v-if="showApplyForm">
            <!-- 选择申请权限 -->
            <div class="apply-section">
              <div class="apply-label">
                {{ t('选择申请权限') }}
              </div>
              <div class="permission-options">
                <div
                  class="option-card"
                  :class="{ active: selectedPerm === 'user' }"
                  @click="selectedPerm = 'user'">
                  <audit-icon type="user" />
                  {{ t('使用者') }}
                </div>
                <div
                  class="option-card"
                  :class="{ active: selectedPerm === 'manager' }"
                  @click="selectedPerm = 'manager'">
                  <audit-icon type="insert" />
                  {{ t('管理者') }}
                </div>
              </div>
              <div class="perm-hint">
                <audit-icon
                  class="info-fill"
                  type="info-fill" />
                <span>{{ permHintText }}</span>
              </div>
            </div>

            <!-- 申请理由 -->
            <bk-form
              :key="applyFormKey"
              ref="applyFormRef"
              class="reason-section"
              form-type="vertical"
              :model="applyForm"
              :rules="applyFormRules">
              <bk-form-item
                :label="t('申请理由')"
                property="reason"
                required>
                <bk-input
                  v-model="applyForm.reason"
                  :maxlength="100"
                  :placeholder="t('请输入')"
                  :rows="3"
                  show-word-limit
                  type="textarea" />
              </bk-form-item>
            </bk-form>

            <!-- 申请按钮 -->
            <bk-button
              class="submit-btn"
              :loading="isSubmitting"
              theme="primary"
              @click="handleApply">
              {{ t('申请权限') }}
            </bk-button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import ScenePermissionApplicationService from '@service/scene-permission-application';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import landingImg from '@/images/landing.png';

  type ApplyStatus = 'idle' | 'applying' | 'rejected' | 'passed';

  interface SceneItem {
    scene_id: number;
    name: string;
    description?: string;
    managers: string[];
    applyStatus: ApplyStatus;
    ticketUrl?: string;
    rejectReason?: string;
  }

  /** 审批中状态 */
  const APPLYING_STATUS = ['pending', 'running', 'processing', 'approving', 'applying'];
  /** 已拒绝状态 */
  const REJECTED_STATUS = ['rejected', 'refused', 'failed'];
  /** 已通过状态 */
  const PASSED_STATUS = ['approved', 'passed', 'success', 'finished', 'granted', 'done', 'completed'];
  /** 申请列表轮询间隔 */
  const POLL_INTERVAL = 5000;

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const sceneList = ref<SceneItem[]>([]);
  const route = useRoute();
  const router = useRouter();
  const selectedPerm = ref<'user' | 'manager'>('user');
  const isReapplying = ref(false);
  const applyFormRef = ref();
  const applyFormKey = ref(0);
  const applyForm = reactive({
    reason: '',
  });
  const applyFormRules = {
    reason: [
      {
        validator: (value: string) => Boolean(value?.trim()),
        message: t('申请理由不能为空'),
        trigger: 'change',
      },
    ],
  };

  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  const currentScene = computed(() => sceneList.value[0] || null);

  const isApplyingStatus = computed(() => currentScene.value?.applyStatus === 'applying');
  const isRejectedStatus = computed(() => currentScene.value?.applyStatus === 'rejected');
  const isPassedStatus = computed(() => currentScene.value?.applyStatus === 'passed');

  const showApplyForm = computed(() => {
    if (isApplyingStatus.value || isPassedStatus.value) return false;
    if (isRejectedStatus.value) return isReapplying.value;
    return true;
  });

  const permHintText = computed(() => {
    if (selectedPerm.value === 'user') {
      return t('可使用场景内的风险、报表及工具，并通过检索功能查询系统操作数据');
    }
    return t('在使用者权限基础上，额外可管理审计策略、新增报表、创建工具等配置能力');
  });

  const mapApplyStatus = (
    status = '',
    statusDisplay = '',
    permission?: { view_scene?: boolean; manage_scene?: boolean },
  ): ApplyStatus => {
    const normalized = status.toLowerCase();
    if (APPLYING_STATUS.includes(normalized) || statusDisplay.includes('申请中') || statusDisplay.includes('审批中')) {
      return 'applying';
    }
    if (REJECTED_STATUS.includes(normalized) || statusDisplay.includes('拒绝')) {
      return 'rejected';
    }
    if (
      PASSED_STATUS.includes(normalized)
      || statusDisplay.includes('通过')
      || statusDisplay.includes('成功')
      || permission?.view_scene
      || permission?.manage_scene
    ) {
      return 'passed';
    }
    return 'idle';
  };

  const getFetchParams = () => {
    const sceneId = route.query.scene_id;
    return {
      page: 1,
      page_size: 1000,
      ...(sceneId ? { scene_id: sceneId as string } : {}),
    };
  };

  const stopPolling = () => {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  };

  const startPolling = () => {
    stopPolling();
    pollTimer = setTimeout(() => {
      fetchMineApplicationList(getFetchParams());
    }, POLL_INTERVAL);
  };

  const {
    run: fetchMineApplicationList,
  } = useRequest(ScenePermissionApplicationService.fetchMineList, {
    defaultValue: {
      page: 1,
      num_pages: 0,
      total: 0,
      results: [],
    },
    onSuccess: (data) => {
      const results = data.results || [];
      sceneList.value = results.map(item => ({
        scene_id: item.scene_id,
        name: item.scene_name,
        description: item.description,
        managers: item.scene_managers || [],
        applyStatus: mapApplyStatus(
          item.application?.status,
          item.application?.status_display,
          item.permission,
        ),
        ticketUrl: item.application?.itsm_ticket_url,
        rejectReason: item.application?.reject_reason,
      }));
      if (sceneList.value[0]?.applyStatus !== 'rejected') {
        isReapplying.value = false;
      }

      if (sceneList.value.some(item => item.applyStatus === 'applying')) {
        startPolling();
      } else {
        stopPolling();
      }
    },
  });

  const {
    loading: isSubmitting,
    run: submitApply,
  } = useRequest(ScenePermissionApplicationService.apply, {
    defaultValue: null,
    manual: false,
    onSuccess: () => {
      const scene = currentScene.value;
      if (scene) {
        messageSuccess(`${t('已发起')}「${scene.name}」${t('场景权限 ITSM 单据申请')}`);
      }
      applyForm.reason = '';
      applyFormKey.value += 1;
      isReapplying.value = false;
      nextTick(() => {
        applyFormRef.value?.clearValidate();
      });
      fetchMineApplicationList(getFetchParams());
    },
  });

  const handleReapply = () => {
    isReapplying.value = true;
    applyForm.reason = '';
    applyFormKey.value += 1;
    nextTick(() => {
      applyFormRef.value?.clearValidate();
    });
  };

  const handleEnterScene = (item: SceneItem) => {
    const sceneId = String(item.scene_id);
    router.push({
      name: 'sceneInfo',
      query: {
        scene_id: sceneId,
        scope_id: sceneId,
        scope_type: 'scene',
      },
    });
  };

  const handleApply = () => {
    if (!currentScene.value || isSubmitting.value) return;
    applyFormRef.value?.validate().then(() => {
      submitApply({
        scene_id: currentScene.value!.scene_id,
        role: selectedPerm.value,
        reason: applyForm.reason.trim(),
      });
    });
  };

  onMounted(() => {
    if (route.query.scene_id) {
      fetchMineApplicationList(getFetchParams());
    }
  });

  onUnmounted(() => {
    stopPolling();
  });

</script>

<style scoped lang="postcss">
.permissions-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 104px);
  padding: 56px 40px;
  background: linear-gradient(180deg, #f5f7fa 0%, #fafbfd 100%);
}

.permissions-page-container {
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
  background: #f5f7fa;
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

  .admin-more {
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
    text-decoration: underline;
    text-decoration-style: dashed;
    text-underline-offset: 2px;
    cursor: pointer;
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

.scene-action {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 16px;
}

.apply-btn {
  min-width: 64px;
  height: 26px;
  padding: 0 16px;
  font-size: 14px;
  line-height: 24px;
  color: #63656e;
  background: #fff;
  border-color: #c4c6cc;
  border-radius: 2px;
}

.enter-btn {
  min-width: 64px;
  height: 26px;
  padding: 0 16px;
  font-size: 14px;
  line-height: 24px;
  border-radius: 2px;
}

.status-applying,
.status-rejected,
.status-passed {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 20px;
  cursor: default;

  .status-icon {
    font-size: 14px;
  }
}

.status-applying {
  color: #3a84ff;
}

.status-rejected {
  color: #63656e;
  cursor: pointer;

  .status-icon {
    font-size: 14px;
    color: #ea3636;

    :deep(svg),
    :deep(svg path) {
      fill: #ea3636;
    }
  }

  .status-text {
    text-decoration: underline;
    text-decoration-style: dashed;
    text-underline-offset: 3px;
    text-decoration-color: #c4c6cc;
  }
}

.status-passed {
  color: #63656e;
  cursor: pointer;

  .status-icon {
    color: #2dcb56;

    :deep(svg),
    :deep(svg path) {
      fill: #2dcb56;
    }
  }

  .status-text {
    text-decoration: underline;
    text-decoration-style: dashed;
    text-underline-offset: 3px;
    text-decoration-color: #c4c6cc;
  }
}

.itsm-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  line-height: 20px;
  color: #3a84ff;
  text-decoration: none;
  cursor: pointer;

  &:hover {
    color: #699df4;
  }

  .link-icon {
    font-size: 12px;
  }
}

.status-tip {
  max-width: 240px;
  padding: 4px 0;

  .status-tip-reason {
    margin-bottom: 8px;
    font-size: 12px;
    line-height: 20px;
    color: #fff;
    word-break: break-all;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .itsm-link {
    color: #699df4;

    &:hover {
      color: #a3c5fd;
    }
  }
}

.rotate-loading {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

/* 申请权限区域 */
.apply-section {
  margin-top: 20px;
}

.reason-section {
  margin-top: 16px;

  :deep(.bk-form-item) {
    margin-bottom: 0;
  }
}

.apply-label {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #21293b;
}

.permission-options {
  display: flex;
  gap: 12px;

  .option-card {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    font-size: 14px;
    color: #63656e;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    transition: all .2s;

    &:hover {
      color: #3a84ff;
      border-color: #3b7eff;
    }

    &.active {
      color: #3a84ff;
      background-color: #ecf2fe;
      border-color: #3b7eff;
    }
  }
}

.perm-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.5;
  color: #63656e;

  .hint-icon {
    flex-shrink: 0;
    font-size: 15px;
    color: #ff9c01;
  }
}

.submit-btn {
  margin-top: 24px;
}
</style>
