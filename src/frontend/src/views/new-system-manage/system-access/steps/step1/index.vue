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
  <div
    v-if="showModelType"
    class="step1-box">
    <div
      v-if="!isNewSystem"
      class="step1-tip">
      <img
        class="remind-icon"
        src="@images/remind.svg">
      <span class="remind-text">{{ t('当前系统为从“权限中心”接入，在审计中心所做的变更将会完全同步至审计中心，请确认后操作') }}</span>
      <audit-icon
        class="close-icon"
        type="close" />
    </div>

    <bk-card
      class="step1-card"
      is-collapse>
      <template #icon>
        <div class="card-icon">
          <audit-icon
            class="angle-fill-down"
            type="angle-fill-down" />
        </div>
      </template>
      <template #header>
        <div class="card-header">
          {{ t('基础信息') }}
        </div>
      </template>

      <bk-form
        ref="baseFormRef"
        class="example"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <div class="form-item-box">
          <bk-form-item
            class="form-item"
            :label="t('系统ID')"
            property="instance_id"
            required>
            <bk-input
              v-model="formData.instance_id"
              clearable
              :disabled="isDisabled"
              :placeholder="t('请输入系统ID')" />
          </bk-form-item>

          <bk-form-item
            class="form-item form-item-right"
            :label="t('系统名称')"
            property="name"
            required>
            <bk-input
              v-model="formData.name"
              clearable
              :disabled="isDisabled"
              :placeholder="t('请输入系统名称')" />
          </bk-form-item>
        </div>
        <bk-form-item
          class="form-item-line"
          :label="t('管理员')"
          property="managers"
          :required="!isDisabled">
          <audit-user-selector
            :is-disabled="isDisabled"
            :model-value="formData.managers"
            @change="handlerManagersChange" />
        </bk-form-item>

        <bk-form-item
          class="form-item-line"
          :label="t('系统域名')"
          property="system_url"
          :required="!isDisabled">
          <bk-input
            v-model="formData.system_url"
            clearable
            :disabled="isDisabled"
            :placeholder="t('请输入可访问的域名')" />
        </bk-form-item>

        <bk-form-item
          class="form-item-line"
          :label="t('描述')">
          <bk-input
            v-model="formData.description"
            clearable
            :disabled="isDisabled"
            :placeholder="t('请输入')"
            :rows="6"
            type="textarea" />
        </bk-form-item>
      </bk-form>
    </bk-card>

    <bk-card
      class="step1-card"
      is-collapse>
      <template #icon>
        <div class="card-icon">
          <audit-icon
            class="angle-fill-down"
            type="angle-fill-down" />
        </div>
      </template>
      <template #header>
        <div class="card-header">
          {{ t('调用信息') }}
        </div>
      </template>

      <bk-form
        ref="callFormRef"
        class="example"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <bk-form-item
          class="form-item-line form-item-top"
          property="clients"
          required>
          <template #label>
            <span>{{ t("可访问客户端") }}</span>
            <bk-popover
              placement="top"
              theme="dark">
              <span
                class="item-right-tips"
                @click="handlerJumpLink">
                <audit-icon
                  class="jump-link"
                  type="jump-link" />
                <span>{{ t('去新建') }}</span>
              </span>
              <template #content>
                <div>{{ t('有权限调用权限中心获取或操作到该系统权限数') }}</div>
                <div>{{ t('据的客户端列表，即 app_code 列表。例如某系') }}</div>
                <div>{{ t('统由一个客户端注册，但是需要多个客户端都可以') }}</div>
                <div>{{ t('调用鉴权接口进行该系统的鉴权。') }}</div>
              </template>
            </bk-popover>
          </template>

          <div
            v-for="item in clientList"
            :key="item.id"
            class="item-concent">
            <bk-input
              v-model="item.value"
              clearable
              :disabled="isDisabled"
              :placeholder="t('请输入可访问客户端')" />
            <audit-icon
              v-if="!isDisabled"
              class="add-fill"
              type="add-fill"
              @click="addClient()" />
            <audit-icon
              v-if="clientList.length === 1 && !isDisabled"
              v-bk-tooltips="{ content: t('至少保留一个'), placement: 'top' }"
              class="reduce-fill"
              type="reduce-fill" />
            <audit-icon
              v-if="clientList.length > 1 && !isDisabled"
              class="reduce-fill"
              style="color: #979ba5;"
              type="reduce-fill"
              @click="deleteClient(item.id)" />
          </div>
        </bk-form-item>


        <bk-form-item
          class="form-item-line"
          property="callback_url"
          required>
          <template #label>
            <bk-popover
              placement="top"
              theme="light">
              <span>{{ t("资源实例回调地址") }}</span>
              <template #content>
                <div>资源，指资源类型，如果系统要对某些操作实现数据级（资源）的权限控制，则需引入资源。同</div>
                <div>时，审计中心会记录到数据级的操作。以下是资源、资源实例和日志的示例：</div>
                <div
                  stripe
                  style="width: 520px;margin-top: 10px;">
                  <bk-table
                    ref="refTable"
                    :data="popoverTable"
                    height="auto">
                    <bk-table-column
                      label="资源类型"
                      prop="type" />
                    <bk-table-column
                      label="资源实例"
                      prop="lv" />
                    <bk-table-column
                      label="操作"
                      prop="cz" />
                    <bk-table-column
                      label="记录日志描述"
                      prop="log" />
                  </bk-table>
                </div>

                <div style=" padding-top: 10px;padding-bottom: 10px;">
                  如果无资源实例或不准确，则无法实现数据级的审计，只能进行操作审计。
                </div>
                <h3>资源实例回调地址填写说明：</h3>
                <div>1、应用说明：审计中心会通过“回调地址”获取详细的资源实例</div>
                <div>2、此处填写是回调地址，格式要求是 HOST格式：scheme://netloc</div>
                <div>3、例如：我的系统是cmdb，可获取到资源实例的url为  http://cmdb.consul</div>
              </template>
            </bk-popover>
          </template>
          <bk-input
            v-model="formData.callback_url"
            clearable
            :disabled="isDisabled"
            :placeholder="t('请输入资源回调url')" />
        </bk-form-item>
      </bk-form>
    </bk-card>
  </div>


  <div
    v-else
    class="step1-select-model-type">
    <bk-alert theme="info">
      {{ t('接入系统需要通过「权限模型」来描述自身系统下的资源和操作，并定义他们之间的关系。后续接入系统在审计中心的操作日志上传将依赖权限模型的定义。') }}
      <a
        class="link-icon"
        href=""
        target="_blank">
        <audit-icon
          svg
          type="jump-link" />
        {{ t('查看详细说明') }}
      </a>
    </bk-alert>
    <div class="select-model-type-container">
      <div class="title">
        {{ t('你的系统模型属于以下哪种类型？') }}
      </div>
      <div>{{ t('请点击选择系统类型') }}</div>
      <div class="type-list">
        <div
          class="type-list-item"
          @click="handlerRouteChange('complex')">
          <h3 style="margin-bottom: 8px;">
            {{ t('复杂权限系统') }}
          </h3>
          <span>{{ t('需要严格控制到具体数据、资源的访问权限和操作范围。') }}</span>
        </div>
        <div
          class="type-list-item"
          @click="handlerRouteChange('simple')">
          <h3 style="margin-bottom: 8px;">
            {{ t('简单权限系统') }}
          </h3>
          <span>{{ t('仅涉及页面访问、操作级别的简单权限控制') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import SystemModel from '@model/meta/system';

  import useRequest from '@/hooks/use-request';

  interface Exposes {
    handlerFormData: () => void,
  }
  interface Emits {
    (e: 'handlerValidates', val: Record<string, any>): void
    (e: 'updateCanEditSystem', val: boolean): void
  }
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const callFormRef = ref();
  const baseFormRef = ref();
  const isDisabled = ref(false);

  const rules = {
    clients: [
      {
        validator: (value: string[]) => value.every(item => item.trim()),
        trigger: 'blur',
        message: t('可访问客户端存在空值'),
      },
    ],
  };
  const route = useRoute();
  const router = useRouter();
  const isNewSystem = ref(computed(() => route.query.isNewSystem === 'true'));
  const handlerJumpLink = () => {
    const configStr = sessionStorage.getItem('BK_AUDIT_CONFIG');
    if (configStr) {
      const link = JSON.parse(sessionStorage.getItem('BK_AUDIT_CONFIG') || '{}').third_party_system?.v3_system_create_url;
      window.open(link, '_blank');
    }
  };
  const showModelType = ref(computed(() => {
    if (Number(route.query.step) === 1.5) {
      return false;
    }
    return true;
  }));
  const popoverTable = ref([
    {
      type: '业务',
      lv: '王者荣耀',
      cz: '新增',
      log: '新增 1 个叫“王者荣耀”的业务',
    },
    {
      type: '业务',
      lv: '王者荣耀',
      cz: '新增',
      log: '新增 1 个叫“王者荣耀”的业务',
    },
    {
      type: '业务',
      lv: '王者荣耀',
      cz: '新增',
      log: '新增 1 个叫“王者荣耀”的业务',
    },
  ]);
  interface FormData {
    name: string;
    instance_id: string;
    callback_url: string;
    managers: string[];
    description: string;
    clients: string[];
    system_url: string;
  }

  const formData = ref<FormData>({
    name: '',
    instance_id: '',
    callback_url: '',
    managers: [],
    description: '',
    clients: [],
    system_url: '',
  });
  const clientList = ref([
    {
      id: 1,
      value: '',
    },
  ]);
  const handlerManagersChange = (val: string[]) => {
    formData.value.managers = val;
  };

  const handlerRouteChange = (type: string) => {
    router.replace({
      query: {
        ...route.query,
        step: 2,
        type,
      },
      params: {
        id: route.params.id,
      },
    });
  };
  // 添加客户端项
  const addClient = () => {
    // 生成新的唯一ID：当前最大ID+1
    const newId = Math.max(...clientList.value.map(item => item.id), 0) + 1;
    clientList.value.push({
      id: newId,
      value: '',
    });
  };

  // 删除客户端项
  const deleteClient = (id: number) => {
    // 过滤掉要删除的项
    clientList.value = clientList.value.filter(item => item.id !== id);
    // 如果删除后列表为空，则添加一个默认项
    if (clientList.value.length === 0) {
      clientList.value.push({
        id: 1,
        value: '',
      });
    }
  };

  // 表单验证
  const handlerFormData = async () => {
    try {
      // 同时验证两个表单
      await Promise.all([
        baseFormRef.value.validate(),
        callFormRef.value.validate(),
      ]);
      emit('handlerValidates', formData.value);
      return true; // 返回验证成功状态
    } catch (error) {
      return false; // 返回验证失败状态
    }
  };

  const {
    run: fetchSystemDetail,
  } = useRequest(MetaManageService.fetchSystemDetail, {
    defaultParams: [],
    defaultValue: new SystemModel(),
    onSuccess: (result) => {
      isDisabled.value = !(result.source_type === 'bk_audit');
      emit('updateCanEditSystem', isDisabled.value);
      clientList.value = result.clients.map((item: string, index: number) => ({
        id: index,
        value: item,
      }));
      formData.value.instance_id = result.system_id;
      formData.value.name = result.name;
      formData.value.managers = result.managers;
      formData.value.callback_url = result.callback_url;
      formData.value.system_url = result.system_url;
      formData.value.description = result.description;
    },
  });

  watch(() => clientList.value, (newData) => {
    formData.value.clients = newData.map(i => i.value);
  }, {
    deep: true,
  });

  watch(() => route, () => {
    nextTick(() => {
      if (route.query.systemId) {
        fetchSystemDetail({
          id: route.query.systemId,
        });
      }
      if (route.query.fromStep) {
        fetchSystemDetail({
          id: route.params.id,
        });
      }
    });
  }, {
    deep: true,
    immediate: true,
  });
  onMounted(() => {

  });

  defineExpose<Exposes>({
    handlerFormData,
  });
</script>

<style scoped lang="postcss">
.step1-box {
  position: absolute;
  left: 50%;
  width: 60%;
  margin-top: 10px;
  transform: translateX(-50%);

  .step1-tip {
    display: flex;
    height: 32px;
    padding: 0 12px;
    background: #fdf4e8;
    border: 1px solid #f9d090;
    border-radius: 2px;
    align-items: center;

    .remind-icon {
      width: 16px;
      height: 16px;
      margin-right: 8px;
    }

    .remind-text {
      font-size: 12px;
      letter-spacing: 0;
      color: #4d4f56;
    }

    .close-icon {
      position: absolute;
      right: 5px;
      font-size: 12px;
      color: #c4c6cc;
    }
  }

  .step1-card {
    margin-top: 10px;

    .card-header {
      height: 22px;
      margin-left: 5px;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0;
      color: #313238;
    }

    .example {
      .form-item-box {
        display: flex;
        width: 96%;
        margin-top: 10px;
        margin-left: 2%;

        .form-item {
          width: 50%;

        }

        .form-item-right {
          margin-left: 5%;
        }
      }

      .form-item-line {
        width: 96%;
        margin-left: 2%;
      }

      .form-item-top {
        margin-top: 10px;

        .item-right-tips {
          position: absolute;
          right: 60px;
          color: #3a84ff;

          .jump-link {
            color: #3a84ff;
          }
        }

        .item-concent {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 8px;

          .add-fill {
            margin-left: 8px;
            font-size: 15px;
            color: #4d4f56;
          }

          .reduce-fill {
            font-size: 15px;
            color: #dcdee5;
          }
        }
      }
    }
  }

}

.step1-select-model-type {
  padding: 16px 24px;

  .select-model-type-container {
    width: 45%;
    min-width: 840px;
    margin: 72px auto;
    text-align: center;

    .title {
      margin-bottom: 10px;
      font-size: 20px;
      line-height: 28px;
    }

    .type-list {
      display: flex;
      margin-top: 30px;
      text-align: left;
      justify-content: space-between;

      .type-list-item {
        width: 45%;
        padding: 24px;
        cursor: pointer;
        background: #fff;
        border-radius: 3px;
        box-shadow: 0 2px 4px 0 #0000001a, 0 2px 4px 0 #1919290d;
      }
    }
  }
}
</style>
