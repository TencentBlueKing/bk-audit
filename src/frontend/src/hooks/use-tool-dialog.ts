import { nextTick, ref } from 'vue';

/**
 * 工具下钻配置项接口
 */
export interface DrillDownItem {
  raw_name: string;
  display_name: string;
  description: string;
  drill_config: Array<{
    tool: {
      uid: string;
      version: number;
    };
    config: Array<{
      source_field: string;
      target_value_type: string;
      target_value: string;
    }>
  }>;
}

/**
 * 工具使用相关的hooks
 * 封装了工具打开、下钻等重复逻辑
 */
export function useToolDialog() {
  // 所有已打开的工具数据
  const allOpenToolsData = ref<string[]>([]);

  // 对话框引用
  const dialogRefs = ref<Record<string, any>>({});

  /**
   * 下钻打开工具
   * @param drillDownItem 下钻配置信息
   * @param drillDownItemRowData 下钻table所在行信息
   * @param activeUid 多工具时，当前激活的工具信息
   */
  const openFieldDown = (
    drillDownItem: DrillDownItem,
    drillDownItemRowData: Record<any, string>,
    activeUid?: string,
  ) => {
    const uids = drillDownItem.drill_config.map(config => config.tool.uid).join('&');

    // 如果工具不在已打开列表中，添加它
    if (!allOpenToolsData.value.find(item => item === uids)) {
      allOpenToolsData.value.push(uids);
    }

    nextTick(() => {
      if (dialogRefs.value[uids]) {
        dialogRefs.value[uids].openDialog(uids, drillDownItem, drillDownItemRowData, activeUid);
      }
    });
  };

  /**
   * 打开工具
   * @param uids 工具UID
   */
  const handleOpenTool = async (uids: string) => {
    // 如果工具不在已打开列表中，添加它
    if (!allOpenToolsData.value.find(item => item === uids)) {
      allOpenToolsData.value.push(uids);
    }

    nextTick(() => {
      if (dialogRefs.value[uids]) {
        dialogRefs.value[uids].openDialog(uids);
      }
    });
  };

  /**
   * 设置对话框引用
   * @param uids 工具UID
   * @param ref 对话框引用
   */
  const setDialogRef = (uids: string, ref: any) => {
    dialogRefs.value[uids] = ref;
  };

  return {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
    handleOpenTool,
    setDialogRef,
  };
}
