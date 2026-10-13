const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixAnnotatedFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 把多个连续的黄色背景 span 合并成一个
  // 例如：<span style='background:#FFFF00;'>growing</span><span style='background:#FFFF00;'> </span><span style='background:#FFFF00;'>pressure</span>
  // 改成：<span style='background:#FFFF00;'>growing pressure</span>
  
  // 循环替换，直到没有连续的黄色 span
  let prev = '';
  while (prev !== content) {
    prev = content;
    content = content.replace(
      /<span style='background:#FFFF00;'>(.*?)<\/span><span style='background:#FFFF00;'>(.*?)<\/span>/g,
      "<span style='background:#FFFF00;'>$1$2</span>"
    );
  }
  
  fs.writeFileSync(filePath, content, 'utf8');
}

// 修复所有 annotated 文件
const yearDirs = fs.readdirSync(articlesDir);
for (const year of yearDirs) {
  const yearPath = path.join(articlesDir, year);
  if (!fs.statSync(yearPath).isDirectory()) continue;
  
  const monthDirs = fs.readdirSync(yearPath);
  for (const month of monthDirs) {
    const monthPath = path.join(yearPath, month);
    if (!fs.statSync(monthPath).isDirectory()) continue;
    
    const files = fs.readdirSync(monthPath);
    for (const file of files) {
      if (file.endsWith('.annotated.html')) {
        const filePath = path.join(monthPath, file);
        fixAnnotatedFile(filePath);
      }
    }
  }
}

console.log('✅ 所有 annotated 文件的黄色 span 已合并');
