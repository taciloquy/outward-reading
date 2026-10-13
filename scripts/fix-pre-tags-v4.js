const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixAnnotatedFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 去掉所有 <pre> 和 </pre> 标签
  content = content.replace(/<pre>/g, '');
  content = content.replace(/<\/pre>/g, '');
  
  // 按行分割
  const lines = content.split('\n');
  
  let newLines = [];
  let inBody = false;
  
  for (let line of lines) {
    const trimmed = line.trim();
    
    // 找到 <body> 标签开始处理
    if (trimmed === '<body>') {
      inBody = true;
      newLines.push(line);
      continue;
    }
    
    // 找到 </body> 标签结束处理
    if (trimmed === '</body>') {
      inBody = false;
      newLines.push(line);
      continue;
    }
    
    if (!inBody) {
      // 在 <body> 之前，直接保留
      newLines.push(line);
      continue;
    }
    
    // 在 <body> 里面
    if (trimmed === '') {
      // 空行直接保留
      newLines.push(line);
    } else if (trimmed.startsWith('<div') || trimmed.startsWith('</div>') || trimmed.startsWith('<h1') || trimmed.startsWith('</h1>')) {
      // HTML 标签行，直接保留，不用 <pre> 包裹
      newLines.push(line);
    } else {
      // 正文行或注释行，用 <pre> 包裹
      newLines.push(`<pre>${line}</pre>`);
    }
  }
  
  const newContent = newLines.join('\n');
  fs.writeFileSync(filePath, newContent, 'utf8');
  console.log(`  修复完成`);
}

// 修复 10 月 11 日和 10 月 13 日的文件
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
