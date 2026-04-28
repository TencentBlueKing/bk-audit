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
  <div
    class="landing-page"
    @click="handleCloseSelect($event)">
    <!-- 顶部：插图 + 内容 -->
    <div class="landing-container">
      <div class="landing-illustration">
        <img
          alt="系统接入"
          :src="landingImg">
      </div>
      <div class="landing-right">
        <h1 class="landing-title">
          {{ t('了解系统接入') }}
        </h1>
        <p class="landing-subtitle">
          {{ t('将你的系统接入审计中心实现操作审计与安全风控') }}
        </p>
        <div class="landing-content">
          <div class="section">
            <div class="section-title">
              {{ t('接入系统后可以实现') }}：
            </div>
            <ul class="feature-list">
              <li>{{ t('接入后自动采集系统操作日志') }}</li>
              <li>{{ t('支持权限模型配置和操作诊断') }}</li>
              <li>{{ t('接入的系统可被安全审计增强系统安全') }}</li>
            </ul>
            <div class="action-row">
              <span
                class="link-text"
                @click="handleLearnMore">
                {{ t('了解更多') }}
              </span>
              <audit-icon
                class="right-icon"
                type="right" />
            </div>
          </div>

          <div class="section">
            <div class="section-title">
              {{ t('更多接入问题咨询？') }}
            </div>
            <p class="permission-desc">
              {{ t('请通过企业微信联系') }}
              <span @click="contactHelper">
                <img
                  class="qw-icon"
                  src="@/images/qw.svg">
                iegsc_helper {{ t('IEG安全助手') }}
              </span>
              {{ t('咨询接入系统问题') }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部全宽区域 -->
    <div class="landing-bottom">
      <!-- 分隔线 -->
      <div class="divider-section">
        <div class="divider-line" />
        <span class="divider-text">{{ t('请选择以下接入类型开始接入') }}</span>
        <div class="divider-line" />
      </div>

      <!-- 接入方式卡片 -->
      <div class="access-cards">
        <div
          class="access-card"
          @click="handleAccessNewSystem">
          <div class="card-icon">
            <img
              class="card-img"
              src="@/images/new-jieru.svg">
          </div>
          <div class="card-body">
            <div class="card-title">
              {{ t('接入新系统') }}
            </div>
            <div class="card-desc">
              {{ t('适用于新系统首次接入蓝鲸安全体系') }}
            </div>
          </div>
        </div>

        <div
          class="access-card existing-card"
          @click.stop="handleToggleExistingSelect">
          <div class="card-icon">
            <img
              class="card-img"
              src="@/images/jieru.svg">
          </div>
          <div class="card-body">
            <div class="card-title">
              {{ t('接入已有系统') }}
              <span class="badge">{{ pendingList.length }}</span>
            </div>
            <div class="card-desc">
              {{ t('适用于已在蓝鲸权限中心注册过但尚未同步注册到审计中心的系统') }}
            </div>
          </div>
        </div>

        <!-- 下拉选择区域 -->
        <transition name="slide-down">
          <div
            v-if="isShowSelect"
            class="select-dropdown">
            <bk-input
              v-model="selectInput"
              behavior="simplicity"
              :placeholder="t('请输入')"
              @input="handleSearch">
              <template #prefix>
                <audit-icon
                  type="search1" />
              </template>
            </bk-input>
            <div
              v-if="dataList.length > 0"
              class="system-list">
              <div
                v-for="item in dataList"
                :key="item.id">
                <!-- 待接入状态 - 可点击 -->
                <div
                  v-if="item.audit_status === 'pending'"
                  class="system-item"
                  :class="{ 'system-item-active': activeItemId === item.id }"
                  @click.stop="handleSystemItemClick(item.id)">
                  <div class="system-item-name">
                    <span
                      v-bk-tooltips="{
                        content: item.name,
                        disabled: item.name.length <= 20,
                        placement: 'top'
                      }"
                      class="system-item-title">{{ item.name }}</span>
                    <span class="system-item-id">({{ item.id }})</span>
                  </div>
                  <div class="system-item-source">
                    {{ t('来源') }}：{{ sourceType(item.source_type) }}
                  </div>
                </div>

                <!-- 已接入状态 - 禁用 -->
                <bk-popover
                  v-else
                  :content="t('已接入审计中心')"
                  placement="top"
                  theme="light">
                  <div
                    class="system-item system-item-disabled"
                    @click.stop="() => {}">
                    <div class="system-item-name">
                      <span
                        v-bk-tooltips="{
                          content: item.name,
                          disabled: item.name.length <= 20,
                          placement: 'top'
                        }"
                        class="system-item-title">{{ item.name }}</span>
                      <span class="system-item-id">({{ item.id }})</span>
                    </div>
                    <div class="system-item-source">
                      {{ t('来源') }}：{{ sourceType(item.source_type) }}
                    </div>
                  </div>
                </bk-popover>
              </div>
            </div>
            <div
              v-else
              class="list-empty">
              {{ t('搜索结果为空') }}
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@/hooks/use-request';
  import landingImg from '@/images/access-system.png';

  interface SystemItem {
    id: string;
    name: string;
    source_type: string;
    audit_status: string;
  }

  const { t } = useI18n();
  const router = useRouter();

  // 待接入系统数据
  const pendingList = ref<SystemItem[]>([]);
  const dataList = ref<SystemItem[]>([]);
  const originDataList = ref<SystemItem[]>([]);
  const activeItemId = ref<string>('');
  const isShowSelect = ref(false);
  const selectInput = ref('');

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  // 全局数据（来源类型）
  const {
    data: GlobalChoices,
  } = useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    manual: true,
  });

  // 获取待接入系统列表
  const {
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    onSuccess: (data) => {
      originDataList.value = data;
      dataList.value = data;
      pendingList.value = data.filter(item => item.audit_status === 'pending');
    },
  });

  const sourceType = (type: string) => {
    if (!GlobalChoices.value?.meta_system_source_type) return type;
    const statusItem = GlobalChoices.value.meta_system_source_type.find(item => item.id === type);
    return statusItem?.name || type;
  };

  // 搜索过滤
  const handleSearch = () => {
    if (!selectInput.value.trim()) {
      dataList.value = originDataList.value;
    } else {
      const searchText = selectInput.value.toLowerCase();
      // eslint-disable-next-line max-len
      dataList.value = originDataList.value.filter(item => item.name.toLowerCase().includes(searchText) || item.id.toLowerCase().includes(searchText));
    }
  };

  // 展开/收起下拉
  const handleToggleExistingSelect = () => {
    if (pendingList.value.length > 0) {
      isShowSelect.value = !isShowSelect.value;
    } else {
      isShowSelect.value = false;
    }
  };

  // 点击外部关闭下拉
  const handleCloseSelect = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (target.closest('.bk-input') || target.closest('.select-dropdown')) {
      return;
    }
    isShowSelect.value = false;
  };

  // 选择系统并跳转（接收 id，与 system-access 一致）
  const handleSystemItemClick = (id: string) => {
    activeItemId.value = activeItemId.value === id ? '' : id;
    router.push({
      name: 'systemAccessSteps',
      query: {
        step: '1',
        showModelType: 'false',
        isNewSystem: 'false',
        systemId: id,
        fromLanding: 'true',
      },
    });
  };

  // 页面挂载时加载待接入系统列表（与 system-access 保持一致）
  onMounted(() => {
    fetchSystemWithAction({
      sort_keys: 'audit_status,name',
      with_favorite: false,
      with_system_status: false,
      source_type__in: 'iam_v3,iam_v4',
    });
  });

  const handleLearnMore = () => {
    window.open(configData.value.help_info.bkaudit_wiki, '_blank');
  };

  const contactHelper = () => {
    window.open(`wxwork://message?uin=${configData.value.iegsec_helper}`, '_blank');
  };

  const handleAccessNewSystem = () => {
    router.push({
      name: 'systemAccessSteps',
      query: {
        step: '1',
        showModelType: 'false',
        isNewSystem: 'true',
        fromLanding: 'true',
      },
    });
  };
