const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixAnnotatedFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 提取 <style> 之前的头部和 <body> 之后的内容
  const headEnd = content.indexOf('</style>');
  const head = content.substring(0, headEnd + 8);
  const bodyStart = content.indexOf('<body>');
  const bodyEnd = content.lastIndexOf('</body>');
  
  let bodyContent = content.substring(bodyStart + 6, bodyEnd);
  
  // 把 <pre> 和 </pre> 标签都去掉
  bodyContent = bodyContent.replace(/<pre>/g, '');
  bodyContent = bodyContent.replace(/<\/pre>/g, '');
  
  // 按行分割
  const lines = bodyContent.split('\n');
  
  // 重新组合：每一行都用 <pre> 和 </pre> 包裹
  let newBody = '';
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed) {
      newBody += `<pre>${line}</pre>\n`;
    } else {
      // 空行保留
      newBody += '\n';
    }
  }
  
  // 重新组合文件
  const newContent = head + '\n<body>\n' + newBody + '</body>\n</html>';
  
  fs.writeFileSync(filePath, newContent, 'utf8');
  console.log(`  修复完成: ${lines.length} 行`);
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
