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
              </div>
            </div>
          </div>

          <!-- 选择申请权限 -->
          <div class="apply-section">
            <div class="apply-label">
              {{ t('选择申请权限') }}
            </div>
            <div class="permission-options">
              <div
                class="option-card"
                :class="{ active: selectedPerm === 'viewer' }"
                @click="selectedPerm = 'viewer'">
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
          <div class="reason-section">
            <div class="apply-label">
              {{ t('申请理由') }}
            </div>
            <bk-input
              v-model="applyReason"
              :placeholder="t('请输入')"
              :rows="3"
              type="textarea" />
          </div>

          <!-- 申请按钮 -->
          <bk-button
            class="submit-btn"
            theme="primary"
            @click="handleApply">
            {{ t('申请权限') }}
          </bk-button>
        </div>
      </div>
    </div>

    <!-- 申请权限提示弹窗 -->
    <bk-dialog
      v-model:is-show="showApplyDialog"
      theme="primary"
      :title="t('权限申请提示')"
      :width="480">
      <div class="apply-dialog-body">
        <audit-icon
          class="dialog-tip-icon"
          type="info-circle" />
        <p>{{ t('请联系以下管理员添加权限') }}：</p>
        <div class="manager-list">
          <span
            v-for="(name, idx) in currentManagers"
            :key="idx"
            class="manager-tag">{{ name }}</span>
        </div>
      </div>
      <template #footer>
        <bk-button
          theme="primary"
          @click="showApplyDialog = false">
          {{ t('我知道了') }}
        </bk-button>
      </template>
    </bk-dialog>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import SceneManageService from '@service/scene-manage';

  import useRequest from '@hooks/use-request';

  import landingImg from '@/images/landing.png';

  interface SceneItem {
    scene_id: number;
    name: string;
    status: 'enabled' | 'disabled';
    permission: Record<string, boolean>;
    description?: string;
    managers?: string[];
  }

  const { t } = useI18n();

  const sceneList = ref<SceneItem[]>([]);
  const route = useRoute();
  const selectedPerm = ref<'viewer' | 'manager'>('viewer');
  const applyReason = ref('');
  const showApplyDialog = ref(false);

  const currentManagers = computed(() => sceneList.value[0]?.managers || []);

  const permHintText = computed(() => {
    if (selectedPerm.value === 'viewer') {
      return t('可查看场景下的报表与工具，并使用检索功能查询系统操作数据');
    }
    return t('在使用者权限基础上，额外可管理审计策略、新增报表、创建工具等配置能力');
  });

  const {
    run: fetchSceneAll,
  } = useRequest(SceneManageService.fetchSceneAll, {
    defaultValue: [],
    onSuccess: (data) => {
      sceneList.value = data.filter(item => item.scene_id === Number(route.query.scene_id));
    },
  });

  function handleApply() {
    showApplyDialog.value = true;
  }

  onMounted(() => {
    fetchSceneAll({
      page_size: 100,
      status: 'enabled',
    });
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

/* 申请权限区域 */
.apply-section {
  margin-top: 20px;
}

.reason-section {
  margin-top: 16px;
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

/* 申请权限弹窗 */
.apply-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 0;

  .dialog-tip-icon {
    font-size: 32px;
    color: #ff9c01;
  }

  p {
    margin: 0;
    font-size: 14px;
    line-height: 1.6;
    color: #21293b;
  }

  .manager-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px 16px;
    background-color: #f5f7fa;
    border-radius: 4px;
  }

  .manager-tag {
    padding: 4px 12px;
    font-size: 13px;
    color: #3b7eff;
    background-color: #ecf2fe;
    border-radius: 2px;
  }
}
</style>
