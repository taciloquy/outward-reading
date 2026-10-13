const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixAnnotatedFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 修复1：把多个 &nbsp; 改成一个正常的空格（但保留黄色背景）
  // 找到所有黄色背景的 <span>，把里面的多个 &nbsp; 改成一个空格
  content = content.replace(/(<span style='background:#FFFF00;'>)&nbsp;(<\/span>)/g, '$1 $2');
  
  // 修复2：把连续多个 <span style='background:#FFFF00;'>&nbsp;</span> 改成一个
  content = content.replace(/(<span style='background:#FFFF00;'>&nbsp;<\/span>)+/g, '<span style=\'background:#FFFF00;\'> </span>');
  
  fs.writeFileSync(filePath, content, 'utf8');
  console.log(`  修复完成`);
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
        console.log(`修复: ${file}`);
        fixAnnotatedFile(filePath);
      }
    }
  }
}

console.log('✅ 所有 annotated 文件修复完成');
