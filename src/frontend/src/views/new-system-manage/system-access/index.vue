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
        @click="handleRouterChange('systemAccessSteps')">
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
          <div class="btn-icon">
            <img
              class="btn-icon-add"
              src="@images/Import.svg">
          </div>
          <div class="access-text">
            <div class="access-text-top">
              {{ t("待接入的系统") }}<span class="text-top-num">5</span>
            </div>
            <div class="access-text-bottom">
              {{
                t(
                  "已在其他安全产品中注册系统的权限模型，但尚未同步注册到审计中心"
                )
              }}
            </div>
          </div>
        </div>
        <bk-select
          v-show="isShowSelect"
          v-model="selectedValue"
          class="bk-select"
          display-key="label"
          filterable
          id-key="value"
          :input-search="false"
          :list="dataList">
          <template #optionRender="{ item }">
            <div style="display: flex;width: 100%;justify-content: space-between;">
              <div>
                <span>{{ item.label }}</span>
                <span style="color: #c4c6cc;">({{ item.value }})</span>
              </div>
              <div style="color: #c4c6cc;">
                来源：权限中心
              </div>
            </div>
          </template>
        </bk-select>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const isShowSelect = ref(false);
  console.log(route);

  const handleRouterChange = (name: string) => {
    router.push({
      name,
    });
  };
  const selectedValue = ref();
  const dataList = ref([
    {
      disabled: false,
      value: 111,
      label: '地下城',
    },
    {
      disabled: false,
      value: 11,
      label: 'PPP',
    },
    {
      disabled: false,
      value: 1,
      label: 'XXX',
    },
  ]);

  const handleMouseenter = () => {
    isShowSelect.value = true;
  };
  const handleMouseleave = () => {
    // isShowSelect.value = false
  };

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
