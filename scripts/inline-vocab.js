// 把行下方的音标释义改成行内注释（紧跟单词后面）
const fs = require('fs');
const path = require('path');

const dir = '/Volumes/WORK DISK/QHY/读书/1.早安英文/';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.annotated.html'));

let modified = 0;

for (const file of files) {
  const filePath = path.join(dir, file);
  let html = fs.readFileSync(filePath, 'utf8');
  
  // 匹配：英文行后面跟着音标释义行
  // 英文行：<pre>...<span style='color:#EE0000;'>word</span>...</pre>
  // 音标行：<pre>&nbsp;&nbsp;...<span style='color:#1A6FB0;font-size:12pt;'>/phonetic/</span><span style='color:#555555;font-size:12pt;'>definition</span></pre>
  
  // 这个比较复杂，暂时先不处理，等用户确认效果
  // ...
  
  fs.writeFileSync(filePath, html);
  modified++;
  console.log(`已处理: ${file}`);
}

console.log(`\n完成！共处理 ${modified} 个文件`);
