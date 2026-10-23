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
        <render-info-item
          :label="t('套餐ID')"
          :label-width="labelWidth">
          {{ data.id }}
        </render-info-item>
      </render-info-block>
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item
          :label="t('套餐名称')"
          :label-width="labelWidth">
          {{ data.name }}
        </render-info-item>
      </render-info-block>
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item
          :label="t('执行动作')"
          :label-width="labelWidth">
          <i
            v-if="soapLoading"
            class="skeleton-bar is-v72"
            data-testid="package-detail-action-skeleton" />
          <template v-else>
            {{ soapList.find(item=>item.id === data.sops_template_id)?.name || '--' }}
          </template>
        </render-info-item>
      </render-info-block>
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item
          :label="t('执行前审批')"
          :label-width="labelWidth">
          {{ data.need_approve ? t('是'):t('否') }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        v-if="data.need_approve"
        style="margin-bottom: 16px;">
        <render-info-item
          :label="t('审批配置')"
          :label-width="labelWidth">
          <div class="approve-config-wrap">
            <render-info-item
              :label="t('审批流程')"
              :label-width="approveLabelWidth"
              style="min-height: 32px;align-items: flex-start;line-height: 32px;">
              <i
                v-if="serviceLoading"
                class="skeleton-bar is-v72"
                data-testid="package-detail-flow-skeleton" />
              <template v-else>
                {{ serviceName }}
              </template>
            </render-info-item>
            <p style="width: 93px;height: 32px;line-height: 32px;color: #313238;text-align: right;">
              {{ t('审批单信息') }}
            </p>
            <div
              v-if="detailLoading && !serviceLoading"
              data-testid="package-detail-approve-skeleton">
              <div
                v-for="row in approveSkeletonRows"
                :key="row"
                class="approve-skeleton-row">
                <span
                  class="approve-skeleton-label"
                  :style="approveLabelStyle">
                  <i class="skeleton-bar is-label" />
                </span>
                <i
                  class="skeleton-bar"
                  :class="row % 2 ? 'is-v48' : 'is-v72'" />
              </div>
            </div>
            <template v-else-if="filterDetailDataFields.length">
              <render-info-item
                v-for="item in filterDetailDataFields"
                :key="item.id"
                class="approve-info-item"
                :label="item.name"
                :label-width="approveLabelWidth"
                style="min-height: 32px;align-items: flex-start;line-height: 32px;">
                <span v-if="item.choice && item.choice.length">
                  {{ item.choice.find(choice => choice.key === approveValue(item.key))?.name
                    || approveValue(item.key)
                    || '--' }}
                </span>
                <span v-else>{{ approveValue(item.key) || '--' }}</span>
              </render-info-item>
            </template>
            <p
              v-else
              class="approve-empty">
              --
            </p>
          </div>
        </render-info-item>
      </render-info-block>
      <render-info-block style="margin-bottom: 16px;">
        <render-info-item
          :label="t('备注')"
          :label-width="labelWidth">
          {{ data.description || '--' }}
        </render-info-item>
      </render-info-block>
    </div>
  </bk-loading>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
    watch,
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
  const { t, locale } = useI18n();

  const labelWidth = computed(() => (locale.value === 'en-US' ? 100 : 80));
  const approveLabelWidth = computed(() => (locale.value === 'en-US' ? 100 : 84));
  const approveLabelStyle = computed(() => ({
    width: `${approveLabelWidth.value}px`,
    flex: `0 0 ${approveLabelWidth.value}px`,
  }));
  const approveSkeletonRows = [1, 2, 3];

  const approveValue = (key: string) => {
    const config = props.data?.approve_config;
    if (!config || typeof config !== 'object') return '';
    const field = config[key];
    if (field == null) return '';
    return field.value ?? '';
  };

  const serviceName = computed(() => {
    const serviceId = props.data?.approve_service_id;
    if (serviceId == null) return '--';
    const matched = (serviceList.value || []).find(item => String(item.id) === String(serviceId));
    return matched?.name || '--';
  });

  const filterDetailDataFields = computed(() => {
    const fields = detailData.value?.fields;
    if (!Array.isArray(fields)) return [] as ServiceField[];
    return fields.filter(item => item && !fieldMap.value[item.key]);
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
  });

  watch(() => props.data?.approve_service_id, (id) => {
    if (id == null) {
      detailData.value = null;
      return;
    }
    fetchServiceDetail({
      id: String(id),
    }).catch(() => {
      detailData.value = null;
    });
  }, { immediate: true });
</script>
<style scoped lang="postcss">
.process-detail-wrap {
  padding: 24px 32px;

  .approve-config-wrap {
    padding: 16px 24px;
    padding-left: 0;
    background-color: #f5f7fa;

    .render-info-item .info-label {
      /* flex: 0 0 120px !important; */
      width: 120px;
    }
  }

  .skeleton-bar {
    display: inline-block;
    height: 12px;
    vertical-align: middle;
    background: var(--audit-neutral-border-01);
    border-radius: var(--audit-radius-control);
    animation: package-detail-skeleton 1.2s ease-in-out infinite;
  }

  .skeleton-bar.is-v48 {
    width: 96px;
  }

  .skeleton-bar.is-v72 {
    width: 160px;
  }

  .skeleton-bar.is-label {
    width: 56px;
  }

  .approve-skeleton-row {
    display: flex;
    align-items: center;
    min-height: 32px;
    line-height: 32px;
  }

  .approve-skeleton-label {
    display: flex;
    justify-content: flex-end;
    padding-right: 12px;
  }

  .approve-empty {
    min-height: 32px;
    padding-left: 12px;
    line-height: 32px;
    color: #313238;
  }
}

@keyframes package-detail-skeleton {
  0%,
  100% {
    background: var(--audit-neutral-border-01);
  }

  50% {
    background: var(--audit-neutral-bg-01);
  }
}
</style>
