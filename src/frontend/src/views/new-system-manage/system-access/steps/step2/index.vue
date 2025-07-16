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
  <div class="step2">
    <div class="step2-header">
      <div class="step2-header-box">
        <span class="step2-header-title"> {{ t('请设置权限模型') }}</span>
        <bk-dropdown
          :disabled="isDropdown"
          rigger="click">
          <div
            class="step2-popover"
            :style="isDropdown ? 'background-color: #eaebf0;color: #4D4F56;' : ''">
            {{ popoverBtn }}
            <audit-icon
              class="angle-line-down"
              :style="isDropdown ? 'color: #C4C6CC;' : ''"
              type="angle-line-down" />
          </div>
          <template #content>
            <bk-dropdown-menu>
              <bk-dropdown-item
                v-for="item in dropdownList"
                :key="item.id"
                @click="handleDropdown(item)">
                {{ item.title }}
              </bk-dropdown-item>
            </bk-dropdown-menu>
          </template>
        </bk-dropdown>
        <audit-icon
          class="info-fill"
          type="info-fill" />
        <span class="step2-header-right"> {{ t('添加的资源和操作将会实时保存并注册，后续可随时在审计中心修改') }}</span>
      </div>
    </div>

    <div class="step2-list">
      <step2
        ref="step2Ref"
        :can-edit-system="canEditSystem"
        @get-is-disabled-btn="getIsDisabledBtn" />
    </div>
  </div>
</template>
<script setup lang="tsx">
  import { InfoBox } from 'bkui-vue';
  import { computed, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import Step2 from '@views/system-manage/detail/components/access-model/index.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface Props {
    canEditSystem: boolean;
  }
  interface Exposes {
    handlerSubmit: () => void,
    previousStep: () => void,

  }
  interface Emits {
    (e: 'getIsDisabledBtn', val: boolean): void;
  }

  defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { messageSuccess } = useMessage();

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();

  const dropdownList = ref([
    {
      title: t('复杂权限类型'),
      id: 'complex',
    },
    {
      title: t('简单权限类型'),
      id: 'simple',
    },
  ]);
  const isDisabledBtn = ref(false);
  const isDropdown = ref(false);
  const systemDetail = ref();
  const step2Ref = ref();

  const popoverBtn = computed(() => (route.query.type === 'simple' ? '简单权限类型' : '复杂权限类型'));

  const getIsDisabledBtn = (val: Record<string, any>) => {
    if (val.actionListListLength > 0 || val.resourceTypeListLength > 0) {
      isDisabledBtn.value = false;
      isDropdown.value = true;
    } else {
      isDisabledBtn.value = true;
      isDropdown.value = false;
    }
    emits('getIsDisabledBtn', isDisabledBtn.value);
  };

  const handleDropdown = (item: Record<string, any>) => {
    router.replace({
      query: {
        ...route.query,
        type: item.id,
      },
      params: {
        ...route.params,
      },
    });
  };

  const {
    run: fetchSystemDetail,
  } = useRequest(MetaManageService.fetchSystemDetail, {
    defaultParams: [],
    defaultValue: null,
    onSuccess: (result) => {
      systemDetail.value = result;
      if (result) {
        isDropdown.value = (result.collector_count === 0 || result.resource_type_count === 0)
          && result.system_stage !== 'permission_model';
      } else {
        isDropdown.value = false;
      }
    },
  });
  // 更新系统
  const {
    run: fetchSystemUpdate,
  } = useRequest(MetaManageService.fetchSystemUpdate, {
    defaultValue: [],
    onSuccess: () => {
      messageSuccess(t('权限模型设置成功'));
      router.push({
        query: {
          ...route.query,
          step: 3,
        },
      });
    },
  });

  onMounted(() => {
    fetchSystemDetail({
      id: route.params.id,
    });
  });

  defineExpose<Exposes>({
    handlerSubmit() {
      InfoBox({
        type: 'warning',
        title: t('确认设置权限模型?'),
        contentAlign: 'left',
        content: (
        <div>
            <span>{t('系统')}：{ `${systemDetail.value.name}(${systemDetail.value.system_id})` }</span>
        </div>
      ),
        cancelText: t('取消'),
        confirmText: t('确定'),
        onConfirm() {
          window.changeConfirm = false;
          fetchSystemUpdate({
            ...systemDetail.value,
            permission_type: route.query.type === 'complex' ? 'complex' : 'simple',
          });
        },
        onCancel() {},
      });
    },
    previousStep() {
      router.push({
        query: {
          ...route.query,
          step: isDropdown.value ? 1 : 1.5,
          fromStep: 2,
        },
      });
    },
  });
</script>
<style scoped lang="postcss">
.step2 {
  max-height: 90vh;
  padding-bottom: 60px;
  overflow: auto;

  .step2-header {
    position: fixed;
    top: 104px;
    left: 0;
    z-index: 999;
    width: 100%;
    height: 48px;
    background: #fff;
    border-top: 1px solid #eceef2;
    box-shadow: 0 2px 4px 0 #1919290d;

    .step2-header-box {
      /* height: 22px; */
      top: 20px;
      padding-top: 14px;
      padding-left: 24px;

      .step2-header-title {
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0;
        color: #4d4f56;
      }

      .step2-header-right {
        font-size: 12px;
        letter-spacing: 0;
        color: #4d4f56;
      }
    }

    .info-fill {
      color: #4d4f56;
    }

    .step2-popover {
      padding: 3px 5px;
      margin-right: 5px;
      margin-left: 5px;
      color: #1768ef;
      background-color: #e1ecff;
    }
  }

  .step2-list {
    padding: 20px 24px;
    margin-top: 40px;

  }

  .angle-line-down {
    color: #1768ef;
  }
}
</style>
