const fs = require('fs');
const path = require('path');

const SOURCE_DIR = "/Volumes/WORK DISK/QHY/读书/1.早安英文";
const TARGET_DIR = "/Users/malen/outward-reading-site-prod/articles";

// 找到所有 clean 文件
const cleanFiles = fs.readdirSync(SOURCE_DIR).filter(f => /^\d{4}-\d{2}-\d{2}_\d{3}\.clean\.html$/.test(f));

console.log(`找到 ${cleanFiles.length} 篇文章\n`);

let count = 0;
for (const cleanFile of cleanFiles) {
  const fileKey = cleanFile.replace('.clean.html', '');
  const annotatedFile = cleanFile.replace('.clean.html', '.annotated.html');
  
  // 解析日期
  const [dateStr] = [fileKey.split('_')[0]];
  const [y, m] = dateStr.split('-');
  const targetDir = path.join(TARGET_DIR, y, m);
  
  // 创建目录
  fs.mkdirSync(targetDir, { recursive: true });
  
  // 复制 clean 文件
  const cleanSrc = path.join(SOURCE_DIR, cleanFile);
  const cleanDst = path.join(targetDir, cleanFile);
  if (fs.existsSync(cleanSrc)) {
    fs.copyFileSync(cleanSrc, cleanDst);
    count++;
  }
  
  // 复制 annotated 文件
  const annotatedSrc = path.join(SOURCE_DIR, annotatedFile);
  const annotatedDst = path.join(targetDir, annotatedFile);
  if (fs.existsSync(annotatedSrc)) {
    fs.copyFileSync(annotatedSrc, annotatedDst);
  }
}

console.log(`✅ 已复制 ${count} 篇文章到 articles 目录`);
