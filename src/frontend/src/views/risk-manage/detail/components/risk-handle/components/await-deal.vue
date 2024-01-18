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
  <div class="risk-await-deal-wrap">
    <audit-form
      ref="formRef"
      :model="formData"
      :rules="rules">
      <bk-form-item
        :label="t('处理方法')"
        required>
        <bk-radio-group
          :model-value="formData.method"
          @change="handleChangeMethod">
          <bk-radio
            v-for="item in radioGroup"
            :key="item.id"
            :label="item.id">
            {{ t(item.name) }}
          </bk-radio>
        </bk-radio-group>
      </bk-form-item>

      <!-- 人工关单 -->
      <template v-if="formData.method === 'closeOrder'">
        <bk-form-item
          :label="t('处理说明')"
          property="description"
          required>
          <bk-input
            v-model.trim="formData.description"
            :maxlength="1000"
            :placeholder="t('请输入')"
            show-word-limit
            style="resize: none;"
            type="textarea" />
        </bk-form-item>
      </template>
      <!-- 转单 -->
      <template v-else-if="formData.method === 'transfer'">
        <bk-form-item
          :label="t('转单人员')"
          property="new_operators"
          required>
          <audit-user-selector
            v-model="formData.new_operators"
            :placeholder="t('请输入人员')" />
        </bk-form-item>
        <bk-form-item
          :label="t('处理说明')"
          property="description"
          required>
          <bk-input
            v-model.trim="formData.description"
            :maxlength="1000"
            :placeholder="t('请输入')"
            show-word-limit
            style="resize: none;"
            type="textarea" />
        </bk-form-item>
      </template>

      <!-- 处理套餐 -->
      <template v-else-if="formData.method === 'ProcessPackage'">
        <bk-form-item
          class="is-required mr16"
          :label="t('处理套餐', { text: 'Tools' })"
          property="pa_id">
          <bk-select
            v-model="formData.pa_id"
            filterable
            :loading="applicationLoading"
            :placeholder="t('请选择')"
            style="width: 480px;"
            @change="handlePaIdChange">
            <bk-option
              v-for="item in filterProcessApplicationList"
              :key="item.id"
              :label="item.name"
              :value="item.id" />
          </bk-select>
        </bk-form-item>
        <bk-loading :loading="detailLoading">
          <bk-form-item
            v-if="Object.keys(paramsDetailData)?.length"
            class="is-required mr16"
            :label="t('套餐参数')"
            property="pa_params">
            <div style="width: 976px;padding: 16px 12px;background: rgb(245 247 250 / 100%)">
              <template
                v-for="(val, index) in Object.values(paramsDetailData)"
                :key="`${val.key}-${index}`">
                <!-- 只显示需要显示的字段 -->
                <bk-form-item
                  v-if="val.show_type === 'show'"
                  :label="val.name"
                  :label-width="150"
                  :property="`pa_params.${val.key}.field`"
                  required
                  style="margin-bottom: 16px;">
                  <bk-select
                    v-model="formData.pa_params[val.key].field"
                    filterable
                    :placeholder="t('请选择')"
                    style="width: 480px;">
                    <bk-option
                      v-for="(item, conditionIndex) in riskFieldList"
                      :key="conditionIndex"
                      :label="item.name"
                      :value="item.id" />
                  </bk-select>
                </bk-form-item>
              </template>
            </div>
          </bk-form-item>
        </bk-loading>
        <bk-form-item
          class="mr16"
          label="">
          <bk-checkbox v-model="formData.auto_close_risk">
            <span style="font-size: 12px;">{{ t('套餐执行成功后自动关单') }}</span>
          </bk-checkbox>
        </bk-form-item>
      </template>
      <bk-form-item label="">
        <auth-button
          action-id="edit_risk_v2"
          :loading="loading"
          :permission="detailData.permission.edit_risk_v2 || detailData.current_operator.includes(userInfo.username)"
          :resource="detailData.risk_id"
          style="min-width: 72px;"
          theme="primary"
          @click="handleSubmit">
          {{ t('提交') }}
        </auth-button>
        <bk-button
          style="min-width: 72px;margin-left: 8px;"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </bk-form-item>
    </audit-form>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import ProcessApplicationManageService from '@service/process-application-manage';
  import RiskManageService from '@service/risk-manage';
  import SoapManageService from '@service/soap-manage';

  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  interface Props {
    riskId: string,
    detailData: RiskManageModel,
    userInfo: {
      username: string,
    }
  }
  interface Emits{
    (e:'update'): void,
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { messageSuccess } = useMessage();

  const rules = {
    new_operators: [{
      validator: (value: string) => !!value && value.length > 0,
      trigger: 'change',
      message: t('转单人不能为空'),
    }],
    description: [{
      validator: (value: string) => !!value,
      trigger: 'change',
      message: t('说明不能为空'),
    }],
    pa_id: [{
      validator: (value: string) => !!value,
      trigger: 'change',
      message: t('处理套餐不能为空'),
    }],
    pa_params: [
      {
        validator: (value: Record<string, any>) => Object.keys(value).length > 0
          && Object.values(value).every(item => !!item),
        message: t('套餐参数不能为空'),
        trigger: 'change',
      },
    ],
  };
  const radioGroup = [
    {
      id: 'closeOrder',
      name: t('人工关单'),
    },
    {
      id: 'transfer',
      name: t('转单'),
    },
    {
      id: 'ProcessPackage',
      name: t('处理套餐', { text: 'Tools' }),
    },
  ];

  const formData = ref<Record<string, any>>({
    method: 'closeOrder',
    risk_id: props.riskId,
  });
  const formRef = ref();
  const loading = computed(() => transLoading.value || autoProcessLoading.value || closeLoading.value);
  const filterProcessApplicationList = computed(() => processApplicationList.value
    .filter(item => item.is_enabled));

  const handlePaIdChange = (id: string) => {
    if (id) {
      const sopsTemplateId = processApplicationList.value
        .find(item => item.id === id)?.sops_template_id;
      fetchDetail({
        id: sopsTemplateId,
      });
    } else {
      paramsDetailData.value = {};
      formData.value.pa_params = {};
    }
  };

  //  获取风险可用字段
  const {
    data: riskFieldList,
  } = useRequest(RiskManageService.fetchFields, {
    defaultValue: [],
    manual: true,
  });
  // 获取处理套餐列表
  const {
    data: processApplicationList,
    loading: applicationLoading,
  } = useRequest(ProcessApplicationManageService.fetchApplicationsAll, {
    defaultValue: [],
    manual: true,
  });
  // 获取处理套餐详情
  const {
    run: fetchDetail,
    loading: detailLoading,
    data: paramsDetailData,
  } = useRequest(SoapManageService.fetchDetail, {
    defaultValue: {},
    onSuccess(data) {
      // 如果是新建 或者 pa_params为null
      formData.value.pa_params = {};
      Object.values(data).forEach((val) => {
        formData.value.pa_params[val.key] = {
          field: '',
        };
      });
    },
  });

  // 人工执行处理套餐
  const {
    run: autoProcess,
    loading: autoProcessLoading,
  } = useRequest(RiskManageService.autoProcess, {
    defaultValue: null,
    onSuccess() {
      // retToList();
      emits('update');
      messageSuccess(t('人工处理提交处理套餐成功'));
    },
  });
  // 人工关单
  const {
    run: close,
    loading: closeLoading,
  } = useRequest(RiskManageService.close, {
    defaultValue: null,
    onSuccess() {
      emits('update');
      messageSuccess(t('人工关单成功'));
    },
  });
  // 人工转单
  const {
    run: transRisk,
    loading: transLoading,
  } = useRequest(RiskManageService.transRisk, {
    defaultValue: null,
    onSuccess() {
      emits('update');
      messageSuccess(t('人工转单成功'));
    },
  });

  const handleChangeMethod = (val: string | number | boolean) => {
    let params = {};
    switch (val as string) {
    case 'closeOrder':
      params = {
        description: '',
      };
      break;
    case 'transfer':
      params = {
        description: '',
        new_operators: [],
      };
      break;
    case 'ProcessPackage':
      params = {
        pa_id: '',
        pa_params: {},
        auto_close_risk: false,
      };
      break;
    }
    formData.value = {
      method: val,
      ...params,
      risk_id: props.riskId,
    };
  };
  const handleSubmit = () => {
    formRef.value.validate().then(() => {
      switch (formData.value.method) {
      case 'closeOrder':
        close(formData.value);
        break;
      case 'transfer':
        transRisk({
          ...formData.value,
        });
        break;
      case 'ProcessPackage':
        autoProcess(formData.value);
        break;
      }
    });
  };
  const handleCancel = () => {
    router.push({
      name: route.name === 'riskManageDetail'
        ? 'riskManageList'
        : 'handleManageList',
    });
  };
</script>
<style scoped>
.risk-await-deal-wrap {
  padding: 10px 16px;
  font-size: 12px;
  background: #fff;
  border: 1px solid #eaebf0;
  border-radius: 6px;
  box-shadow: 0 2px 6px 0 #0000000a;
}
</style>
