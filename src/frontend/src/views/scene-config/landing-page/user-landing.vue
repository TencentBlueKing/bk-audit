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
          {{ t('你还没有场景配置权限') }}
        </h1>
        <p class="landing-subtitle">
          {{ t('场景配置用于管理审计策略、报表、工具、处理规则等审计核心能力') }}
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
          <template v-if="sceneList.length > 0">
            <div class="section-header">
              <span>{{ t('你可申请') }}</span>
              <span class="scene-count">{{ sceneList.length }}</span>
              <span>{{ t('个场景的配置权限') }}</span>
            </div>

            <div class="scene-list">
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

                <div class="scene-action">
                  <!-- 申请中 -->
                  <template v-if="getApplyStatus(item.scene_id) === 'applying'">
                    <span class="status-applying">
                      <audit-icon
                        class="status-icon rotate-loading"
                        svg
                        type="loading" />
                      {{ t('申请中...') }}
                    </span>
                    <a
                      v-if="getTicketUrl(item.scene_id)"
                      class="itsm-link"
                      :href="getTicketUrl(item.scene_id)"
                      rel="noopener noreferrer"
                      target="_blank"
                      @click.stop>
                      {{ t('查看 ITSM 单据') }}
                      <audit-icon
                        class="link-icon"
                        type="jump-link" />
                    </a>
                  </template>

                  <!-- 已拒绝 -->
                  <template v-else-if="getApplyStatus(item.scene_id) === 'rejected'">
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
                            {{ getRejectReason(item.scene_id) }}
                          </div>
                          <a
                            v-if="getTicketUrl(item.scene_id)"
                            class="itsm-link"
                            :href="getTicketUrl(item.scene_id)"
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
                      class="apply-btn"
                      @click="openApplyDialog(item)">
                      {{ t('重新申请') }}
                    </bk-button>
                  </template>

                  <!-- 已通过 -->
                  <template v-else-if="getApplyStatus(item.scene_id) === 'passed'">
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
                            v-if="getTicketUrl(item.scene_id)"
                            class="itsm-link"
                            :href="getTicketUrl(item.scene_id)"
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
                  </template>

                  <!-- 默认：申请 -->
                  <bk-button
                    v-else
                    class="apply-btn"
                    @click="openApplyDialog(item)">
                    {{ t('申请') }}
                  </bk-button>
                </div>
              </div>
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
                  iegsec_helper（{{ t('IEG安全助手') }}）
                </span>
                {{ t('申请创建审计场景') }}
              </div>
            </div>
          </template>

          <!-- 无场景时的引导空态 -->
          <template v-else>
            <div class="section">
              <div class="section-title">
                {{ t('场景配置可以实现:') }}
              </div>
              <ul class="feature-list">
                <li>{{ t('配置审计策略，自动发现业务中的安全风险') }}</li>
                <li>{{ t('自定义报表和工具，满足您的分析需求') }}</li>
              </ul>
              <div
                class="action-row"
                @click="handleLearnMore">
                <span class="link-text">
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
                  iegsc_helper（{{ t('IEG安全助手') }}）
                </span>
                {{ t('申请创建审计场景') }}
              </p>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- 申请弹窗 -->
    <bk-dialog
      v-model:is-show="showApplyDialog"
      :quick-close="false"
      :title="t('申请场景配置权限')"
      :width="480"
      @closed="handleDialogClosed">
      <bk-form
        ref="applyFormRef"
        class="apply-dialog-body"
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
            :rows="4"
            show-word-limit
            type="textarea" />
        </bk-form-item>
      </bk-form>
      <template #footer>
        <bk-button
          class="mr8"
          :loading="isApplying"
          theme="primary"
          @click="handleConfirmApply">
          {{ t('确定申请') }}
        </bk-button>
        <bk-button
          :disabled="isApplying"
          @click="showApplyDialog = false">
          {{ t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>
  </div>
</template>

<script setup lang="ts">
  import { nextTick, onMounted, onUnmounted, reactive, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { onBeforeRouteLeave, useRouter } from 'vue-router';

  import RootManageService from '@service/root-manage';
  import ScenePermissionApplicationService from '@service/scene-permission-application';

  import ConfigModel from '@model/root/config';
  import type ScenePermissionApplicationModel from '@model/scene/scene-permission-application';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import landingImg from '@/images/landing.png';

  type ApplyStatus = 'idle' | 'applying' | 'rejected' | 'passed';

  interface SceneItem {
    scene_id: number;
    name: string;
    description?: string;
    managers: string[];
  }

  interface ApplyState {
    status: ApplyStatus;
    rejectReason?: string;
    ticketUrl?: string;
  }

  /** 审批中状态 */
  const APPLYING_STATUS = ['pending', 'running', 'processing', 'approving', 'applying'];
  /** 已拒绝状态 */
  const REJECTED_STATUS = ['rejected', 'refused', 'failed'];
  /** 已通过状态（不含 ITSM finished：结束单据可能是拒绝） */
  const PASSED_STATUS = ['approved', 'passed', 'success', 'granted', 'done', 'completed', 'pass'];
  /** 申请列表轮询间隔 */
  const POLL_INTERVAL = 5000;
  /** 当前停留会话标记（刷新保留，路由离开清除） */
  const VISIT_ACTIVE_KEY = 'scene-config-user-landing:visit-active';
  /** 本页提交申请并跟踪的场景（仅这些场景在轮询成功后展示「已通过」） */
  const VISIT_TRACKED_SCENE_IDS_KEY = 'scene-config-user-landing:visit-tracked-scene-ids';

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const router = useRouter();

  const sceneList = ref<SceneItem[]>([]);
  const applyStateMap = reactive<Record<number, ApplyState>>({});

  const showApplyDialog = ref(false);
  const applyFormRef = ref();
  const applyForm = reactive({
    reason: '',
  });
  const applyFormRules = {
    reason: [
      {
        validator: (value: string) => Boolean(value?.trim()),
        message: t('申请理由不能为空'),
        trigger: 'blur',
      },
    ],
  };
  const currentScene = ref<SceneItem | null>(null);

  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  const matchStatus = (
    values: string[],
    status = '',
    statusDisplay = '',
    extraDisplays: string[] = [],
  ) => {
    const normalized = status.toLowerCase();
    if (values.includes(normalized)) return true;
    return extraDisplays.some(text => statusDisplay.includes(text));
  };

  const isPassedApplication = (application?: ScenePermissionApplicationModel['application'] | null) => {
    if (!application) return false;
    return matchStatus(
      PASSED_STATUS,
      application.grant_status || application.status,
      application.grant_status_display || application.status_display,
      ['通过', '成功', '授权'],
    );
  };

  const mapApplyStatus = (
    status = '',
    statusDisplay = '',
    options?: {
      manageScene?: boolean;
      hasPassedApplication?: boolean;
      grantStatus?: string;
      grantStatusDisplay?: string;
    },
  ): ApplyStatus => {
    const grantStatus = options?.grantStatus || '';
    const grantStatusDisplay = options?.grantStatusDisplay || '';
    if (
      matchStatus(REJECTED_STATUS, grantStatus, grantStatusDisplay, ['拒绝', '驳回'])
      || matchStatus(REJECTED_STATUS, status, statusDisplay, ['拒绝', '驳回'])
    ) {
      return 'rejected';
    }
    if (
      matchStatus(APPLYING_STATUS, status, statusDisplay, ['申请中', '审批中'])
      || matchStatus(APPLYING_STATUS, grantStatus, grantStatusDisplay, ['申请中', '审批中'])
    ) {
      return 'applying';
    }
    if (
      options?.manageScene
      || options?.hasPassedApplication
      || matchStatus(PASSED_STATUS, grantStatus, grantStatusDisplay, ['通过', '成功', '授权'])
      || matchStatus(PASSED_STATUS, status, statusDisplay, ['通过', '成功', '授权'])
    ) {
      return 'passed';
    }
    return 'idle';
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
      fetchMineApplicationList({
        page: 1,
        page_size: 1000,
      });
    }, POLL_INTERVAL);
  };

  const readIdSet = (key: string): Set<number> => {
    try {
      const raw = JSON.parse(sessionStorage.getItem(key) || '[]');
      if (!Array.isArray(raw)) return new Set();
      return new Set(raw.map(id => Number(id)).filter(id => Number.isFinite(id)));
    } catch {
      return new Set();
    }
  };

  const persistIdSet = (key: string, ids: Set<number>) => {
    sessionStorage.setItem(key, JSON.stringify([...ids]));
  };

  const readTrackedSceneIds = () => readIdSet(VISIT_TRACKED_SCENE_IDS_KEY);

  const trackSceneId = (sceneId: number | string) => {
    const id = Number(sceneId);
    if (!Number.isFinite(id)) return;
    const ids = readTrackedSceneIds();
    ids.add(id);
    persistIdSet(VISIT_TRACKED_SCENE_IDS_KEY, ids);
  };

  /** 路由进入（非刷新）时清空上一轮跟踪，避免直链进来展示历史已通过项 */
  const initVisitSession = () => {
    if (sessionStorage.getItem(VISIT_ACTIVE_KEY) === '1') return;
    sessionStorage.removeItem(VISIT_TRACKED_SCENE_IDS_KEY);
    sessionStorage.setItem(VISIT_ACTIVE_KEY, '1');
  };

  const clearVisitSession = () => {
    sessionStorage.removeItem(VISIT_ACTIVE_KEY);
    sessionStorage.removeItem(VISIT_TRACKED_SCENE_IDS_KEY);
  };

  const resolveItemStatus = (item: ScenePermissionApplicationModel): ApplyStatus => {
    const { application } = item;
    const resolvedStatus = mapApplyStatus(
      application?.status,
      application?.status_display,
      {
        manageScene: Boolean(item.permission?.manage_scene),
        hasPassedApplication: isPassedApplication(application),
        grantStatus: application?.grant_status,
        grantStatusDisplay: application?.grant_status_display,
      },
    );
    // 仅有使用权限、无管理权限时：忽略历史「已通过」记录，仍展示申请按钮；
    // 申请中 / 已拒绝 保留真实状态展示。
    if (
      item.permission?.view_scene
      && !item.permission?.manage_scene
      && resolvedStatus === 'passed'
    ) {
      return 'idle';
    }
    return resolvedStatus;
  };

  const applyApplicationList = (list: ScenePermissionApplicationModel[]) => {
    const trackedIds = readTrackedSceneIds();

    // 已通过：仅本页提交申请后，轮询从「申请中」变为成功时展示
    const filtered = list.filter((item) => {
      const sceneId = Number(item.scene_id);
      const status = resolveItemStatus(item);
      if (status === 'passed') {
        return trackedIds.has(sceneId);
      }
      return Boolean(item.permission?.view_scene && !item.permission?.manage_scene);
    });

    sceneList.value = filtered.map(item => ({
      scene_id: item.scene_id,
      name: item.scene_name,
      managers: item.scene_managers || [],
      description: item.description,
    }));

    Object.keys(applyStateMap).forEach((key) => {
      delete applyStateMap[Number(key)];
    });
    filtered.forEach((item) => {
      const { application } = item;
      applyStateMap[item.scene_id] = {
        status: resolveItemStatus(item),
        rejectReason: application?.reject_reason,
        ticketUrl: application?.itsm_ticket_url,
      };
    });

    const hasApplying = filtered.some((item) => {
      const status = applyStateMap[item.scene_id]?.status;
      return status === 'applying';
    });
    if (hasApplying) {
      startPolling();
    } else {
      stopPolling();
    }
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
      applyApplicationList(data.results || []);
    },
  });

  const {
    loading: isApplying,
    run: submitApply,
  } = useRequest(ScenePermissionApplicationService.apply, {
    defaultValue: null,
    manual: false,
    onSuccess: () => {
      const scene = currentScene.value;
      if (scene) {
        trackSceneId(scene.scene_id);
        messageSuccess(`${t('已发起')}「${scene.name}」${t('场景配置权限 ITSM 单据申请')}`);
      }
      showApplyDialog.value = false;
      handleDialogClosed();
      fetchMineApplicationList({
        page: 1,
        page_size: 1000,
      });
    },
  });

  const getApplyState = (sceneId: number): ApplyState => (
    applyStateMap[sceneId] || { status: 'idle' }
  );

  const getApplyStatus = (sceneId: number) => getApplyState(sceneId).status;

  const getTicketUrl = (sceneId: number) => getApplyState(sceneId).ticketUrl || '';

  const getRejectReason = (sceneId: number) => (
    getApplyState(sceneId).rejectReason || t('暂无')
  );

  const openApplyDialog = (item: SceneItem) => {
    currentScene.value = item;
    applyForm.reason = '';
    showApplyDialog.value = true;
    nextTick(() => {
      applyFormRef.value?.clearValidate();
    });
  };

  const handleDialogClosed = () => {
    applyForm.reason = '';
    currentScene.value = null;
    nextTick(() => {
      applyFormRef.value?.clearValidate();
    });
  };

  const handleConfirmApply = () => {
    if (!currentScene.value || isApplying.value) return;
    applyFormRef.value?.validate().then(() => {
      const scene = currentScene.value!;
      trackSceneId(scene.scene_id);
      submitApply({
        scene_id: scene.scene_id,
        role: 'manager',
        reason: applyForm.reason.trim(),
      });
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

  onMounted(() => {
    initVisitSession();
    fetchMineApplicationList({
      page: 1,
      page_size: 1000,
    });
  });

  onUnmounted(() => {
    stopPolling();
  });

  onBeforeRouteLeave((to) => {
    if (to.name === 'userLandingPage') return;
    clearVisitSession();
  });

  const handleLearnMore = () => {
    window.open(configData.value.third_doc_url.scene_iwiki_url, '_blank');
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
  font-size: 14px;
  line-height: 22px;
  color: #63656e;
  align-items: center;
  gap: 4px;

  .scene-count {
    font-weight: 700;
    color: #3a84ff;
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
  min-height: 64px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  transition: background-color .2s;
  align-items: center;
  justify-content: space-between;
  gap: 16px;

  &:hover {
    background: #f0f1f5;
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
  flex-wrap: wrap;

  .scene-name {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .admin-icon {
    font-size: 14px;
    color: #a3c5fd;
  }

  .admin-name {
    font-size: 12px;
    line-height: 20px;
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
  overflow: hidden;
  font-size: 12px;
  line-height: 20px;
  color: #979ba5;
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

.apply-dialog-body {
  margin-bottom: 0;
}

.mr8 {
  margin-right: 8px;
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

.list-empty {
  padding: 32px 0 16px;
  font-size: 13px;
  color: #979ba5;
  text-align: center;
}

/* 无场景时的引导样式，与 index.vue 保持一致 */
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
    color: #3b7eff;
  }
}

.permission-desc {
  margin: 0 0 10px;
  font-size: 15px;
  line-height: 1.75;
  color: #63656e;

  span {
    color: #3b7eff;
    white-space: nowrap;
    cursor: pointer;

    .qw-icon {
      display: inline-block;
      width: 18px;
      height: 18px;
      vertical-align: text-bottom;
    }
  }
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
  font-size: 13px;
  line-height: 1.65;
  color: #63656e;

  .contact-link {
    color: #3b7eff;
    white-space: nowrap;
    cursor: pointer;

    .qw-icon {
      display: inline-block;
      width: 17px;
      height: 17px;
      vertical-align: text-bottom;
    }
  }
}
</style>
