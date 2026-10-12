// 删除 annotated 文件里的空行（<pre>&nbsp;</pre>）
const fs = require('fs');
const path = require('path');

const dir = '/Volumes/WORK DISK/QHY/读书/1.早安英文/';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.annotated.html'));

let modified = 0;

for (const file of files) {
  const filePath = path.join(dir, file);
  let html = fs.readFileSync(filePath, 'utf8');
  
  // 删除 <pre>&nbsp;</pre> 空行
  html = html.replace(/<pre>&nbsp;<\/pre>\n?/g, '');
  
  fs.writeFileSync(filePath, html);
  modified++;
  console.log(`已清理: ${file}`);
}

console.log(`\n完成！共清理 ${modified} 个文件`);
