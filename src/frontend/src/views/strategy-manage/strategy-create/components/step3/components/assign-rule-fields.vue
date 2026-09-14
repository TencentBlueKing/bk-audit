<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="assign-rule-fields">
    <div class="form-section">
      <div class="form-label is-required">
        {{ t('分派场景空间') }}
      </div>
      <bk-select
        v-model="selectedSceneId"
        filterable
        :placeholder="t('请选择')">
        <bk-option
          v-for="item in sceneOptions"
          :key="item.id"
          :label="item.name"
          :value="item.id" />
      </bk-select>
    </div>

    <div class="form-section form-section-row">
      <div class="form-section-col">
        <div class="form-label is-required">
          {{ t('风险单处理人') }}
        </div>
        <notice-group-select
          v-model="localValue.processors"
          :check-result-map="checkResultMap"
          :disabled="!selectedSceneId"
          :group-list="groupList"
          :loading="isGroupLoading"
          :scene-id="selectedSceneId"
          @refresh="refreshGroupList" />
      </div>
      <div class="form-section-col">
        <div class="form-label">
          {{ t('关注人') }}
        </div>
        <notice-group-select
          v-model="localValue.notice_users"
          :check-result-map="checkResultMap"
          :disabled="!selectedSceneId"
          :group-list="groupList"
          :loading="isGroupLoading"
          :scene-id="selectedSceneId"
          @refresh="refreshGroupList" />
      </div>
    </div>

    <div class="form-section">
      <div class="form-label">
        {{ t('风险单分派方式') }}
      </div>
      <bk-radio-group v-model="localValue.assign_mode">
        <bk-radio label="confirm">
          {{ t('确认后分派') }}
        </bk-radio>
        <bk-radio label="direct">
          {{ t('直接分派') }}
        </bk-radio>
      </bk-radio-group>
    </div>

    <div
      v-if="localValue.assign_mode === 'confirm'"
      class="form-section">
      <div class="form-label is-required">
        {{ t('确认人') }}
      </div>
      <notice-group-select
        v-model="localValue.confirmers"
        :check-result-map="checkResultMap"
        :disabled="!selectedSceneId"
        :group-list="groupList"
        :loading="isGroupLoading"
        :scene-id="selectedSceneId"
        @refresh="refreshGroupList" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import IamManageService from '@service/iam-manage';
  import NoticeManageService from '@service/notice-group';

  import useRequest from '@/hooks/use-request';

  import NoticeGroupSelect from './notice-group-select.vue';

  interface RuleFields {
    scene_ids: Array<string | number>;
    processors: Array<string | number>;
    notice_users: Array<string | number>;
    assign_mode: 'confirm' | 'direct';
    confirmers: Array<string | number>;
  }

  interface Props {
    modelValue: RuleFields;
    sceneOptions: Array<{ id: string | number; name: string }>;
  }

  interface Emits {
    (e: 'update:modelValue', value: RuleFields): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const localValue = computed({
    get: () => props.modelValue,
    set: value => emits('update:modelValue', value),
  });

  const selectedSceneId = computed({
    get: () => props.modelValue.scene_ids?.[0] ?? '',
    set: (val: string | number | '') => {
      emits('update:modelValue', {
        ...props.modelValue,
        scene_ids: val === '' || val === null || val === undefined ? [] : [val],
      });
    },
  });

  const checkResultMap = ref<Record<string, boolean>>({});

  const {
    loading: isGroupLoading,
    data: groupList,
    run: fetchGroupList,
  } = useRequest(NoticeManageService.fetchGroupSelectList, {
    defaultValue: [],
  });

  const {
    run: fetchPermissionCheck,
  } = useRequest(IamManageService.check, {
    defaultValue: {},
    onSuccess: (data) => {
      checkResultMap.value = data || {};
    },
  });

  const hasSceneId = (sceneId: unknown): sceneId is string | number => (
    sceneId !== '' && sceneId !== null && sceneId !== undefined
  );

  const loadSceneRelatedData = (sceneId: string | number | '') => {
    if (!hasSceneId(sceneId)) {
      groupList.value = [];
      checkResultMap.value = {};
      return;
    }
    fetchGroupList({ scene_id: sceneId });
    fetchPermissionCheck({
      action_ids: 'list_notice_group_v2,create_notice_group_v2',
      resources: sceneId,
    });
  };

  const refreshGroupList = () => {
    if (!selectedSceneId.value) return;
    groupList.value = [];
    fetchGroupList({ scene_id: selectedSceneId.value });
  };

  watch(
    () => props.modelValue.scene_ids?.[0],
    (sceneId, prevSceneId) => {
      if (!hasSceneId(sceneId)) {
        groupList.value = [];
        checkResultMap.value = {};
        // 用户清空场景时，通知组一并清空；编辑回填（prev 为空）不能清
        if (hasSceneId(prevSceneId)) {
          emits('update:modelValue', {
            ...props.modelValue,
            processors: [],
            notice_users: [],
            confirmers: [],
          });
        }
        return;
      }
      loadSceneRelatedData(sceneId);
      // 首次从空回填到有场景，不算用户切换
      if (!hasSceneId(prevSceneId)) {
        return;
      }
      if (`${sceneId}` !== `${prevSceneId}`) {
        emits('update:modelValue', {
          ...props.modelValue,
          processors: [],
          notice_users: [],
          confirmers: [],
        });
      }
    },
    { immediate: true },
  );
</script>
<style lang="postcss" scoped>
.assign-rule-fields {
  .form-section {
    margin-bottom: 20px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .form-section-row {
    display: flex;
    gap: 16px;
  }

  .form-section-col {
    flex: 1;
    min-width: 0;
  }

  .form-label {
    margin-bottom: 8px;
    font-size: 12px;
    color: #63656e;

    &.is-required::before {
      display: inline-block;
      width: 8px;
      color: #ea3636;
      text-align: center;
      content: '*';
    }
  }
}
</style>
