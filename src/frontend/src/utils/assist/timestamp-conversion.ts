// 添加日期格式化方法
export const formatDate = (dateString: string | number): string => {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).replace(/\//g, '-');
};

// 转换多种日期格式为 "2025-11-20 16:57:32" 格式
export const convertGMTTimeToStandard = (dateInput: string | Date): string => {
  let date: Date;

  // 如果已经是Date对象，直接使用
  if (dateInput instanceof Date) {
    date = dateInput;
  } else {
    // 尝试直接解析为Date对象
    const parsedDate = new Date(dateInput);

    // 如果解析成功且是有效日期，使用解析结果
    if (!isNaN(parsedDate.getTime())) {
      date = parsedDate;
    } else {
      // 如果直接解析失败，尝试处理GMT格式字符串
      const match = dateInput.match(/^(\w{3} \w{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2})/);
      if (!match) {
        throw new Error('Invalid date format');
      }
      date = new Date(match[1]);
    }
  }

  // 格式化为 YYYY-MM-DD HH:mm:ss
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');

  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
};

// 日期格式为 时间戳格式
export const convertToTimestamp = (dateInput: string | Date): number => {
  let date: Date;

  // 如果已经是Date对象，直接使用
  if (dateInput instanceof Date) {
    date = dateInput;
  } else {
    // 尝试直接解析为Date对象
    const parsedDate = new Date(dateInput);

    // 如果解析成功且是有效日期，使用解析结果
    if (!isNaN(parsedDate.getTime())) {
      date = parsedDate;
    } else {
      // 如果直接解析失败，尝试处理GMT格式字符串
      const match = dateInput.match(/^(\w{3} \w{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2})/);
      if (!match) {
        throw new Error('Invalid date format');
      }
      date = new Date(match[1]);
    }
  }

  // 返回时间戳（毫秒级）
  return date.getTime();
};

// 转换为秒级时间戳（Unix timestamp）
export const convertToUnixTimestamp = (dateInput: string | Date): number => {
  const timestampMs = convertToTimestamp(dateInput);
  return Math.floor(timestampMs / 1000);
};
