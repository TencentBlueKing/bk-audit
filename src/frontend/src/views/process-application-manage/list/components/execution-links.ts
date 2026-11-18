import type { Router } from 'vue-router';

import { getSceneContextQuery } from '@/utils/assist/scene-system-params';

const riskDetailLocation = (riskId: string, sceneId?: string) => {
  const query = sceneId
    ? {
      scene_id: String(sceneId),
      scope_id: String(sceneId),
      scope_type: 'scene',
    }
    : getSceneContextQuery();
  return {
    name: 'sceneRiskManageDetail',
    params: { riskId },
    query,
  };
};

export const openRiskDetail = (router: Router, riskId: string, sceneId?: string) => {
  if (!riskId) return;
  const href = router.resolve(riskDetailLocation(riskId, sceneId)).href;
  window.open(href, '_blank');
};

/** 打开标准运维任务，地址来自接口 sops_task_url。 */
export const openSopsTask = (url?: string) => {
  if (!url || !/^https?:\/\//i.test(url)) return;
  window.open(url, '_blank', 'noopener');
};
