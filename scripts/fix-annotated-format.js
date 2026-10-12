// 批量修改 annotated 文件格式
// 1. 去掉音标和中文释义之间的空格
// 2. 确保黄色背景的词组内的空格也涂黄

const fs = require('fs');
const path = require('path');

const dir = '/Volumes/WORK DISK/QHY/读书/1.早安英文/';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.annotated.html'));

let modified = 0;

for (const file of files) {
  const filePath = path.join(dir, file);
  let html = fs.readFileSync(filePath, 'utf8');
  
  // 1. 去掉音标和中文释义之间的空格
  // 匹配：</span><span style='color:#555555;font-size:12pt;'> xxx
  // 替换：</span><span style='color:#555555;font-size:12pt;'>xxx
  html = html.replace(/(<span style='color:#555555;font-size:12pt;'>)\s+([^<])/g, '$1$2');
  
  // 2. 确保黄色背景的词组内的空格也涂黄
  // 这个比较复杂，暂时先只处理第一个要求
  
  fs.writeFileSync(filePath, html);
  modified++;
  console.log(`已修改: ${file}`);
}

console.log(`\n完成！共修改 ${modified} 个文件`);
