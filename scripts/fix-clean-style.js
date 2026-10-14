const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixCleanFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 修改 body 行高：1.8 → 1.4
  content = content.replace(/line-height:1\.8;/g, 'line-height:1.4;');
  
  // 修改页边距：20mm 20mm 18mm → 12mm 12mm 14mm
  content = content.replace(/margin:20mm 20mm 18mm/g, 'margin:12mm 12mm 14mm');
  
  fs.writeFileSync(filePath, content, 'utf8');
}

// 修复所有 clean 文件
const yearDirs = fs.readdirSync(articlesDir);
let count = 0;
for (const year of yearDirs) {
  const yearPath = path.join(articlesDir, year);
  if (!fs.statSync(yearPath).isDirectory()) continue;
  
  const monthDirs = fs.readdirSync(yearPath);
  for (const month of monthDirs) {
    const monthPath = path.join(yearPath, month);
    if (!fs.statSync(monthPath).isDirectory()) continue;
    
    const files = fs.readdirSync(monthPath);
    for (const file of files) {
      if (file.endsWith('.clean.html')) {
        const filePath = path.join(monthPath, file);
        fixCleanFile(filePath);
        count++;
      }
    }
  }
}

console.log(`✅ 已修复 ${count} 个原文版文件的样式`);
