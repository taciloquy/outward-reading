// 把黄色背景词组之间的空格也涂黄
const fs = require('fs');
const path = require('path');

const dir = '/Volumes/WORK DISK/QHY/读书/1.早安英文/';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.annotated.html'));

let modified = 0;

for (const file of files) {
  const filePath = path.join(dir, file);
  let html = fs.readFileSync(filePath, 'utf8');
  
  // 找到两个连续的黄色span之间没有&nbsp;的情况，插入&nbsp;
  // 匹配：</span><span style='background:#FFFF00;'>
  // 替换：</span><span style='background:#FFFF00;'>&nbsp;</span><span style='background:#FFFF00;'>
  html = html.replace(/<\/span><span style='background:#FFFF00;'>/g, "</span><span style='background:#FFFF00;'>&nbsp;</span><span style='background:#FFFF00;'>");
  
  fs.writeFileSync(filePath, html);
  modified++;
  console.log(`已处理: ${file}`);
}

console.log(`\n完成！共处理 ${modified} 个文件`);
