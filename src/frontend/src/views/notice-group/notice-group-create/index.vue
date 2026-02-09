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
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showCreate"
    :show-footer="false"
    :title="isEditMode ? t('编辑通知组') : t('新建通知组')"
    :width="960">
    <smart-action
      class="create-notice-group"
      :offset-target="getSmartActionOffsetTarget">
      <bk-loading :loading="isEditDataLoading">
        <audit-form
          ref="formRef"
          :model="formData"
          :rules="rules"
          :style="{'margin-left':marginOffset}">
          <bk-form-item
            class="is-required"
            :label="t('通知组名称')"
            label-width="135"
            property="group_name">
            <bk-input
              v-model="formData.group_name"
              class="form-item-common"
              :placeholder="t('请输入通知组名称')" />
          </bk-form-item>
          <bk-form-item
            class="is-required"
            :label="t('通知对象')"
            label-width="135"
            property="group_member">
            <user-variable-select-tenant
              class="form-item-common"
              :collapse-tags="collapseTags"
              :model-value="formData.group_member"
              :multiple="multiple"
              :placeholder="t('请输入用户名，或通过输入$使用变量')"
              @change="handleNoticeReceiver" />
            <bk-alert
              class="form-item-common mt8"
              theme="info"
              :title="t('处理套餐中使用了电话语音通知，拨打的顺序是按通知对象顺序依次拨打，用户组内无法保证顺序')" />
          </bk-form-item>
          <bk-form-item
            class="is-required"
            :label="t('通知方式')"
            label-width="135"
            property="notice_config">
            <div class="form-item-common">
              <table class="notice-table-content">
                <tr class="notice-table-title">
                  <!-- <td style="width: 115px;font-weight: bold;">
                    告警级别
                  </td> -->
                  <td
                    v-for="item in msgType"
                    :key="item.id">
                    <div>
                      <img
                        alt=""
                        height="16"
                        :src="getAssetsFile(`${item.id}.svg`)"
                        style="margin-right: 5px;vertical-align: sub;"
                        width="16">
                      <span>{{ t(item.name) }}</span>
                    </div>
                  </td>
                </tr>
                <tr
                  class="notice-table-value">
                  <td
                    v-for="msg in msgType"
                    :key="msg.id">
                    <bk-switcher
                      v-model="formData.notice_config[msg.id]"
                      size="small"
                      theme="primary" />
                  </td>
                </tr>
              </table>
            </div>
          </bk-form-item>
          <bk-form-item
            :label="t('说明')"
            label-width="135">
            <bk-input
              v-model="formData.description"
              class="form-item-common"
              :maxlength="100"
              :placeholder="t('请输入说明')"
              :rows="2"
              type="textarea" />
          </bk-form-item>
        </audit-form>
      </bk-loading>
      <template #action>
        <bk-button
          class="w88"
          :loading="isSubmiting || isEditSubmiting"
          theme="primary"
          @click="handleSubmit">
          {{ isEditMode?t('保存'):t('提交') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="closeDialog">
          {{ t('取消') }}
        </bk-button>
      </template>
    </smart-action>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import NoticeManageService from '@service/notice-group';

  import NoticeGroupsModel from '@model/notice/notice-group';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  // import UserVariableSelect from './user-variable-select.vue';
  import userVariableSelectTenant from './user-variable-select-tenant.vue';

  import getAssetsFile from '@/utils/getAssetsFile';

  interface NoticeWay{
    [key: string|number]: boolean
  }
  interface Emits {
    (e:'update'):void
  }
  interface Exposes {
    show(id?:number):void
  }
  const emits = defineEmits<Emits>();
  const { messageSuccess } = useMessage();
  const getSmartActionOffsetTarget = () => document.querySelector('.bk-form-content');
  const isEditMode = ref(false);
  const multiple = true;
  const formData = ref({
    group_id: 0,
    group_name: '',
    notice_config: {} as NoticeWay,
    group_member: [] as Array<string>,
    description: '',
  });
  const formRef = ref();
  const noticeWay = ref<Record<string, any>>({});
  const collapseTags = false;
  const { t, locale } = useI18n();
  const showCreate = ref(false);
  const marginOffset = ref(locale.value === 'zh-CN' ?  '-25px' : '-10px');
  const rules = {
    group_member: [
      {
        validator: (value: Array<any>) => value.length > 0,
        message: t('通知对象不能为空'),
        trigger: 'change',
      },
    ],
    group_name: [
      {
        validator: (value: Array<any>) => !!value,
        message: t('通知组名称不能为空'),
        trigger: 'blur',
      },
    ],
    notice_config: [
      {
        validator: (value: NoticeWay) => checkNoticeWay(value),
        message: t('通知方式不能为空'),
        trigger: 'change',
      },
    ],
  };

  // 保存告警组
  const {
    run: addGroup,
    loading: isSubmiting,
  } = useRequest(NoticeManageService.addGroup, {
    defaultValue: {},
    onSuccess: () => {
      window.changeConfirm = false;
      isEditMode.value ? messageSuccess(t('编辑成功')) : messageSuccess(t('新建成功'));
      showCreate.value = false;
      emits('update');
    },
  });
  const {
    run: updateGroup,
    loading: isEditSubmiting,
  } = useRequest(NoticeManageService.updateGroup, {
    defaultValue: {},
    onSuccess: () => {
      window.changeConfirm = false;
      messageSuccess(t('编辑成功'));
      showCreate.value = false;
      emits('update');
    },
  });

  // 格式化通知方式
  const filerNoticeWay = (value: Array<{
    msg_type: string
  }>) => {
    const noticeWay = value.reduce((result, item) => {
      // eslint-disable-next-line no-param-reassign
      result[item.msg_type] = true;
      return result;
    }, {} as NoticeWay);
    return noticeWay;
  };

  const {
    run: fetchRetriveGroup,
    loading: isEditDataLoading,
  } = useRequest(NoticeManageService.getGroupDetail, {
    defaultValue: new NoticeGroupsModel(),
    onSuccess: (data) => {
      formData.value.group_id = data.group_id;
      formData.value.group_name = data.group_name;
      formData.value.group_member = data.group_member;
      formData.value.notice_config = filerNoticeWay(data.notice_config);
      formData.value.description = data.description;
    },
  });

  // 校验通知方式
  const checkNoticeWay = (value: NoticeWay) => {
    let isCheck = false;
    const list = [] as Array<string>;
    Object.keys(value).forEach((item:string) => {
      if (value[item]) {
        list.push(item);
      }
    });
    isCheck = list.length > 0;
    noticeWay.value = list;
    return isCheck;
  };

  // 获取通知方式
  const {
    data: msgType,
  } = useRequest(NoticeManageService.fetchMsgType, {
    defaultValue: {},
    manual: true,
  });

  // 提交
  const handleSubmit = () => {
    formRef.value.validate().then((validator: any) => {
      if (!isEditMode.value) {
        // eslint-disable-next-line no-param-reassign
        delete validator.id;
      }
      const saveGroup = isEditMode.value ? updateGroup : addGroup;
      saveGroup({
        ...validator,
        notice_config: noticeWay.value.map((item: string) => ({
          msg_type: item,
        })),
      });
    });
  };

  // 接收通知对象
  const handleNoticeReceiver = (value: Array<string> | string) => {
    formData.value.group_member = value as string[];
  };
  const closeDialog = () => {
    showCreate.value = false;
  };

  defineExpose<Exposes>({
    show(id?: number) {
      formData.value = {
        group_id: 0,
        group_name: '',
        notice_config: {} as NoticeWay,
        group_member: [] as Array<string>,
        description: '',
      };
      showCreate.value = true;
      isEditMode.value = !!id;
      if (isEditMode.value) {
        fetchRetriveGroup({
          group_id: id,
        });
      }
    },
  });
</script>
<style lang="postcss" scoped>
.create-notice-group {
  padding: 24px;
  background-color: white;

  :deep(.bk-select .bk-select-trigger .bk-select-tag-input) {
    width: 330px;
  }

  .form-item-common {
    width: 800px;
  }

  .w88 {
    width: 88px;
  }

  .ml15 {
    margin-left: 15px;
  }

  .notice-table-content {
    width: 100%;
    text-align: center;
  }

  .show-input {
    display: flex;
  }

  .level-1 {
    padding: 0 8px;
    color: #eb3635;
    border-left: 5px solid #eb3635;
  }

  .level-2 {
    padding: 0 8px;
    color: #ff9c00;
    border-left: 5px solid #ff9c00;
  }

  .level-3 {
    padding: 0 8px;
    color: #3a84ff;
    border-left: 5px solid #3a84ff;
  }

  .notice-table-title {
    height: 42px;
    color: #63656e;
    text-align: center;
    background-color: #fafbfd;
  }

  .notice-table-value {
    padding: 5px 12px;
    color: #63656e;
    word-break: break-all;
  }

  .notice-table-content tr td {
    border-top: 1px solid #dcdee5;
    border-right: 1px solid #dcdee5;
    border-left: 1px solid #dcdee5;
  }

  .notice-table-content .notice-table-value td {
    padding: 10px;
  }

  .notice-table-content tr .border-left-none {
    border-left: none;
  }

  .notice-table-content tr .border-bottom {
    border-bottom: 1px solid #dcdee5;
  }

  .notice-table-content tr:last-child td {
    border-bottom: 1px solid #dcdee5;
  }
}
</style>
