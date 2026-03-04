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
  <bk-loading
    :loading="experienceLoading"
    style="display: inline-block;">
    <auth-button
      v-if="!isEdit"
      action-id="process_risk"
      :permission="data.permission.process_risk || data.current_operator.includes(userInfo.username)"
      :resource="data.risk_id"
      style="font-size: 12px;"
      text
      theme="primary"
      @click="handleAddRiskExperience">
      <audit-icon
        style="margin-right: 6px;"
        type="report" />
      {{ t('添加风险总结') }}
    </auth-button>
  </bk-loading>


  <!-- 弹窗  -->
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showSlider"
    :show-footer="false"
    show-header-slot
    title=""
    :width="960">
    <template #header>
      {{ isEdit ? t('编辑风险总结'): t('添加风险总结') }}
    </template>
    <div style="padding: 24px 40px;">
      <rich-editor
        v-model:content="content"
        :default="content"
        height="calc(100vh - 180px)" />

      <div class="mt16">
        <bk-button
          class="mr8"
          :loading="loading"
          style="height: 32px;"
          theme="primary"
          @click="handleSubmit">
          {{ t('提交') }}
        </bk-button>
        <bk-button
          style="height: 32px;"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </div>
    </div>
  </audit-sideslider>
  <risk-content-item
    v-for="(item,index) in experienceData"
    :key="item.id"
    class="mt16"
    :data="experienceData[index]"
    :show-edit-btn="myExperienceData === item"
    @edit="handleEditExperience" />
</template>

<script setup lang='ts'>
  import {
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import RiskExperienceManage from '@service/risk-experience-manage';

  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import RichEditor from '@components/rich-editor/index.vue';

  import { changeConfirm } from '@utils/assist';

  import RiskContentItem from './components/risk-content-item.vue';

  interface Emits{
    (e:'update'):void,
  }
  interface Props{
    data: RiskManageModel,
    userInfo: {
      username: string,
    }
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const showSlider = ref(false);
  const content = ref('');


  const myExperienceData = computed(() => experienceData.value
    .find(item => item.created_by === props.userInfo.username));
  // 判断自身是否添加过风险总结
  const isEdit = computed(() => {
    let res = Boolean(experienceData.value && experienceData.value.length);
    if (res) {
      res = !!myExperienceData.value;
    }
    return res;
  });

  // 获取风险总结
  const {
    run: fetchExperience,
    data: experienceData,
    loading: experienceLoading,
  } = useRequest(RiskExperienceManage.fetchExperience, {
    defaultValue: [],
  });
  // 保存风险总结
  const {
    run: saveExperience,
    loading,
  } = useRequest(RiskExperienceManage.saveExperience, {
    defaultValue: null,
    onSuccess() {
      window.changeConfirm = false;
      showSlider.value = false;
      emits('update');
      messageSuccess(isEdit.value ? t('编辑成功') : t('新建成功'));
    },
  });


  const handleSubmit = () => {
    if (content.value) {
      saveExperience({
        risk_id: props.data.risk_id,
        content: content.value,
      });
    }
  };
  const handleCancel = () => {
    changeConfirm()
      .then(() => {
        showSlider.value = false;
      });
  };
  const handleEditExperience = () => {
    if (!myExperienceData.value) return;
    content.value = myExperienceData.value.content;
    nextTick(() => {
      showSlider.value = true;
    });
  };
  // 打开风险总结
  const handleAddRiskExperience = () => {
    content.value = '';
    nextTick(() => {
      showSlider.value = true;
    });
  };
  watch(() => content.value, () => {
    if (content.value) {
      window.changeConfirm = true;
    }
  });
  watch(() => props.data, () => {
    if (props.data) {
      fetchExperience({
        risk_id: props.data.risk_id,
      });
    }
  }, {
    immediate: true,
  });
  watch(() => showSlider.value, () => {
    if (!showSlider.value) {
      window.changeConfirm = false;
    }
  }, {
    immediate: true,
  });
</script>
<!-- <style scoped>

</style> -->
