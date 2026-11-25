import toolTypeApi from '@images/tools-square/tool-type-api.svg';
import toolTypeBkvision from '@images/tools-square/tool-type-bkvision.svg';
import toolTypeSmart from '@images/tools-square/tool-type-smart.svg';
import toolTypeSql from '@images/tools-square/tool-type-sql.svg';

/** 工具类型角标。列表和详情用同一套图，颜色跟图形才对得上。 */
export const getToolTypeMark = (toolType?: string) => {
  if (toolType === 'api') return toolTypeApi;
  if (toolType === 'data_search') return toolTypeSql;
  if (toolType === 'bk_vision') return toolTypeBkvision;
  if (toolType === 'smart_page') return toolTypeSmart;
  return '';
};
