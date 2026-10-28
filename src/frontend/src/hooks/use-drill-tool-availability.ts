/*
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
*/
import { Button, InfoBox } from 'bkui-vue';
import { h, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';

import RootManageService from '@service/root-manage';
import SceneManageService from '@service/scene-manage';
import ToolManageService from '@service/tool-manage';

interface DrillToolConfig {
  tool: {
    uid: string;
  };
  drill_name?: string;
}

interface Options {
  /** 当前风险所属场景可见的工具（场景工具 + 对该场景可见的全局工具） */
  sceneTools: Ref<Array<{ uid: string }>>;
  /** 场景可见工具是否已加载完成，未加载完成时不拦截 */
  isSceneToolsLoaded: Ref<boolean>;
  getSceneId: () => number | string;
}

/**
 * 风险单据字段下钻：拦截未对当前场景开放的工具
 * 策略只能引用对其场景可见的工具，场景下不可见的只可能是未开放给该场景的全局工具
 */
export default function useDrillToolAvailability(options: Options) {
  const { t } = useI18n();

  const isToolAvailable = (uid: string) => options.sceneTools.value
    .some(item => String(item.uid) === String(uid));

  const getToolName = (config: DrillToolConfig) => ToolManageService.fetchToolsDetail({ uid: config.tool.uid })
    .then(detail => detail?.name || config.drill_name || config.tool.uid)
    .catch(() => config.drill_name || config.tool.uid);

  const getSceneName = () => {
    const sceneId = String(options.getSceneId() ?? '');
    return SceneManageService.fetchSceneAll()
      .then(scenes => scenes.find(scene => String(scene.scene_id) === sceneId)?.name || sceneId)
      .catch(() => sceneId);
  };

  const showUnavailableTip = async (configs: DrillToolConfig[]) => {
    const [toolNames, platformAdmins, sceneName] = await Promise.all([
      Promise.all(configs.map(getToolName)),
      RootManageService.config()
        .then(config => config.platform_admin_users || [])
        .catch(() => [] as string[]),
      getSceneName(),
    ]);
    const infoBox = InfoBox({
      type: 'warning',
      title: t('暂时无法使用'),
      subTitle: t('全局工具{tools}未对当前场景「{scene}」开放，暂时无法使用。如需使用，请联系平台管理员「{admins}」将「{scene}」加入该工具的可见范围', {
        tools: toolNames.map(name => `「${name}」`).join('、'),
        scene: sceneName,
        admins: platformAdmins.join(','),
      }),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      footer: () => h(Button, {
        theme: 'primary',
        onClick: () => infoBox.hide(),
      }, () => t('知道了')),
    });
  };

  /**
   * 过滤出当前场景可用的下钻工具；
   * 指定打开的工具不可用或没有可用工具时，弹出提示并返回 null
   */
  const resolveAvailableDrillConfig = <T extends DrillToolConfig>(drillConfig: T[], activeUid?: string): T[] | null => {
    if (!options.isSceneToolsLoaded.value) {
      return drillConfig;
    }
    const unavailableConfigs = drillConfig.filter(config => !isToolAvailable(config.tool.uid));
    if (!unavailableConfigs.length) {
      return drillConfig;
    }
    const activeConfig = activeUid
      ? unavailableConfigs.find(config => String(config.tool.uid) === String(activeUid))
      : undefined;
    const availableConfigs = drillConfig.filter(config => isToolAvailable(config.tool.uid));
    if (activeConfig || !availableConfigs.length) {
      showUnavailableTip(activeConfig ? [activeConfig] : unavailableConfigs);
      return null;
    }
    return availableConfigs;
  };

  return {
    resolveAvailableDrillConfig,
  };
}
