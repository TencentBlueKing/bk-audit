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
  <bk-sideslider
    :before-close="handleBeforeClose"
    :esc-close="false"
    :is-show="isShow"
    :show-mask="false"
    :title="isEditMode ? t('编辑场景') : t('新建场景')"
    :width="740"
    @closed="handleClose">
    <template #default>
      <div class="create-scene-content">
        <bk-form
          ref="formRef"
          form-type="vertical"
          :model="formData"
          :rules="formRules">
          <!-- 场景名称 -->
          <bk-form-item
            :label="t('场景名称')"
            property="name"
            required>
            <bk-input
              v-model="formData.name"
              :placeholder="t('请输入')" />
          </bk-form-item>

          <!-- 场景管理员 -->
          <bk-form-item
            property="managers"
            required>
            <template #label>
              <bk-popover
                placement="top"
                theme="dark">
                <span class="label-tips">{{ t('场景管理员') }}</span>
                <template #content>
                  <div>{{ t('拥有场景的完整管理权限，包括策略配置、数据源管理、成员管理等') }}</div>
                </template>
              </bk-popover>
            </template>
            <audit-user-selector
              v-model="formData.managers"
              :auto-focus="false"
              :collapse-tags="false"
              multiple />
          </bk-form-item>

          <!-- 场景描述 -->
          <bk-form-item
            :label="t('场景描述')"
            property="description">
            <bk-input
              v-model="formData.description"
              :maxlength="100"
              :placeholder="t('请输入')"
              :rows="3"
              show-word-limit
              type="textarea" />
          </bk-form-item>

          <!-- 场景使用者 -->
          <bk-form-item
            property="users">
            <template #label>
              <bk-popover
                placement="top"
                theme="dark">
                <span class="label-tips">{{ t('场景使用者') }}</span>
                <template #content>
                  <div>{{ t('仅拥有场景下资源的只读使用权限（检索、报表、工具），无法更改场景配置') }}</div>
                </template>
              </bk-popover>
            </template>
            <audit-user-selector
              v-model="formData.users"
              :auto-focus="false"
              :collapse-tags="false"
              multiple />
          </bk-form-item>

          <!-- 关联系统 -->
          <bk-form-item
            property="system_id">
            <template #label>
              <bk-popover
                placement="top"
                theme="dark">
                <span class="label-tips">{{ t('关联系统') }}</span>
                <template #content>
                  <div>{{ t('关联「系统接入」中已接入系统的操作数据，场景可基于此数据进行检索、配置策略、生成报表') }}</div>
                </template>
              </bk-popover>
            </template>
            <bk-select
              v-model="formData.system_id"
              :clearable="false"
              collapse-tags
              filterable
              :loading="systemLoading"
              multiple
              multiple-mode="tag"
              :placeholder="t('请选择')"
              show-all
              @change="handleSystemChange">
              <bk-option
                v-for="item in systemList"
                :key="item.system_id"
                :label="item.name"
                :value="item.system_id" />
            </bk-select>
          </bk-form-item>

          <!-- 关联数据表 -->
          <bk-form-item
            property="table_id">
            <template #label>
              <bk-popover
                placement="top"
                theme="dark">
                <span class="label-tips">{{ t('关联数据表') }}</span>
                <template #content>
                  <div>{{ t('授权审计中心的数据表给场景使用，场景管理员可基于数据表配置审计策略、在工具广场创建 SQL 工具。注：数据表数据不在「检索」菜单中展示') }}</div>
                </template>
              </bk-popover>
            </template>
            <bk-select
              v-model="formData.table_id"
              :clearable="false"
              :disabled="!formData.system_id"
              filterable
              :loading="tableLoading"
              :placeholder="t('请选择')">
              <bk-option
                v-for="item in tableList"
                :key="item.id"
                :label="item.name"
                :value="item.id" />
            </bk-select>
          </bk-form-item>
        </bk-form>
      </div>
    </template>
    <template #footer>
      <bk-button
        class="mr8"
        :loading="submitLoading"
        theme="primary"
        @click="handleSubmit">
        {{ t('提交') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import {
    computed,
    ref,
    watch  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';
  import SceneManageService from '@service/scene-manage';

  import SystemModel from '@model/meta/system';
  import SceneModel from '@model/scene/scene';

  import useMessage from '@hooks/use-message';

  import AuditUserSelector from '@components/audit-user-selector/index.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    isShow: boolean;
    sceneId?: string | number;
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'success'): void;
  }

  interface FormData {
    name: string;
    managers: string[];
    description: string;
    users: string[];
    system_id: string[];
    table_id: string;
  }


  interface TableItem {
    id: string;
    name: string;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  // 编辑模式判断
  const isEditMode = computed(() => !!props.sceneId);

  const formRef = ref();
  const submitLoading = ref(false);
  const systemLoading = ref(false);
  const tableLoading = ref(false);

  // 系统列表
  const systemList = ref<SystemModel[]>([]);
  // 数据表列表
  const tableList = ref<TableItem[]>([]);

  // 表单数据
  const formData = ref<FormData>({
    name: '',
    managers: [],
    description: '',
    users: [],
    system_id: [] as string[],
    table_id: '',
  });

  // 表单校验规则
  const formRules = {
    name: [
      {
        required: true,
        message: t('场景名称不能为空'),
        trigger: 'blur',
      },
    ],
    managers: [
      {
        required: true,
        message: t('场景管理员不能为空'),
        trigger: 'blur',
      },
    ],
  };


  // 关联系统变更
  const handleSystemChange = () => {
    formData.value.table_id = '';
    if (formData.value.system_id.length > 0) {
      fetchTableList();
    } else {
      tableList.value = [];
    }
  };

  // 获取系统列表
  const {
    run: fetchSystemList,
  } = useRequest(MetaManageService.fetchSystemList, {
    defaultValue: {
      results: [] as SystemModel[],
      page: 1,
      num_pages: 1000,
      total: 0,
    },
    onSuccess: (res) => {
      systemList.value = res.results;
      // 编辑模式下，系统列表加载完成后回填关联系统
      if (isEditMode.value && props.sceneId) {
        fetchSceneDetail(props.sceneId as any);
      } else {
        resetForm();
      }
    },
  });
  // 获取数据表列表
  const fetchTableList = async () => {
    tableLoading.value = true;
    try {
      tableList.value = [];
    } finally {
      tableLoading.value = false;
    }
  };

  // 重置表单
  const resetForm = () => {
    formData.value = {
      name: '',
      managers: [],
      description: '',
      users: [],
      system_id: [],
      table_id: '',
    };
    tableList.value = [];
  };

  // 关闭前确认
  const handleBeforeClose = (): boolean | Promise<boolean> => {
    // 检查是否有未保存的数据
    const hasData = formData.value.name
      || formData.value.managers.length > 0
      || formData.value.description
      || formData.value.users.length > 0
      || formData.value.system_id.length > 0
      || formData.value.table_id;

    if (hasData) {
      return new Promise<boolean>((resolve) => {
        // 可以使用 InfoBox 确认
        resolve(true);
      });
    }
    return true;
  };

  // 创建场景
  const {
    run: createScene,
  } = useRequest(SceneManageService.createScene, {
    defaultValue: new SceneModel(),
    onSuccess: () => {
      messageSuccess(t(isEditMode.value ? '编辑成功' : '创建成功'));
      emits('success');
      handleClose();
    },
  });

  // 编辑场景
  const {
    run: updateScene,
  } = useRequest(SceneManageService.updateScene, {
    defaultValue: new SceneModel(),
    onSuccess: () => {
      messageSuccess(t('编辑成功'));
      emits('success');
      handleClose();
    },
  });

  // 获取场景详情
  const {
    run: fetchSceneDetail,
  } = useRequest(SceneManageService.fetchSceneDetail, {
    defaultValue: new SceneModel(),
    onSuccess: (res) => {
      fillFormFromSceneData(res);
    },
  });

  // 编辑模式下回填表单基础字段
  const fillFormFromSceneData = (data: SceneModel) => {
    formData.value = {
      name: data.name || '',
      managers: data.managers || [],
      description: data.description || '',
      users: data.users || [],
      system_id: data.systems.map(item => item.system_id),
      table_id: '',
    };
  };

  // 判断是否选择了"全部"
  const isSelectAllSystems = computed(() => {
    // show-all 模式下，选中全部时 system_id 会包含一个特殊标记或与系统列表长度一致
    const selected = formData.value.system_id;
    return selected.length > 0 && selected.includes('__ALL__');
  });

  // 构建 systems 参数
  const buildSystemsParam = () => {
    if (isSelectAllSystems.value) {
      // 选择全部时，返回完整系统列表
      return systemList.value.map(item => ({
        system_id: item.system_id,
        is_all_systems: true,
        filter_rules: '',
      }));
    }
    return formData.value.system_id.map(id => ({
      system_id: id,
      is_all_systems: false,
      filter_rules: '',
    }));
  };

  // 提交表单
  const submitParams = () => ({
    scene_id: typeof props.sceneId === 'number' ? props.sceneId : undefined,
    name: formData.value.name,
    description: formData.value.description || undefined,
    managers: formData.value.managers as string[],
    users: (formData.value.users as string[]).length > 0 ? (formData.value.users as string[]) : undefined,
    systems: buildSystemsParam(),
    tables: [],
  });

  const handleSubmit = async () => {
    try {
      await formRef.value?.validate();
      if (isEditMode.value) {
        if (!props.sceneId) return;
        updateScene({
          id: props.sceneId,
          ...submitParams(),
        } as any);
      } else {
        createScene(submitParams() as any);
      }
    } catch (e) {
      console.error('表单校验失败', e);
    }
  };

  // 取消
  const handleCancel = () => {
    emits('update:isShow', false);
  };

  // 关闭
  const handleClose = () => {
    resetForm();
    emits('update:isShow', false);
  };


  // 监听显示状态，打开时加载系统列表
  watch(() => props.isShow, (val) => {
    if (val) {
      fetchSystemList();
    }
  });
</script>

<style lang="postcss" scoped>
.create-scene-content {
  padding: 24px 40px;

  .form-item-tips {
    margin-top: 4px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  :deep(.label-tips) {
    cursor: pointer;
    border-bottom: 1px dashed #979ba5;
  }
}

.mr8 {
  margin-right: 8px;
}
</style>
