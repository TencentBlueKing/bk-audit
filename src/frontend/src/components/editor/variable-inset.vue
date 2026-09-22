<template>
  <bk-sideslider
    v-model:isShow="isShow"
    class="editor-variable-inset"
    quick-close
    :title="t('引用变量')"
    transfer
    :width="960">
    <div class="editor-variable-inset__body">
      <bk-tab
        v-model:active="active"
        type="card-grid">
        <bk-tab-panel
          :label="t('风险信息')"
          name="risk">
          <variable-field-list
            :fields="riskFields"
            @insert="handleInsert" />
        </bk-tab-panel>
        <bk-tab-panel
          :label="t('事件信息')"
          name="event">
          <variable-field-list
            :fields="eventFields"
            @insert="handleInsert" />
        </bk-tab-panel>
      </bk-tab>
    </div>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import VariableFieldList from './variable-field-list.vue';

  interface VariableField {
    id: string;
    name: string;
  }

  interface Props {
    visible: boolean;
    riskFields?: VariableField[];
    eventFields?: VariableField[];
  }

  interface Emits {
    (e: 'update:visible', value: boolean): void;
    (e: 'confirm', value: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    riskFields: () => [],
    eventFields: () => [],
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const isShow = ref(false);
  const active = ref('risk');

  const handleInsert = (variableText: string) => {
    emit('confirm', variableText);
  };

  watch(() => props.visible, (value) => {
    isShow.value = value;
    if (value) {
      active.value = 'risk';
    }
  }, { immediate: true });

  watch(isShow, (value) => {
    if (!value) {
      emit('update:visible', false);
    }
  });
</script>

<style lang="postcss" scoped>
.editor-variable-inset__body {
  margin-top: 10px;
}

.editor-variable-inset {
  :deep(.bk-modal-body) {
    background-color: #f5f7fa;
  }

  :deep(.bk-tab-content) {
    padding: 0;
  }

  :deep(.bk-tab-header) {
    margin-left: 40px;
  }
}
</style>
