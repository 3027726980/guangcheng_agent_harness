// 作者：LHF。
// 时间：2026-10-20。
// 作用：从输入中提取明确的 @工具，忽略邮箱、普通单词与未知工具。
export function mentionedTools(content: string, tools: { name: string }[]): string[] {
  // 作用：从输入提取已注册的工具名称，去重并排除邮箱及不完整提及。
  const known = new Set(tools.map(/* 作用：区分未知用量和有效估算。 */ (tool) => tool.name));
  const names: string[] = [];
  // 要求前后是明确边界，避免把 a@search.com 或 @search查询 误认为工具选择。
  for (const match of content.matchAll(/(?:^|[^a-zA-Z0-9_.@+-])@([a-zA-Z_][\w-]*)(?=$|\s|[，。！？、；：,!?;:])/g)) {
    const name = match[1]!;
    if (known.has(name) && !names.includes(name)) names.push(name);
  }
  return names;
}
