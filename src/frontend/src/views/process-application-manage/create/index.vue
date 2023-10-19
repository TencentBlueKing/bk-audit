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
<!-- eslint-disable vue/prefer-true-attribute-shorthand -->
<template>
  <div class="process-create-wrap">
    <smart-action
      class="create-application-page">
      <bk-loading :loading="fetchLoading">
        <audit-form
          ref="formRef"
          class="strategt-form"
          :label-width="80"
          :model="formData"
          :rules="rules">
          <bk-form-item
            class="is-required mr16"
            :label="t('套餐名称')"
            property="name">
            <bk-input
              v-model.trim="formData.name"
              :placeholder="t('请输入')"
              show-word-limit
              style="width: 480px;" />
          </bk-form-item>
          <div style="display: flex;">
            <bk-form-item
              class="mb0"
              :label="t('执行动作')"
              property="sops_template_id"
              required>
              <bk-select
                v-model="formData.sops_template_id"
                class="condition-equation"
                filterable
                :loading="soapLoading"
                :placeholder="t('请选择')"
                style="width: 480px;">
                <bk-option
                  v-for="(operatorItem, valueIndex) in soapList"
                  :key="valueIndex"
                  :label="operatorItem.name"
                  :value="operatorItem.id" />
              </bk-select>
            </bk-form-item>
            <a
              v-if="soapUrl"
              :href="soapUrl"
              style="padding-top: 8px;margin-left: 8px;"
              target="_blank">
              {{ t("查看动作详情") }}
            </a>
          </div>
          <bk-form-item
            class="mb0"
            label="">
            <p style="display: flex;align-items: center;">
              <bk-checkbox v-model="formData.need_approve" />
              <span style="margin-left: 4px;font-size: 12px; color: #63656E;">
                {{ t('执行前审批') }}
              </span>
            </p>
          </bk-form-item>
          <bk-form-item
            v-if="formData.need_approve"
            :label="t('审批配置')"
            required>
            <div class="approve-config-wrap">
              <div style="display: flex;">
                <bk-form-item
                  class="config-form-item"
                  :label="t('审批流程')"
                  label-position="left"
                  :label-width="configLabelWidth"
                  property="approve_service_id"
                  required
                  style="margin-bottom: 10px;margin-left: 7px;">
                  <bk-select
                    v-model="formData.approve_service_id"
                    class="condition-equation"
                    filterable
                    :loading="serviceLoading"
                    :placeholder="t('请选择')"
                    :style="configStyle"
                    @change="handleServiceChange">
                    <bk-option
                      v-for="(operatorItem, valueIndex) in serviceList"
                      :key="valueIndex"
                      :label="operatorItem.name"
                      :value="operatorItem.id" />
                  </bk-select>
                </bk-form-item>
                <a
                  v-if="serviceUrl"
                  :href="serviceUrl"
                  style="margin-left: 8px;"
                  target="_blank">
                  {{ t("查看流程") }}
                </a>
              </div>
              <bk-loading :loading="detailLoading">
                <template v-if="detailData && Object.keys(formData.approve_config).length">
                  <p style="padding-left: 6px;margin-top: -4px;">
                    {{ t('审批单信息') }}
                  </p>
                  <bk-form-item
                    v-for="item in filterDetailDataFields"
                    :key="item.id"
                    class="config-form-item mb0"
                    :label="item.name"
                    label-position="left"
                    :label-width="configLabelWidth"
                    :property="`approve_config.${item.key}.value`"
                    required
                    style="margin-left: 7px;">
                    <bk-select
                      v-if="item.type==='SELECT' && item.choice && item.choice.length"
                      v-model="formData.approve_config[item.key].value"
                      class="condition-equation"
                      filterable
                      :placeholder="t('请选择')"
                      :style="configStyle">
                      <bk-option
                        v-for="(operatorItem, valueIndex) in item.choice"
                        :key="valueIndex"
                        :label="operatorItem.name"
                        :value="operatorItem.key" />
                    </bk-select>
                    <bk-input
                      v-else-if="item.type==='TEXT'"
                      v-model="formData.approve_config[item.key].value"
                      :maxlength="100"
                      :placeholder="t('请输入')"
                      :style="configStyle"
                      type="textarea" />
                    <bk-input
                      v-else
                      v-model="formData.approve_config[item.key].value"
                      :placeholder="t('请输入')"
                      :style="configStyle" />
                  </bk-form-item>
                </template>
              </bk-loading>
            </div>
          </bk-form-item>
          <bk-form-item
            class="mb0"
            :label="t('备注')">
            <bk-input
              v-model="formData.description"
              :maxlength="100"
              :placeholder="t('请输入')"
              style="resize: none;"
              type="textarea" />
          </bk-form-item>
        </audit-form>
      </bk-loading>

      <template #action>
        <bk-button
          class="w88"
          :loading="submitLoading || updateLoading"
          style="margin-left: 80px;"
          theme="primary"
          @click="handleSubmit">
          {{ isEditMode ? t('保存') : t('提交') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="retToList">
          {{ t('取消') }}
        </bk-button>
      </template>
    </smart-action>
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

  import ItsmManageService from '@service/itsm-manage';
  import ProcessApplicationManageService from '@service/process-application-manage';
  import SoapManageService from '@service/soap-manage';

  import ProcessApplicationCreateModel from '@model/application/application-create';
  import type ServiceField from '@model/itsm/service-field';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useRouterBack from '@hooks/use-router-back';

  const route = useRoute();
  const router = useRouter();

  const isEditMode = route.name === 'processApplicationEdit';
  const isCloneMode = route.name === 'processApplicationClone';


  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const rules = {
    name: [
      {
        validator: (value: string) => !!value,
        message: t('套餐名称不能为空'),
        trigger: 'blur',
      },
    ],
    sops_template_id: [
      {
        validator: (value: string) => !!value,
        message: t('执行动作不能为空'),
        trigger: 'change',
      },
    ],
    need_approve: [
      {
        validator: (value: boolean) => value === true || value === false,
        message: t('执行要求不能为空'),
        trigger: 'change',
      },
    ],
    approve_service_id: [
      {
        validator: (value: string) => !!value,
        message: t('审批流程不能为空'),
        trigger: 'change',
      },
    ],
  };

  const formData = ref<Record<string, any>>(new ProcessApplicationCreateModel());
  const fieldMap = ref<Record<string, string>>({});
  const formRef = ref();
  const defaultLabelWidht = 68;
  const configLabelWidth = ref(defaultLabelWidht);

  const configStyle = computed(() => ({
    width: `${445 - configLabelWidth.value}px`,
    resize: 'none',
    'margin-left': '4px',
  }));
  const soapUrl = computed(() => {
    if (!formData.value.sops_template_id) return '';
    return soapList.value.find(item => item.id === formData.value.sops_template_id)?.url || '';
  });
  const serviceUrl = computed(() => {
    if (!formData.value.approve_service_id) return '';
    return serviceList.value.find(item => item.id === formData.value.approve_service_id)?.url || '';
  });
  const filterDetailDataFields = computed(() => {
    if (!detailData.value) return [] as ServiceField[];
    const { fields } = detailData.value;
    const res = fields.filter(item => !fieldMap.value[item.key]);
    return res;
  });

  // 获取内置字段
  useRequest(ProcessApplicationManageService.fetchInFields, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      fieldMap.value = data.reduce((res, item) => {
        res[item.id] = item.id;
        return res;
      }, {} as Record<string, string>);
    },
  });
  const {
    loading: fetchLoading,
  } = useRequest(ProcessApplicationManageService.fetchList, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 0,
    },
    defaultParams: {
      id: route.params.id,
      page: 1,
      page_size: 1,
    },
    manual: isEditMode || isCloneMode,
    onSuccess(data) {
      if (data.results.length) {
        formData.value = {
          ...data.results[0],
        };
        if (isCloneMode) {
          formData.value.name = `${formData.value.name}_copy`;
        }
        if (formData.value.approve_service_id) {
          fetchServiceDetail({
            id: formData.value.approve_service_id,
          });
        }
      }
    },
  });
  // 标准运维流程
  const {
    data: soapList,
    loading: soapLoading,
  } = useRequest(SoapManageService.fetchList, {
    defaultValue: [],
    manual: true,
  });

  // 服务列表
  const {
    data: serviceList,
    loading: serviceLoading,
  } = useRequest(ItsmManageService.fetchList, {
    defaultValue: [],
    manual: true,
  });
  // 服务详情
  const {
    data: detailData,
    loading: detailLoading,
    run: fetchServiceDetail,
  } = useRequest(ItsmManageService.fetchServiceDetail, {
    defaultValue: null,
    onSuccess() {
      if (!Object.keys(formData.value.approve_config).length) {
        formData.value.approve_config = filterDetailDataFields.value.reduce((res, item) => {
          res[item.key] = {
            value: '',
          };
          return res;
        }, {} as Record<string, any>);
        // 计算最大宽度
        configLabelWidth.value = defaultLabelWidht;
        let canvas: null | HTMLCanvasElement = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.font = '400 12px Microsoft YaHei';
          filterDetailDataFields.value.forEach((item) => {
            const { width } = ctx.measureText(item.name);
            configLabelWidth.value = Math.max(configLabelWidth.value, width + 22);
          });
        }
        canvas = null;
      }
    },
  });
  const {
    run: create,
    loading: submitLoading,
  } = useRequest(ProcessApplicationManageService.create, {
    defaultValue: null,
    onSuccess() {
      window.changeConfirm = false;
      messageSuccess('新建成功');
      retToList();
    },
  });
  const {
    run: update,
    loading: updateLoading,
  } = useRequest(ProcessApplicationManageService.update, {
    defaultValue: null,
    onSuccess() {
      window.changeConfirm = false;
      messageSuccess('编辑成功');
      retToList();
    },
  });

  // 审批流程改变
  const handleServiceChange = (id: string) => {
    if (id) {
      formData.value.approve_config = {};
      fetchServiceDetail({
        id,
      });
    } else {
      detailData.value = null;
    }
  };

  const handleSubmit = () => {
    formRef.value.validate()
      .then(() => {
        const submitAction = isEditMode ? update : create;
        submitAction(formData.value);
      });
  };
  const retToList = () => {
    router.push({
      name: 'applicationManageList',
    });
  };
  useRouterBack(() => {
    retToList();
  });
</script>

<style scoped lang="postcss">
.process-create-wrap{
  padding: 28px 24px;
  background-color: #fff;

  .approve-config-wrap{
    padding: 16px 24px;
    background-color: #F5F7FA;
  }

  :deep(.config-form-item .bk-form-label){
    padding-right: 0;

    /* margin-right: 8px; */
  }
}
</style>
