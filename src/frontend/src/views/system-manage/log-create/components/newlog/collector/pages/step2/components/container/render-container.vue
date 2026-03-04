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
  <div>
    <bk-form-item
      class="is-required"
      :label="t('集群选择')"
      property="bcs_cluster_id">
      <bk-loading
        class="form-item-common"
        :loading="isClustersListLoading">
        <bk-select
          v-model="formData.bcs_cluster_id"
          :clearable="false"
          filterable
          :input-search="false"
          :no-data-text="t('无数据')"
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择集群')"
          :search-placeholder="t('请输入关键字')"
          @change="handleChange">
          <bk-option
            v-for="item in clustersData"
            :key="item.id"
            :label="item.name"
            :value="item.id" />
        </bk-select>
      </bk-loading>
    </bk-form-item>
    <bk-form-item
      :label="t('采集配置')"
      property="yaml_config"
      required>
      <yaml
        ref="yamlRef"
        v-model:yamlData="formData.yaml_config"
        :data="data"
        :log-config-type="data.environment"
        @check-yaml="handleCheckYaml"
        @update:yaml-data="handeUpdate" />
    </bk-form-item>
  </div>
</template>
<script setup lang="ts">
  import {
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CollectorManageService from '@service/collector-manage';
  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  import type { TFormData } from '../../index.vue';

  import Yaml from './yaml.vue';

  interface Props {
    data: TFormData,
    isEditMode: boolean,
  }
  interface Emits{
    (e:'change', value: Props['data']): void
    (e: 'checkYaml', value: string): void
  }
  interface Exposes {
    getCheckConfigYaml: (value: string) => Promise<Record<string, any>>;
  }
  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const formData = ref({
    bcs_cluster_id: '',
    yaml_config: '',
  });
  const yamlRef = ref();
  // 集群数据
  const {
    loading: isClustersListLoading,
    data: clustersData,
    run: fetchListBcsClusters,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(MetaManageService.fetchListBcsClusters, {
    defaultValue: [],
    defaultParams: {
      bk_biz_id: props.data.bk_biz_id,
    },
  });

  // 切换容器环境获取yaml模板
  const {
    data: yamlData,
    run: fetchLogConfigType,
  } = useRequest(CollectorManageService.fetchLogConfigType, {
    defaultValue: {
      yaml_config: '',
    },
    onSuccess: (data) => {
      yamlData.value.yaml_config = decodeURIComponent(escape(atob(data.yaml_config)));
      if (!props.isEditMode) {
        formData.value.yaml_config =  yamlData.value.yaml_config;
        emits('change', {
          ...props.data,
          ...formData.value,
        });
      }
    },
  });

  // 切换容器环境获取yaml模板 检测语法
  const handleChange = (value: string) => {
    formData.value.bcs_cluster_id = value;
    emits('change', {
      ...props.data,
      ...formData.value,
    });
    if (value) {
      yamlRef.value.getCheckConfigYaml();
    }
  };
  const handleCheckYaml =  (value:string) => {
    emits('checkYaml', value);
  };
  const handeUpdate = () => {
    emits('change', {
      ...props.data,
      ...formData.value,
    });
  };
  // 监听切换业务获取集群
  watch(() => props.data.bk_biz_id, (id) => {
    formData.value.bcs_cluster_id = '';
    clustersData.value = [];
    if (id) {
      fetchListBcsClusters({
        bk_biz_id: props.data.bk_biz_id,
      });
    }
    emits('change', {
      ...props.data,
      ...formData.value,
    });
  }, {
    deep: true,
  });
  watch(() => props.data, (modelValue) => {
    if (modelValue) {
      formData.value.bcs_cluster_id = modelValue.bcs_cluster_id;
      formData.value.yaml_config = modelValue.yaml_config;
    }
  }, {
    deep: true,
    immediate: true,
  });
  // 监听切换容器环境
  watch(() => props.data.environment, (environment) => {
    if (environment) {
      fetchLogConfigType({
        log_config_type: environment,
      });
    }
  }, {
    deep: true,
    immediate: true,
  });
  onMounted(() => {
    if (props.data.bk_biz_id) {
      fetchListBcsClusters({
        bk_biz_id: props.data.bk_biz_id,
      });
    }
  });
  defineExpose<Exposes>({
    getCheckConfigYaml() {
      return yamlRef.value.getCheckConfigYaml();
    },
  });
</script>
