const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixAnnotatedFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 修改 CSS：把 pre 的 line-height 调小一点
  // 原来的 line-height 是 1.4，改成 1.2
  content = content.replace(/pre\{margin:0;padding:0;font:inherit;white-space:pre;\}/g, 
    'pre{margin:0;padding:0;font:inherit;white-space:pre;line-height:1.2;}');
  
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

console.log('✅ 所有 annotated 文件的 line-height 已调整');
