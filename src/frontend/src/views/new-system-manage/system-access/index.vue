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
  <div class="access">
    <img
      class="access-empty"
      src="@images/empty.svg">
    <div class="icon-title">
      {{ t("尚未接入系统") }}
    </div>
    <div class="title-text">
      <span>{{ t("请选择以下类型进行接入，") }}</span>
      <span class="text-link">{{ t("查看接入指引") }}</span>
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
        @mouseenter="handleMouseenter"
        @mouseleave="handleMouseleave">
        <div class="btn">
          <div
            class="btn-icon"
            :style="dataList.length > 0 ? '' : 'background: #F5F7FA;'">
            <img
              class="btn-icon-add"
              :src="dataList.length > 0 ? ImportActiveSvg : ImportSvg">
          </div>
          <div class="access-text">
            <div class="access-text-top">
              {{ t("待接入的系统") }}<span class="text-top-num">{{ dataList.length }}</span>
            </div>
            <div
              v-if="dataList.length > 0"
              v-bk-tooltips="{ content: '暂无待接入的系统'}"
              class="access-text-bottom">
              {{
                t(
                  "已在其他安全产品中注册系统的权限模型，但尚未同步注册到审计中心"
                )
              }}
            </div>
            <div
              v-else
              v-bk-tooltips="{ content: '暂无待接入的系统'}"
              class="access-text-bottom">
              {{
                t(
                  "已在其他安全产品中注册系统的权限模型，但尚未同步注册到审计中心"
                )
              }}
            </div>
          </div>
        </div>
        <bk-select
          v-if="isShowSelect"
          v-model="systemId"
          class="bk-select"
          filterable
          :popover-options="{
            width: 'auto'
          }"
          @change="handleSelectChange">
          <bk-option
            v-for="item in dataList"
            :id="item.id"
            :key="item.id"
            :name="item.name">
            <div style="display: flex;width: 100%;justify-content: space-between;">
              <div>
                <span>{{ item.name }}</span>
                <span style="color: #c4c6cc;">({{ item.id }})</span>
              </div>
              <div style="margin-left: 10px;color: #c4c6cc;">
                {{ t('来源：') }} {{ sourceType(item.source_type) }}
              </div>
            </div>
          </bk-option>
        </bk-select>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import ImportSvg from '@images/Import.svg';
  import ImportActiveSvg from '@images/Import-active.svg';

  import useRequest from '@/hooks/use-request';

  const { t } = useI18n();
  const router = useRouter();
  // const route = useRoute();
  const isShowSelect = ref(false);

  const handleRouterChange = (name: string, isNewSystem: boolean) => {
    router.push({
      name,
      query: {
        step: '1',  // 改为字符串类型
        showModelType: 'false',  // 改为字符串类型
        isNewSystem: isNewSystem.toString(),  // 转为字符串
      },
    });
  };
  const systemId = ref();
  interface SystemItem {
    id: string;
    name: string;
    source_type: string;
  }
  const dataList = ref<SystemItem[]>([]);

  const handleMouseenter = () => {
    isShowSelect.value = true;
  };
  const handleMouseleave = () => {
    // isShowSelect.value = false
  };

  const {
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    onSuccess: (data) => {
      dataList.value = data;
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

  const handleSelectChange = (val: string) => {
    let systemVal = null;
    dataList.value.forEach((i: SystemItem) => {
      if (i.id === val) {
        systemVal = JSON.stringify(i);
      }
    });
    router.push({
      name: 'systemAccessSteps',
      query: {
        step: '1',  // 改为字符串类型
        showModelType: 'false',  // 改为字符串类型
        isNewSystem: 'false',  // 改为字符串类型
        systemVal,
      },
    });
  };
  onMounted(() => {
    fetchSystemWithAction({
      with_favorite: false,
      with_system_status: false,
      audit_status__in: 'pending',
    });
  });
</script>

<style scoped lang="postcss">
.access {
  position: relative;
  width: 100vw;
  height: 100vh;
  background-color: #f5f7fa;

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
    color: #313238;
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
    color: #4d4f56;
    transform: translateX(-50%);

    .text-link {
      color: #3a84ff;
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
    color: #4d4f56;
    transform: translateX(-50%);

    .btn {
      display: flex;
      width: 488px;
      height: 124px;
      cursor: pointer;
      background: #fff;
      border-radius: 3px;
      box-shadow: 0 2px 4px 0 #1919290d;

      .btn-icon {
        position: relative;
        top: 30px;
        width: 64px;
        height: 64px;
        margin-left: 20px;
        cursor: pointer;
        background: #e1ecff;
        border-radius: 8px;

        .btn-icon-add {
          position: absolute;
          top: 50%;
          left: 50%;
          font-size: 33px;
          color: #3a84ff;
          transform: translate(-50%, -50%);
        }
      }

      .access-text {
        .access-text-top {
          height: 24px;
          margin-top: 24px;
          margin-left: 15px;
          font-size: 16px;
          font-weight: 700;
          line-height: 24px;
          letter-spacing: 0;
          color: #313238;

          .text-top-num {
            display: inline-block;
            height: 24px;
            padding-right: 5px;
            padding-left: 5px;
            margin-left: 10px;
            font-size: 10px;
            line-height: 24px;
            color: #1768ef;
            text-align: center;
            background-color: #e1ecff;
            border-radius: 2px;
          }
        }

        .access-text-bottom {
          width: 95%;
          height: 24px;
          margin-top: 8px;
          margin-left: 15px;
          font-size: 14px;
          line-height: 22px;
          letter-spacing: 0;
          color: #4d4f56;
        }
      }
    }

    .btn-right {
      margin-left: 10px;

      .bk-select {
        margin-top: 5px;

      }

      .label {
        display: flex;
      }
    }
  }
}
</style>
