<template>
  <div class="step1-box">
    <div class="step1-tip">
      <img
        class="remind-icon"
        src="@images/remind.svg">
      <span class="remind-text">当前系统为从“权限中心”接入，在审计中心所做的变更将会完全同步至审计中心，请确认后操作</span>
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
          基础信息
        </div>
      </template>

      <bk-form
        ref="formRef"
        class="example"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <div class="form-item-box">
          <bk-form-item
            class="form-item"
            label="系统 ID"
            required>
            <bk-input
              v-model="formData.id"
              clearable
              placeholder="请输入系统 ID" />
          </bk-form-item>
          <bk-form-item
            class="form-item form-item-right"
            label="系统名称"
            property="name"
            required>
            <bk-input
              v-model="formData.name"
              clearable
              placeholder="请输入系统名称" />
          </bk-form-item>
        </div>

        <bk-form-item
          class="form-item-line"
          label="管理员"
          required>
          <audit-user-selector :model-value="formData.user" />
        </bk-form-item>
        <bk-form-item
          class="form-item-line"
          label="系统域名"
          required>
          <bk-input
            v-model="formData.name"
            clearable
            placeholder="请输入可访问的域名" />
        </bk-form-item>
        <bk-form-item
          class="form-item-line"
          label="描述">
          <bk-input
            v-model="formData.name"
            clearable
            placeholder="请输入"
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
          调用信息
        </div>
      </template>

      <bk-form
        ref="formRef"
        class="example"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <bk-form-item
          class="form-item-line form-item-top"
          property="kh"
          required>
          <template #label>
            <span>{{ t("可访问客户端") }}</span>
            <bk-popover
              placement="top"
              theme="dark">
              <span class="item-right-tips">
                <audit-icon
                  class="jump-link"
                  type="jump-link" />
                <span>去新建</span>
              </span>
              <template #content>
                <div>有权限调用权限中心获取或操作到该系统权限数</div>
                <div>据的客户端列表，即 app_code 列表。例如某系</div>
                <div>统由一个客户端注册，但是需要多个客户端都可以</div>
                <div>调用鉴权接口进行该系统的鉴权。</div>
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
              placeholder="请输入可访问客户端" />
            <audit-icon
              class="add-fill"
              type="add-fill"
              @click="addClient()" />
            <audit-icon
              v-if="clientList.length === 1"
              v-bk-tooltips="{ content: '至少保留一个', placement: 'top' }"
              class="reduce-fill"
              type="reduce-fill" />
            <audit-icon
              v-if="clientList.length > 1"
              class="reduce-fill"
              style="color: #979ba5;"
              type="reduce-fill"
              @click="deleteClient(item.id)" />
          </div>
        </bk-form-item>
        <bk-form-item
          class="form-item-line"
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
            v-model="formData.name"
            clearable
            placeholder="请输入资源回调url" />
        </bk-form-item>
      </bk-form>
    </bk-card>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  //   import { useRoute, useRouter } from 'vue-router';

  const { t } = useI18n();
  //   const router = useRouter();
  //   const route = useRoute();
  const formRef = ref('');
  const rules = ref({});
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
  const formData = ref({
    name: '',
    id: '',
    user: [],
    kh: [],
  });
  const clientList = ref([
    {
      id: 1,
      value: '',
    },
  ]);
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
</style>
