<template>
  <div class="ai-report-edit-form">
    <bk-form
      form-type="vertical"
      label-width="80">
      <bk-form-item :label="t('报告名称')">
        <bk-input v-model="localTitle" />
      </bk-form-item>
      <bk-form-item :label="t('报告内容')">
        <rich-editor
          v-model:content="localContent"
          :default="localContent"
          height="calc(100vh - 300px)" />
      </bk-form-item>
    </bk-form>
  </div>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RichEditor from '@components/rich-editor/index.vue';

  interface Props {
    title: string;
    content: string;
  }

  interface Emits {
    (e: 'update:title', value: string): void;
    (e: 'update:content', value: string): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  const localTitle = ref(props.title);
  const localContent = ref(props.content);

  watch(() => props.title, (val:string) => {
    localTitle.value = val;
  });

  watch(() => props.content, (val:string) => {
    localContent.value = val;
  });

  watch(localTitle, (val:string) => {
    emit('update:title', val);
  });

  watch(localContent, (val:string) => {
    emit('update:content', val);
  });
</script>

<style scoped lang="postcss">
.ai-report-edit-form {
  width: 96%;
  margin-top: 16px;
  margin-left: 2%;
  background: #fff;
}
</style>

