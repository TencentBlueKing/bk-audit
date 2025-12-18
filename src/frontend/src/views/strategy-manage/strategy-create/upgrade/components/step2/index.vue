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
  <smart-action>
    <card-part :title="t('方案设置')">
      <template #content>
        <bk-loading :loading="isEditDataLoading">
          <audit-form
            ref="formRef"
            form-type="vertical"
            :model="formData"
            :rules="rules"
            style="padding-bottom: 14px;">
            <aiops-part
              ref="aiopsRef"
              :control-detail="controlDetail"
              trigger-error
              @update-aiops-config="handleUpdateAiopsConfig"
              @update-data-source="handleUpdateDataSource" />
          </audit-form>
        </bk-loading>
      </template>
    </card-part>

    <template #action>
      <bk-button
        class="w88"
        @click="handlePrev">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        :loading="submitLoading"
        theme="primary"
        @click="handleSubmit">
        {{ t('确认升级') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>

<script setup lang='ts'>
  import { InfoBox } from 'bkui-vue';
  import _ from 'lodash';
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import ControlManageService from '@service/control-manage';
  import StrategyManageService from '@service/strategy-manage';

  import ControlModel from '@model/control/control';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import CardPart from '@views/strategy-manage/strategy-create/components/step1/components/card-part.vue';
  import AiopsPart from '@views/strategy-manage/strategy-create/components/step1/components/reference-model/components/aiops/index.vue';

  import { changeConfirm } from '@utils/assist';

  interface Emits{
    (e:'change', step: number): void,
  }

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { messageSuccess } = useMessage();

  const formRef = ref();
  const aiopsRef = ref();
  const formData = ref<Record<string, any>>({});
  const strategyTagMap = ref<Record<string, string>>({});
  const rules = {
    'configs.data_source.system_id': [
      {
        validator: (value: Array<string>) => !!value && value.length > 0,
        message: t('系统不能为空'),
        trigger: 'change',
      }],
    'configs.data_source.result_table_id': [
      {
        validator: (value: Array<string>) => !!value && value.length > 0,
        message: t('不能为空'),
        trigger: 'change',
      }],
    'configs.data_source.bk_biz_id': [
      {
        validator: (value: string) => !!value,
        message: t('所属业务不能为空'),
        trigger: 'change',
      }],
    // 检测条件
    'configs.agg_condition': [
      {
        validator: (val: Array<Record<string, any>>) => val.length > 0,
        message: t('检测条件不能为空'),
        trigger: 'none',
      },
    ],
    // 统计字段
    'configs.agg_dimension': [
      {
        validator: (value: Array<string>) => value.length > 0,
        message: t('统计字段不能为空'),
        trigger: 'change',
      },
    ],
    'configs.user_groups': [
      {
        validator: (value: Array<string>) => value.length > 0,
        message: t('通知组不能为空'),
        trigger: 'change',
      },
    ],
    'configs.agg_interval': [
      {
        validator: (value: Array<string>) => !!value,
        message: t('不能为空'),
        trigger: 'change',
      },
    ],
    'configs.algorithms.method': [
      {
        validator: (value: string) => !!value,
        message: t('不能为空'),
        trigger: 'change',
      },
    ],
    'configs.algorithms.threshold': [
      {
        validator: (value: number) => value || value === 0,
        message: t('不能为空'),
        trigger: 'change',
      },
    ],
    // 调度周期
    'configs.aiops_config.count_freq': [
      {
        validator: (value: number) => !!value,
        message: t('调度周期不能为空'),
        trigger: 'blur',
      },
    ],
    'configs.aiops_config.schedule_period': [
      {
        validator: (value: number) => !!value,
        message: t('不能为空'),
        trigger: 'change',
      },
    ],
  };

  // 获取标签列表
  useRequest(StrategyManageService.fetchStrategyTags, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      strategyTagMap.value = data.reduce<Record<string, string>>((acc, item) => {
        acc[item.tag_id] = item.tag_name;
        return acc;
      }, {});
    },
  });

  // 编辑状态获取数据
  const {
    loading: isEditDataLoading,
  } = useRequest(StrategyManageService.fetchStrategyList, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 1,
    },
    defaultParams: {
      page: 1,
      page_size: 1,
      strategy_id: route.params.strategyId,
    },
    manual: true,
    onSuccess: (data) => {
      [formData.value] = data.results;
      // 处理操作记录部分
      if (formData.value.configs.config_type === 'EventLog') {
        formData.value.configs.data_source.system_id = Object.keys(formData.value.configs.data_source.fields);
      }
      aiopsRef.value.setConfigs(formData.value.configs);
    },
  });

  // 获取方案详情
  const {
    data: controlDetail,
  } = useRequest(ControlManageService.fetchControlDetail, {
    defaultValue: new ControlModel(),
    defaultParams: {
      control_id: route.params.controlId,
    },
    manual: true,
  });
  const {
    loading: submitLoading,
    run: updateStrategy,
  } = useRequest(StrategyManageService.updateStrategy, {
    defaultValue: {},
    onSuccess() {
      window.changeConfirm = false;
      messageSuccess('升级成功');
      router.push({
        name: 'strategyList',
      });
    },
  });

  const handleSubmit = () => {
    const taskQueue = [formRef.value.validate(), aiopsRef.value.getValue()];
    Promise.all(taskQueue).then(() => {
      // 修改版本号
      formData.value.control_version = controlDetail.value.control_version;
      const params = { ...formData.value };
      const fields = aiopsRef.value.getFields();
      const tableIdList = params.configs.data_source.result_table_id;
      if (params.configs.config_type !== 'EventLog') {
        params.configs.data_source = {
          ...params.configs.data_source,
          fields,
          result_table_id: _.isArray(tableIdList) ?  _.last(tableIdList) : tableIdList,
        };
      } else {
        params.configs.data_source = {
          ...params.configs.data_source,
          fields,
        };
      }
      if (params.tags) {
        // eslint-disable-next-line max-len
        params.tags = params.tags.map((item: string) => (strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
      }
      InfoBox({
        title: t('升级确认'),
        subTitle: t('升级后将按照方案新版本设定的最新输出字段输出审计风险，请确认是否升级？'),
        cancelText: t('取消'),
        confirmText: t('确定'),
        headerAlign: 'center',
        contentAlign: 'center',
        footerAlign: 'center',
        onConfirm() {
          updateStrategy(params);
        },
      });
    });
  };

  const handleUpdateDataSource = (dataSource: Record<string, any>) => {
    formData.value.configs.data_source = {
      ...formData.value.configs.data_source,
      ...dataSource,
    };
  };
  const handleUpdateAiopsConfig = (aiopsConfig?: {
    count_freq: string,
    schedule_period: string,
  }) => {
    if (aiopsConfig) {
      formData.value.configs.aiops_config = {
        ...formData.value.configs.aiops_config,
        ...aiopsConfig,
      };
    } else {
      delete formData.value.configs.aiops_config;
    }
  };

  const handlePrev = () => {
    changeConfirm().then(() => {
      emits('change', 1);
    });
  };

  const handleCancel = () => {
    router.push({
      name: 'strategyEdit',
      params: {
        id: route.params.strategyId,
      },
    });
  };

</script>
<!-- <style scoped>

</style> -->
