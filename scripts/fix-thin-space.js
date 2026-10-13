const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixAnnotatedFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 找到所有黄色背景的 span，把里面的空格改成窄空格
  // 例如：<span style='background:#FFFF00;'>growing pressure</span>
  // 改成：<span style='background:#FFFF00;'>growing&thinsp;pressure</span>
  
  // 先匹配所有黄色背景的 span
  const yellowSpans = content.match(/<span style='background:#FFFF00;'>(.*?)<\/span>/g);
  if (yellowSpans) {
    for (const span of yellowSpans) {
      // 把 span 里面的空格改成窄空格
      const newSpan = span.replace(/ /g, '&thinsp;');
      content = content.replace(span, newSpan);
    }
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

console.log('✅ 所有 annotated 文件的黄色 span 空格已改成窄空格');