</script>

<style scoped lang="postcss">
.landing-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: calc(100vh - 104px);
  padding: 56px 40px;
  background: linear-gradient(180deg, #f5f7fa 0%, #fafbfd 100%);
}

.landing-container {
  display: flex;
  width: 100%;
  max-width: 1400px;
  gap: 90px;
  align-items: center;
}

.landing-bottom {
  width: 100%;
  max-width: 1400px;
  margin-top: 44px;
}

.landing-illustration {
  display: flex;
  width: 540px;
  height: 540px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;

  img {
    width: 420px;
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
  margin: 0 0 16px;
  font-size: 42px;
  font-weight: 700;
  line-height: 1.3;
  color: #21293b;
}

.landing-subtitle {
  margin: 0 0 38px;
  font-size: 17px;
  line-height: 1.6;
  color: #979ba5;
}

.landing-content {
  padding: 34px 36px 30px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 20px rgb(59 126 255 / 10%);
}

.section {
  margin-bottom: 32px;

  &:last-child {
    margin-bottom: 0;
  }
}

.section-title {
  margin-bottom: 18px;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.5;
  color: #21293b;
}

.feature-list {
  padding-left: 22px;
  margin: 0 0 20px;
  list-style: none;

  li {
    position: relative;
    padding-left: 20px;
    margin-bottom: 10px;
    font-size: 15px;
    line-height: 1.7;
    color: #63656e;

    &::before {
      position: absolute;
      top: 8px;
      left: 0;
      width: 4px;
      height: 16px;
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
  gap: 10px;
  cursor: pointer;

  .right-icon {
    font-size: 22px;
    color: #3b7eff;
  }
}

.link-text {
  font-size: 15px;
  color: #3b7eff;
  cursor: pointer;
}

.permission-desc {
  margin: 0;
  font-size: 15px;
  line-height: 1.75;
  color: #63656e;

  span {
    display: inline-flex;
    color: #3b7eff;
    vertical-align: baseline;
    cursor: pointer;
    align-items: center;
    gap: 5px;
  }

  .qw-icon {
    width: 19px;
    height: 19px;
  }
}

.divider-section {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 32px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background-color: #dcdee5;
}

.divider-text {
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
}

.access-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px;
}

.existing-card {
  position: relative;

  &.card-open {
    border-color: #3b7eff;
    box-shadow: 0 4px 20px rgb(59 126 255 / 14%);
  }
}

.access-card {
  display: flex;
  padding: 28px 24px;
  cursor: pointer;
  background: #fff;
  border: 1px solid #eaebf0;
  border-radius: 12px;
  box-shadow: 0 1px 8px rgb(59 126 255 / 6%);
  transition: all .25s;
  align-items: flex-start;
  gap: 20px;

  &:hover {
    border-color: #3b7eff;
    box-shadow: 0 4px 20px rgb(59 126 255 / 14%);
  }
}

.card-icon {
  display: flex;
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;

  .card-img {
    width: 48px;
    height: 48px;
    object-fit: contain;
  }
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-title {
  display: flex;
  margin-bottom: 10px;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.35;
  color: #21293b;
  align-items: center;
  gap: 8px;
}

.badge {
  display: inline-flex;
  height: 22px;
  padding: 0 10px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
  color: #3b7eff;
  background: #e1edff;
  border-radius: 11px;
  align-items: center;
}

.card-desc {
  font-size: 14px;
  line-height: 1.6;
  color: #979ba5;
}

.bottom-tip {
  display: flex;
  margin-top: 24px;
  font-size: 14px;
  line-height: 1.65;
  color: #ff6ec7;
  align-items: flex-start;
  gap: 6px;

  :deep(.bk-icon) {
    position: relative;
    top: 3px;
    flex-shrink: 0;
    font-size: 16px;
  }
}

/* 下拉选择区域 */
.select-dropdown {
  padding: 16px 20px;
  margin-top: 12px;
  background: #fff;
  border: 1px solid #eaebf0;
  border-radius: 10px;
  box-shadow: 0 4px 24px rgb(59 126 255 / 12%);
  grid-column: 1 / -1;

  :deep(.bk-input) {
    margin-bottom: 8px;

    .bk-input-wrapper {
      border-color: #eaebf0;

      &:hover,
      &:focus-within {
        border-color: #3b7eff;
      }
    }
  }
}

.system-list {
  max-height: 260px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.system-item {
  display: flex;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.5;
  color: #63656e;
  cursor: pointer;
  border-radius: 6px;
  transition: all .15s;
  justify-content: space-between;
  align-items: center;

  &:hover {
    background: #f5f7fa;
  }

  &.system-item-active {
    color: #3b7eff;
    background: #e6f1ff;
  }

  &.system-item-disabled {
    cursor: not-allowed;
    opacity: 60%;

    &:hover {
      background: transparent;
    }
  }
}

.system-item-name {
  display: flex;
  align-items: center;
  gap: 4px;

  .system-item-title {
    display: inline-block;
    max-width: 280px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .system-item-id {
    color: #c4c6cc;
  }
}

.system-item-source {
  color: #c4c6cc;
  flex-shrink: 0;
}

.list-empty {
  padding: 32px 0 16px;
  font-size: 13px;
  color: #979ba5;
  text-align: center;
}

.slide-down-enter-active,
.slide-down-leave-active {
  overflow: hidden;
  transition: all .25s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0%;
  transform: translateY(-8px);
}
</style>
