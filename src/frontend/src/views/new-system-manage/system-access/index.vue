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
    class="access"
    :class="{ 'with-sidebar': withSidebar, 'sidebar-folded': isSideFolded }"
    @click="handleCloseSelect($event)">
    <img
      class="access-empty"
      :src="emptySvg">
    <div class="icon-title">
      {{ t("尚未接入系统") }}
    </div>
    <div class="title-text">
      <span>{{ t("请选择以下类型进行接入") }}</span>
      <!-- <span class="text-link">{{ t("查看接入指引") }}</span> -->
    </div>
    <div class="access-btn">
      <div
        class="btn btn-left"
        @click="handleRouterChange('systemAccessSteps', true)">
        <div class="btn-icon">
          <audit-icon
            class="btn-icon-add"
            type="add" />
        </div>
        <div class="access-text">
          <div class="access-text-top">
            {{ t("新系统接入") }}
          </div>
          <div class="access-text-bottom">
            {{ t("适用于新系统首次接入蓝鲸安全体系") }}
          </div>
        </div>
      </div>
      <div
        class="btn-right"
        @click.stop="handleIsShowSelect">
        <div class="btn">
          <div
            class="btn-icon"
            :style="pendingList.length > 0 ? '' : 'background: #f5f7fa;'">
            <img
              class="btn-icon-add"
              :src="pendingList.length > 0 ? ImportActiveSvg : ImportSvg">
          </div>
          <div class="access-text">
            <div class="access-text-top">
              {{ t("待接入的系统") }}<span class="text-top-num">{{ pendingList.length }}</span>
            </div>
            <div
              v-if="pendingList.length > 0"
              class="access-text-bottom">
              {{
                t(
                  "已在其他安全产品中注册系统的权限模型，但尚未同步注册到审计中心"
                )
              }}
            </div>
            <div
              v-else
              v-bk-tooltips="{ content: t('暂无待接入的系统') }"
              class="access-text-bottom">
              {{
                t(
                  "已在其他安全产品中注册系统的权限模型，但尚未同步注册到审计中心"
                )
              }}
            </div>
          </div>
        </div>
        <div
          v-if="isShowSelect"
          class="select-input">
          <bk-input
            v-model="selectInput"
            behavior="simplicity"
            style=" width: 98%;margin-left: 1%;background-color: #fff"
            @click.stop="handleSearch"
            @input="handleSearch">
            <template #prefix>
              <audit-icon
                class="btn-icon-search1"
                type="search1" />
            </template>
          </bk-input>

          <div
            v-if="dataList.length > 0"
            class="list">
            <div
              v-for="item in dataList"
              :key="item.id"
              class="list-item"
              text>
              <div
                v-if="item.audit_status === 'pending'"
                class="list-btn"
                :class="{ 'list-btn-active': activeItemId === item.id }"
                @click.stop="handleItemClick(item.id)">
                <div class="list-btn-name">
                  <span
                    v-bk-tooltips="{
                      content: item.name,
                      disabled: item.name.length <= 20,
                      placement: 'top'
                    }"
                    class="list-btn-title">{{ item.name }}</span>
                  <span class="list-btn-id">({{ item.id }})</span>
                </div>
                <div class="list-btn-source">
                  {{ t('来源') }}：{{ sourceType(item.source_type) }}
                </div>
              </div>

              <bk-popover
                v-if="item.audit_status === 'accessed'"
                :content="t('已接入审计中心')"
                placement="top"

                theme="light">
                <div
                  class="list-btn list-btn-not-allowed"
                  @click.stop="()=>{}">
                  <div class="list-btn-name">
                    <span
                      v-bk-tooltips="{
                        content: item.name,
                        disabled: item.name.length <= 20,
                        placement: 'top'
                      }"
                      class="list-btn-id">{{ item.name }}</span>
                    <span class="list-btn-id">({{ item.id }})</span>
                  </div>
                  <div class="list-btn-source">
                    {{ t('来源') }}：{{ sourceType(item.source_type) }}
                  </div>
                </div>
              </bk-popover>
            </div>
          </div>
          <div
            v-else
            class="list-empty">
            <div class="empty">
              {{ t('搜索结果为空') }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter, useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import ImportSvg from '@images/Import.svg';
  import ImportActiveSvg from '@images/Import-active.svg';
  import emptySvg from '@images/empty.svg?inline';

  import useEventBus from '@/hooks/use-event-bus';
  import useRequest from '@/hooks/use-request';

  interface SystemItem {
    id: string;
    name: string;
    source_type: string;
    audit_status: string;
  }

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { on: onEvent } = useEventBus();

  // 是否在带侧边栏模式（isShowSideBar==='true' 时页面自适应侧边栏）
  const withSidebar = computed(() => route.params?.isShowSideBar === 'true');
  // 侧边栏是否折叠（折叠时宽度60px，展开时220/280px）
  const isSideFolded = ref(false);

  const isShowSelect = ref(false);

  const handleRouterChange = (name: string, isNewSystem: boolean) => {
    router.push({
      name,
      params: withSidebar.value ? { isShowSideBar: 'true' } : undefined,
      query: {
        step: '1',
        showModelType: 'false',
        isNewSystem: isNewSystem.toString(),
      },
    });
  };
  const dataList = ref<SystemItem[]>([]);
  const pendingList = ref<SystemItem[]>([]);
  const selectInput = ref();
  const originDataList = ref<SystemItem[]>([]); // 保存原始数据
  const activeItemId = ref<string>(''); // 当前选中项的ID

  const handleItemClick = (id: string) => {
    activeItemId.value = activeItemId.value === id ? '' : id;
    router.push({
      name: 'systemAccessSteps',
      params: withSidebar.value ? { isShowSideBar: 'true' } : undefined,
      query: {
        step: '1',  // 改为字符串类型
        showModelType: 'false',  // 改为字符串类型
        isNewSystem: 'false',  // 改为字符串类型
        systemId: id,
      },
    });
  };
  const handleIsShowSelect = () => {
    if (pendingList.value.length > 0) {
      isShowSelect.value = !isShowSelect.value;
    } else {
      isShowSelect.value = false;
    }
  };

  const handleCloseSelect = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    // 如果点击的是输入框或输入框的子元素，不关闭下拉框
    if (target.closest('.bk-input') || target.closest('.select-input')) {
      return;
    }
    isShowSelect.value = false;
  };

  const {
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    onSuccess: (data) => {
      originDataList.value = data;
      dataList.value = data.filter(item => item.permission.edit_system && item.permission.view_system);
      pendingList.value = data.filter(item => item.audit_status === 'pending').filter(item => item.permission.edit_system && item.permission.view_system);
    },
  });
  // 全局数据
  const {
    data: GlobalChoices,
  } = useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    manual: true,
  });

  const sourceType = (type: string) => {
    if (!GlobalChoices.value?.meta_system_source_type) return type;
    const statusItem = GlobalChoices.value.meta_system_source_type.find(item => item.id === type);
    return statusItem?.name || type; // 如果找不到对应状态，返回原值
  };

  // 搜索处理方法
  const handleSearch = () => {
    if (!selectInput.value.trim()) {
      // 搜索值为空时显示全部数据
      dataList.value = originDataList.value;
    } else {
      // 根据名称或ID进行搜索（不区分大小写）
      const searchText = selectInput.value.toLowerCase();
      dataList.value = originDataList.value.filter(item => item.name.toLowerCase().includes(searchText)
        || item.id.toLowerCase().includes(searchText));
    }
  };
  onMounted(() => {
    fetchSystemWithAction({
      sort_keys: 'audit_status,name',
      with_favorite: false,
      with_system_status: false,
      source_type__in: 'iam_v3,iam_v4',
      action_ids: 'edit_system,view_system',
      audit_status__in: 'pending',
    });
  });
  // 监听侧边栏折叠/展开事件
  (onEvent as (type: string, handler: (...args: any[]) => void) => void)('menu-flod', (folded: boolean) => {
    isSideFolded.value = folded;
  });
