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
  <bk-sideslider
    :is-show="isShow"
    :title="sliderTitle"
    :width="640"
    @closed="handleClose">
    <template #header>
      <div class="scene-detail-header">
        <div class="header-left">
          <span class="header-title">{{ t('场景详情') }}</span>
          <span class="header-divider">|</span>
          <span class="header-scene-info">{{ detailData.name }}（{{ detailData.id }}）</span>
        </div>
        <div class="header-right">
          <bk-button
            outline
            theme="primary"
            @click="handleEdit">
            {{ t('编辑') }}
          </bk-button>
          <bk-button
            outline
            @click="handleToggleStatus">
            {{ detailData.status === 'enabled' ? t('停用') : t('启用') }}
          </bk-button>
          <bk-button
            class="mr8"
            outline
            @click="handleDelete">
            {{ t('删除') }}
          </bk-button>
        </div>
      </div>
    </template>
    <template #default>
      <div class="scene-detail-content">
        <!-- 基础信息 -->
        <div class="info-section">
          <div class="section-title">
            {{ t('基础信息') }}
          </div>
          <div class="info-list">
            <div class="info-item">
              <span class="info-label">{{ t('场景 ID') }}：</span>
              <span class="info-value">{{ detailData.id }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ t('场景名称') }}：</span>
              <span class="info-value">
                {{ detailData.name }}
                <audit-icon
                  v-bk-tooltips="t('跳转至场景')"
                  class="ml8 jump-link"
                  type="jump-link"
                  @click="handleJumpToScene" />
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ t('场景描述') }}：</span>
              <span class="info-value">{{ detailData.description || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ t('场景管理员') }}：</span>
              <span class="info-value">{{ formatManagers(detailData.managers) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ t('场景使用者') }}：</span>
              <span class="info-value">{{ formatUsers(detailData.users) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ t('启用状态') }}：</span>
              <span class="info-value">
                <bk-tag :theme="detailData.status === 'enabled' ? 'success' : ''">
                  {{ detailData.status === 'enabled' ? t('启用') : t('停用') }}
                </bk-tag>
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ t('更新人') }}：</span>
              <span class="info-value">{{ detailData.updated_by }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ t('更新时间') }}：</span>
              <span class="info-value">{{ detailData.updated_at }}</span>
            </div>
          </div>
        </div>

        <!-- 关联系统 -->
        <div class="info-section">
          <div class="section-title">
            {{ t('关联系统') }}
            <bk-tag class="count-tag">
              {{ detailData.systems.length }}
            </bk-tag>
          </div>
          <div class="system-list">
            <bk-tag
              v-for="system in detailData.systems"
              :key="system.id"
              class="system-tag">
              {{ system.name }}
            </bk-tag>
          </div>
        </div>

        <!-- 关联数据表 -->
        <div class="info-section">
          <div class="section-title">
            {{ t('关联数据表') }}
            <bk-tag class="count-tag">
              {{ detailData.tables.length }}
            </bk-tag>
          </div>
          <div class="table-list">
            <bk-tag
              v-for="table in detailData.tables"
              :key="table.id"
              class="table-tag">
              {{ table.name }}
            </bk-tag>
          </div>
        </div>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    isShow: boolean;
    sceneId?: string | number;
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'edit', data: DetailData): void;
    (e: 'delete', data: DetailData): void;
    (e: 'toggle-status', data: DetailData): void;
  }

  interface UserInfo {
    username: string;
    display_name: string;
  }

  interface SystemInfo {
    id: string;
    name: string;
  }

  interface TableInfo {
    id: string;
    name: string;
  }

  interface DetailData {
    id: string | number;
    name: string;
    description: string;
    managers: UserInfo[];
    users: UserInfo[];
    status: string;
    updated_by: string;
    updated_at: string;
    systems: SystemInfo[];
    tables: TableInfo[];
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  // 假数据
  const detailData = ref<DetailData>({
    id: '10001',
    name: '主机安全审计',
    description: '-',
    managers: [
      { username: 'zhaominghui', display_name: '赵明辉' },
    ],
    users: [
      { username: 'zhangsan', display_name: '张三' },
      { username: 'lisi', display_name: '李四' },
      { username: 'wangwu', display_name: '王五' },
    ],
    status: 'enabled',
    updated_by: 'local_dev_user',
    updated_at: '2026-03-19 13:08',
    systems: [
      { id: '1', name: '蓝鲸配置平台' },
      { id: '2', name: '蓝鲸流程服务' },
    ],
    tables: [
      { id: '1', name: '用户行为分析表' },
      { id: '2', name: '资产清单表' },
    ],
  });

  const sliderTitle = computed(() => t('场景详情'));

  // 格式化管理员显示
  const formatManagers = (managers: UserInfo[]) => {
    if (!managers || managers.length === 0) return '-';
    return managers.map(m => `${m.display_name}（${m.username}）`).join('、');
  };

  // 格式化使用者显示
  const formatUsers = (users: UserInfo[]) => {
    if (!users || users.length === 0) return '-';
    return users.map(u => `${u.display_name}（${u.username}）`).join('、');
  };

  // 编辑
  const handleEdit = () => {
    emits('edit', detailData.value);
  };

  // 切换状态
  const handleToggleStatus = () => {
    emits('toggle-status', detailData.value);
  };

  // 删除
  const handleDelete = () => {
    emits('delete', detailData.value);
  };

  // 跳转到场景
  const handleJumpToScene = () => {
    // TODO: 跳转逻辑
    console.log('Jump to scene:', detailData.value.id);
  };

  // 关闭
  const handleClose = () => {
    emits('update:isShow', false);
  };

  // 监听 sceneId 变化加载数据
  watch(() => props.sceneId, (newId) => {
    if (newId && props.isShow) {
      // TODO: 根据 sceneId 加载真实数据
      // 目前使用假数据
      console.log('Load scene detail:', newId);
    }
  });
</script>

<style lang="postcss" scoped>
.scene-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  .header-left {
    display: flex;
    align-items: center;

    .header-title {
      font-weight: 700;
    }

    .header-divider {
      margin: 0 8px;
      color: #dcdee5;
    }

    .header-scene-info {
      color: #63656e;
    }
  }

  .header-right {
    display: flex;
    gap: 8px;
  }
}

.scene-detail-content {
  padding: 24px 40px;

  .info-section {
    margin-bottom: 24px;

    .section-title {
      display: flex;
      align-items: center;
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 700;
      color: #313238;

      .count-tag {
        margin-left: 8px;
      }
    }

    .info-list {
      .info-item {
        display: flex;
        margin-bottom: 16px;
        font-size: 12px;
        line-height: 20px;

        .info-label {
          flex-shrink: 0;
          width: 100px;
          color: #63656e;
          text-align: right;
        }

        .info-value {
          display: flex;
          flex: 1;
          align-items: center;
          color: #313238;

          .jump-link {
            color: #3a84ff;
            cursor: pointer;

            &:hover {
              color: #699df4;
            }
          }
        }
      }
    }

    .system-list,
    .table-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      .system-tag,
      .table-tag {
        margin: 0;
      }
    }
  }
}
</style>
