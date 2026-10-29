/**
 * 工具广场「我的所有场景」分组
 * - 只按用户有权限的场景分组，避免从无权限场景打开工具时取到不可用的场景默认值
 * - 全部可见 / 全部场景可见的通用工具放入用户的每个场景分组
 */

export const UNCATEGORIZED_SCENE_GROUP_KEY = '0';

const ALL_SCENE_VISIBILITY_TYPES = ['all_visible', 'all_scenes'];

interface SceneGroupTool {
  visibility?: {
    visibility_type?: string;
    scene_ids?: number[];
  };
}

/**
 * 计算工具应归入的场景分组 ID
 * accessibleSceneIds 为 null 表示用户场景列表尚未就绪，此时按工具授权场景分组
 */
export const resolveToolGroupSceneIds = (
  tool: SceneGroupTool,
  accessibleSceneIds: number[] | null,
): number[] => {
  const visibilityType = tool.visibility?.visibility_type || '';
  const sceneIds = tool.visibility?.scene_ids || [];

  if (accessibleSceneIds === null) {
    return sceneIds;
  }
  if (ALL_SCENE_VISIBILITY_TYPES.includes(visibilityType)) {
    return accessibleSceneIds;
  }
  const accessibleSet = new Set(accessibleSceneIds.map(Number));
  return sceneIds.filter(id => accessibleSet.has(Number(id)));
};

/** 按场景分组：返回 { 分组 key: 工具列表 }，key 顺序为场景 ID 倒序，未归属任何场景的工具放在 '0' */
export const groupToolsByScene = <T extends SceneGroupTool>(
  tools: T[],
  accessibleSceneIds: number[] | null,
): Array<{ groupKey: string; tools: T[] }> => {
  const groupMap = new Map<string, T[]>();
  tools.forEach((tool) => {
    const groupSceneIds = resolveToolGroupSceneIds(tool, accessibleSceneIds);
    const keys = groupSceneIds.length
      ? groupSceneIds.map(id => String(id))
      : [UNCATEGORIZED_SCENE_GROUP_KEY];
    keys.forEach((key) => {
      if (!groupMap.has(key)) {
        groupMap.set(key, []);
      }
      groupMap.get(key)!.push(tool);
    });
  });
  return Array.from(groupMap.entries())
    .map(([groupKey, groupTools]) => ({ groupKey, tools: groupTools }))
    .sort((a, b) => Number(b.groupKey) - Number(a.groupKey));
};