</script>

<style scoped lang="postcss">
.access {
  position: relative;
  width: 100vw;
  height: 100vh;
  background-color: var(--bk-theme-surface-subtle);
  transition: width .3s;

  &.with-sidebar {
    width: 100%;
    height: auto;
    min-height: calc(100vh - 160px);
  }

  .access-empty {
    position: absolute;
    top: 128px;
    left: 50%;
    width: 440px;
    height: 200px;
    transform: translateX(-50%);
  }

  .icon-title {
    position: absolute;
    top: 328px;
    left: 50%;
    height: 31px;
    font-size: 24px;
    letter-spacing: 0;
    color: var(--bk-theme-text-strong);
    transform: translateX(-50%);
  }

  .title-text {
    position: absolute;
    top: 375px;
    left: 50%;
    height: 22px;
    font-size: 14px;
    line-height: 22px;
    letter-spacing: 0;
    color: var(--bk-theme-text-default);
    transform: translateX(-50%);

    .text-link {
      color: var(--bk-theme-color-brand-2);
      cursor: progress;
    }
  }

  .access-btn {
    position: absolute;
    top: 420px;
    left: 50%;
    display: flex;
    font-size: 14px;
    letter-spacing: 0;
    color: var(--bk-theme-text-default);
    transform: translateX(-50%);

    .btn {
      display: flex;
      width: 488px;
      height: 124px;
      cursor: pointer;
      background: var(--bk-theme-surface-default);
      border-radius: var(--bk-theme-tag-radius);
      box-shadow: var(--bk-theme-card-shadow);

      .btn-icon {
        position: relative;
        top: 30px;
        width: 64px;
        height: 64px;
        margin-left: var(--bk-theme-space-16);
        cursor: pointer;
        background: var(--bk-theme-fill-selected);
        border-radius: var(--bk-theme-message-radius);

        .btn-icon-add {
          position: absolute;
          top: 50%;
          left: 50%;
          font-size: 33px;
          color: var(--bk-theme-color-brand-2);
          transform: translate(-50%, -50%);
        }
      }

      .access-text {
        width: 85%;

        .access-text-top {
          height: 24px;
          margin-top: var(--bk-theme-space-24);
          margin-left: var(--bk-theme-space-16);
          font-size: 16px;
          font-weight: 700;
          line-height: 24px;
          letter-spacing: 0;
          color: var(--bk-theme-text-strong);

          .text-top-num {
            display: inline-block;
            height: 24px;
            padding-right: var(--bk-theme-space-4);
            padding-left: var(--bk-theme-space-4);
            margin-left: var(--bk-theme-space-12);
            font-size: 10px;
            line-height: 24px;
            color: var(--bk-theme-color-brand-1);
            text-align: center;
            background-color: var(--bk-theme-fill-selected);
            border-radius: var(--bk-theme-tag-radius);
          }
        }

        .access-text-bottom {
          width: 95%;
          height: 24px;
          margin-top: var(--bk-theme-space-8);
          margin-left: var(--bk-theme-space-16);
          font-size: 14px;
          line-height: 22px;
          letter-spacing: 0;
          color: var(--bk-theme-text-default);
        }
      }
    }

    .btn-right {
      margin-left: var(--bk-theme-space-12);

      .bk-select {
        margin-top: var(--bk-theme-space-4);

      }

      .label {
        display: flex;
      }
    }

    .select-input {
      width: 488px;
      margin-top: var(--bk-theme-space-4);
      background-color: var(--bk-theme-surface-default);

      .btn-icon-search1 {
        margin-top: var(--bk-theme-space-8);
        font-size: 20px;
        color: var(--bk-theme-text-weak);
        background-color: var(--bk-theme-surface-default);
      }

      .list {
        height: 20vh;
        margin-top: var(--bk-theme-space-4);
        overflow: auto;

        .list-btn {
          display: flex;
          width: 100%;
          height: 32px;
          font-size: 12px;
          line-height: 32px;
          letter-spacing: 0;
          color: var(--bk-theme-text-default);
          cursor: pointer;
          justify-content: space-between;

          &:hover {
            background: var(--bk-theme-surface-subtle);
          }

          &.list-btn-active {
            color: var(--bk-theme-color-brand-2);
            background: var(--bk-theme-fill-selected);
          }

          .list-btn-name {
            display: flex;
            width: 350px;
            margin-left: 1%;

            .list-btn-title {
              display: inline-block;
              max-width: 250px;
              overflow: hidden;
              font-family: monospace;
              text-overflow: ellipsis;
              white-space: nowrap;
            }

            .list-btn-id {
              display: inline-block;
              margin-left: var(--bk-theme-space-4);
              color: var(--bk-theme-border-strong);
            }
          }

          .list-btn-source {
            margin-right: 1%;
            color: var(--bk-theme-border-strong);
          }

        }

        .list-btn-not-allowed {
          &:hover {
            cursor: not-allowed;
          }
        }

      }

      .list-empty {
        position: relative;
        height: 20vh;
        margin-top: var(--bk-theme-space-4);
        overflow: auto;

        .empty {
          position: absolute;
          top: 50%;
          left: 50%;
          color: var(--bk-theme-text-weak);
          transform: translate(-50%,-50%);
        }
      }
    }
  }
}
</style>
