const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixAnnotatedFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 找到 <body> 之后的内容
  const bodyStart = content.indexOf('<body>');
  const bodyEnd = content.lastIndexOf('</body>');
  
  let bodyContent = content.substring(bodyStart + 6, bodyEnd);
  
  // 把内容按 <pre> 和 </pre> 分割
  // 然后确保每个 <pre> 都有对应的 </pre>
  
  // 简单方法：找到所有 <pre> 的位置，然后确保它们成对出现
  const lines = bodyContent.split('\n');
  
  let inPre = false;
  let newLines = [];
  
  for (let line of lines) {
    const trimmed = line.trim();
    
    if (trimmed.startsWith('<pre>')) {
      inPre = true;
      // 检查这一行有没有 </pre>
      if (trimmed.includes('</pre>')) {
        inPre = false;
      }
      newLines.push(line);
    } else if (trimmed === '</pre>' || trimmed.endsWith('</pre>')) {
      inPre = false;
      newLines.push(line);
    } else if (inPre) {
      // 在 <pre> 块里，直接保留
      newLines.push(line);
    } else {
      // 不在 <pre> 块里，如果这一行有内容，就用 <pre> 包裹
      if (trimmed) {
        newLines.push(`<pre>${line}</pre>`);
      } else {
        newLines.push(line);
      }
    }
  }
  
  const newBody = newLines.join('\n');
  const newContent = content.substring(0, bodyStart + 6) + newBody + content.substring(bodyEnd);
  
  fs.writeFileSync(filePath, newContent, 'utf8');
  console.log(`  修复完成`);
}

// 只修复 10 月 11 日和 10 月 13 日的文件
const filesToFix = [
  '2026/10/2026-10-11_001.annotated.html',
  '2026/10/2026-10-13_001.annotated.html'
];

for (const file of filesToFix) {
  const filePath = path.join(articlesDir, file);
  if (fs.existsSync(filePath)) {
    console.log(`修复: ${file}`);
    fixAnnotatedFile(filePath);
  } else {
    console.log(`文件不存在: ${file}`);
  }
}

console.log('✅ 修复完成');
