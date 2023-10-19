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
  <bk-loading :loading="false">
    <div class="process-detail-wrap">
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item :label="t('套餐ID')">
          {{ data.id }}
        </render-info-item>
      </render-info-block>
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item :label="t('套餐名称')">
          {{ data.name }}
        </render-info-item>
      </render-info-block>
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item :label="t('执行动作')">
          <bk-loading :loading="soapLoading">
            {{ soapList.find(item=>item.id === data.sops_template_id)?.name || '--' }}
          </bk-loading>
        </render-info-item>
      </render-info-block>
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item :label="t('执行前审批')">
          {{ data.need_approve ? t('是'):t('否') }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        v-if="data.need_approve"
        style="margin-bottom: 16px;">
        <render-info-item
          :label="t('审批配置')">
          <bk-loading :loading="serviceLoading">
            <div class="approve-config-wrap">
              <render-info-item
                :label="t('审批流程')"
                :label-width="84"
                style="min-height: 32px;align-items: flex-start;line-height: 32px;">
                {{ serviceList.find(item=>item.id === data.approve_service_id)?.name || '--' }}
              </render-info-item>
              <p style="width: 93px;height: 32px;line-height: 32px;color: #313238;text-align: right;">
                {{ t('审批单信息') }}
              </p>
              <bk-loading :loading="detailLoading && !serviceLoading">
                <template v-if="detailData">
                  <render-info-item
                    v-for="item in filterDetailDataFields"
                    :key="item.id"
                    class="approve-info-item"
                    :label="item.name"
                    :label-width="84"
                    style="min-height: 32px;align-items: flex-start;line-height: 32px;">
                    <span v-if="item.choice && item.choice.length">
                      {{ item.choice.find(cItem=>cItem.key === data.approve_config[item.key]?.value )?.name
                        || data.approve_config[item.key]?.value
                        || '--' }}
                    </span>
                    <span v-else>{{ data.approve_config[item.key]?.value || '--' }}</span>
                  </render-info-item>
                </template>
              </bk-loading>
            </div>
          </bk-loading>
        </render-info-item>
      </render-info-block>
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item :label="t('备注')">
          {{ data.description || '--' }}
        </render-info-item>
      </render-info-block>
    </div>
  </bk-loading>
</template>

<script setup lang='ts'>
  import {
    computed,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ItsmManageService from '@service/itsm-manage';
  import ProcessApplicationManageService from '@service/process-application-manage';
  import SoapManageService from '@service/soap-manage';

  import type ProcessApplicationManageModel from '@model/application/application';
  import type ServiceField from '@model/itsm/service-field';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';

  import RenderInfoItem from './render-info-item.vue';

  const props = defineProps<Props>();
  const fieldMap = ref<Record<string, string>>({});
  interface Props{
    data: ProcessApplicationManageModel
  }
  const { t } = useI18n();
  const filterDetailDataFields = computed(() => {
    if (!detailData.value) return [] as ServiceField[];
    const { fields } = detailData.value;
    const res = fields.filter(item => !fieldMap.value[item.key]);
    return res;
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
  // 服务详情
  const {
    data: detailData,
    loading: detailLoading,
    run: fetchServiceDetail,
  } = useRequest(ItsmManageService.fetchServiceDetail, {
    defaultValue: null,
    // onSuccess(data) {
    //   console.log('fetchServiceDetail', data);
    // },
  });
  onMounted(() => {
    if (!props.data) return;
    if (props.data.approve_service_id) {
      fetchServiceDetail({
        id: props.data.approve_service_id,
      });
    }
  });
</script>
<style scoped lang="postcss">
.process-detail-wrap{
  padding: 24px 32px;

  .approve-config-wrap{
    padding: 16px 24px;
    padding-left: 0;
    background-color: #F5F7FA;

    .render-info-item .info-label{
      /* flex: 0 0 120px !important; */
      width: 120px;
    }
  }
}
</style>
