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
  <smart-action
    class="create-strategy-page"
    :offset-target="getSmartActionOffsetTarget">
    <div class="create-strategy-main">
      <audit-form
        ref="formRef"
        class="strategt-form"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <card-part-vue :title="t('其他配置')">
          <template #content>
            <bk-form-item
              class="is-required"
              :label="t('风险单处理人')"
              label-width="160"
              property="processor_groups"
              style="flex: 1;">
              <bk-loading
                :loading="isGroupLoading"
                style="width: 100%;">
                <bk-select
                  ref="groupSelectRef"
                  v-model="formData.processor_groups"
                  class="bk-select"
                  filterable
                  :input-search="false"
                  multiple
                  multiple-mode="tag"
                  :placeholder="t('请选择通知组')"
                  :popover-options="{
                    zIndex: 1000
                  }"
                  :search-placeholder="t('请输入关键字')">
                  <auth-option
                    v-for="(item, index) in groupList"
                    :key="index"
                    action-id="list_notice_group"
                    :label="item.name"
                    :permission="checkResultMap.list_notice_group"
                    :value="item.id" />
                  <template #extension>
                    <div class="create-notice-group">
                      <auth-router-link
                        action-id="create_notice_group"
                        class="create_notice_group"
                        target="_blank"
                        :to="{
                          name: 'noticeGroupList',
                          query: {
                            create: true
                          }
                        }">
                        <audit-icon
                          style="font-size: 14px;color: #3a84ff;"
                          type="plus-circle" />
                        {{ t('新增通知组') }}
                      </auth-router-link>
                    </div>
                    <div
                      class="refresh"
                      @click="refreshGroupList">
                      <audit-icon
                        v-if="isGroupLoading"
                        class="rotate-loading"
                        svg
                        type="loading" />
                      <template v-else>
                        <audit-icon
                          type="refresh" />
                        {{ t('刷新') }}
                      </template>
                    </div>
                  </template>
                </bk-select>
              </bk-loading>
            </bk-form-item>
            <bk-form-item
              :label="t('关注人')"
              label-width="160"
              property="notice_groups"
              style="flex: 1;">
              <bk-loading
                :loading="isGroupLoading"
                style="width: 100%;">
                <bk-select
                  ref="groupSelectRef"
                  v-model="formData.notice_groups"
                  class="bk-select"
                  filterable
                  :input-search="false"
                  multiple
                  multiple-mode="tag"
                  :placeholder="t('请选择通知组')"
                  :popover-options="{
                    zIndex: 1000
                  }"
                  :search-placeholder="t('请输入关键字')">
                  <auth-option
                    v-for="(item, index) in groupList"
                    :key="index"
                    action-id="list_notice_group"
                    :label="item.name"
                    :permission="checkResultMap.list_notice_group"
                    :value="item.id" />
                  <template #extension>
                    <div class="create-notice-group">
                      <auth-router-link
                        action-id="create_notice_group"
                        class="create_notice_group"
                        target="_blank"
                        :to="{
                          name: 'noticeGroupList',
                          query: {
                            create: true
                          }
                        }">
                        <audit-icon
                          style="font-size: 14px;color: #3a84ff;"
                          type="plus-circle" />
                        {{ t('新增通知组') }}
                      </auth-router-link>
                    </div>
                    <div
                      class="refresh"
                      @click="refreshGroupList">
                      <audit-icon
                        v-if="isGroupLoading"
                        class="rotate-loading"
                        svg
                        type="loading" />
                      <template v-else>
                        <audit-icon
                          type="refresh" />
                        {{ t('刷新') }}
                      </template>
                    </div>
                  </template>
                </bk-select>
              </bk-loading>
            </bk-form-item>
          </template>
        </card-part-vue>
      </audit-form>
    </div>
    <template #action>
      <bk-button
        @click="handlePrevious">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        theme="primary"
        @click="submit">
        {{ t('提交') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import NoticeManageService from '@service/notice-group';

  import StrategyModel from '@model/strategy/strategy';

  import CardPartVue from '../step1/components/card-part.vue';

  import useRequest from '@/hooks/use-request';

  interface IFormData {
    processor_groups: Array<number>,
    notice_groups: Array<number>,
  }

  interface Emits {
    (e: 'previousStep', step: number): void;
    (e: 'nextStep', step: number, params: IFormData): void;
    (e: 'submitData'): void;
  }
  interface Props {
    editData: StrategyModel
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const groupSelectRef = ref();
  const formRef = ref();

  const formData = ref<IFormData>({
    processor_groups: [],
    notice_groups: [],
  });

  const rules = {
    processor_groups: [
      {
        validator: (value: Array<any>) => !!value.length,
        message: t('风险单处理人不能为空'),
        trigger: 'change',
      },
    ],
  };

  // 获取通知组权限
  const {
    data: checkResultMap,
  } = useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'list_notice_group',
    },
    defaultValue: {},
    manual: true,
  });

  const refreshGroupList = () => {
    groupList.value = [];
    groupSelectRef.value.searchKey = '';
    fetchGroupList();
  };

  // 获取通知组下拉
  const {
    loading: isGroupLoading,
    data: groupList,
    run: fetchGroupList,
  } = useRequest(NoticeManageService.fetchGroupSelectList, {
    defaultValue: [],
    manual: true,
  });

  const handlePrevious = () => {
    emits('previousStep', 3);
  };

  const handleCancel = () => {
    router.push({
      name: 'strategyList',
    });
  };

  const submit = () => {
    formRef.value.validate().then(() => {
      // 先更新formData, 最后一步step不变
      emits('nextStep', 3, formData.value);
      emits('submitData');
    });
  };

  // 编辑
  watch(() => props.editData, (data) => {
    formData.value.notice_groups = Array.isArray(data.notice_groups) ? data.notice_groups : [];
    formData.value.processor_groups = Array.isArray(data.processor_groups) ? data.processor_groups : [];
  }, {
    immediate: isEditMode || isCloneMode,
  });

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-main');
</script>
<style lang="postcss" scoped>
.create-strategy-main {
  margin-bottom: 32px;
}

.create-notice-group {
  padding: 0 12px;
  text-align: center;
  flex: 1;
}

.refresh {
  padding: 0 12px;
  color: #3a84ff;
  text-align: center;
  cursor: pointer;
  border-left: 1px solid #dcdee5;
  flex: 1;
}
</style>
