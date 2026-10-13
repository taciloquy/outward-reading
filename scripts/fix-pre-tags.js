const fs = require('fs');
const path = require('path');

const articlesDir = path.join(__dirname, '..', 'articles');

function fixAnnotatedFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // 找到所有 <pre> 标签和 </pre> 标签
  const openTags = content.match(/<pre>/g) || [];
  const closeTags = content.match(/<\/pre>/g) || [];
  
  console.log(`  打开标签: ${openTags.length}, 闭合标签: ${closeTags.length}`);
  
  // 如果打开标签比闭合标签多，说明有标签没闭合
  if (openTags.length > closeTags.length) {
    // 简单修复：在每个 <pre> 后面检查，如果下一行不是 </pre>，就在行尾加 </pre>
    // 不对，这样太粗暴了
    
    // 更好的方法：把每一行都用 <pre> 和 </pre> 包裹
    // 但这会改变原来的格式
    
    // 最简单的方法：在文件末尾补上缺失的 </pre>
    const missing = openTags.length - closeTags.length;
    for (let i = 0; i < missing; i++) {
      content += '\n</pre>';
    }
    console.log(`  修复: 补上 ${missing} 个 </pre>`);
  }
  
  fs.writeFileSync(filePath, content, 'utf8');
}

// 遍历所有月份目录
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
