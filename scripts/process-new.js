#!/usr/bin/env node
/**
 * 一键处理新文章脚本
 * 用法: node scripts/process-new.js
 * 
 * 功能：
 * 1. 扫描早安英文目录，找到未处理的 plain + annotated 对
 * 2. 生成正式命名的 clean/annotated HTML 到 articles/YYYY/MM/
 * 3. 提取生词
 * 4. 自动更新 index.html 的 ARTICLES 数组
 * 5. git add / commit / push
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SOURCE_DIR = '/Volumes/WORK DISK/QHY/读书/1.早安英文';
const REPO_DIR = path.resolve(__dirname, '..');
const ARTICLES_DIR = path.join(REPO_DIR, 'articles');
const INDEX_HTML = path.join(REPO_DIR, 'index.html');

// ========== 工具函数 ==========

function dateFromFilename(filename) {
  // 261011_SiliconValleyPodcasts_plain.html -> 2026-10-11
  const m = filename.match(/^(\d{2})(\d{2})(\d{2})_/);
  if (!m) return null;
  const [, yy, mm, dd] = m;
  return `20${yy}-${mm}-${dd}`;
}

function extractPlainText(htmlPath) {
  let html = fs.readFileSync(htmlPath, 'utf8');
  html = html.replace(/<style[\s\S]*?<\/style>/g, '');
  html = html.replace(/<script[\s\S]*?<\/script>/g, '');
  let text = html.replace(/<[^>]+>/g, ' ');
  text = text.replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ');
  text = text.replace(/\s+/g, ' ').trim();
  return text;
}

function extractVocabs(annotatedHtml) {
  const vocabs = [];
  // 找所有蓝色音标 span + 灰色释义 span 的组合（不硬编码 font-size，兼容 8.5pt/12pt 等写法）
  const phoneticRe = /<span style='color:#1A6FB0;[^']*'>([^<]+)<\/span><span style='color:#555555;[^']*'>([^<]*)<\/span>/g;
  // 找红色词（被标注的生词）
  const redWordRe = /<span style='color:#EE0000;'>([^<]+)<\/span>/g;
  
  const redWords = [];
  let m;
  while ((m = redWordRe.exec(annotatedHtml)) !== null) {
    redWords.push(m[1]);
  }
  
  const pairs = [];
  while ((m = phoneticRe.exec(annotatedHtml)) !== null) {
    pairs.push({ phonetic: m[1], definition: m[2].trim() });
  }
  
  // 把红色词和音标对按顺序配对
  for (let i = 0; i < redWords.length && i < pairs.length; i++) {
    vocabs.push({
      word: redWords[i],
      phonetic: pairs[i].phonetic,
      definition: pairs[i].definition
    });
  }
  
  // 如果红色词和音标对数不一致，用音标对里的文本推断
  if (vocabs.length === 0 && pairs.length > 0) {
    for (const p of pairs) {
      vocabs.push({ word: '?', phonetic: p.phonetic, definition: p.definition });
    }
  }
  
  return vocabs;
}

function ensureViewport(html) {
  if (html.includes('viewport')) return html;
  return html.replace('<title>', '<meta charset=utf-8>\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>');
}

// ========== 主流程 ==========

console.log('🔍 扫描早安英文目录...\n');

// 找所有 HTML 文件
const allFiles = fs.readdirSync(SOURCE_DIR).filter(f => f.endsWith('.html'));

// 已处理的 fileKey 列表（如 2026-10-11_001）
const existingArticles = [];
function scanExisting(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) scanExisting(full);
    else if (entry.name.endsWith('.clean.html')) {
      existingArticles.push(entry.name.replace('.clean.html', ''));
    }
  }
}
scanExisting(ARTICLES_DIR);

console.log(`已处理文章: ${existingArticles.length} 篇`);
console.log(`目录中 HTML 文件: ${allFiles.length} 个\n`);

// ========== 补同步：已处理文章新增的 translated.html ==========
let syncedTranslated = 0;
for (const fileKey of existingArticles) {
  const translatedName = `${fileKey}.translated.html`;
  if (!allFiles.includes(translatedName)) continue;
  // 找 clean 文件位置（推断年月目录）
  const [dateStr] = [fileKey.split('_')[0]];
  const [y, m] = dateStr.split('-');
  const targetPath = path.join(ARTICLES_DIR, y, m, translatedName);
  if (fs.existsSync(targetPath)) continue; // 已存在，跳过
  const targetDir = path.dirname(targetPath);
  fs.mkdirSync(targetDir, { recursive: true });
  const translatedHtml = fs.readFileSync(path.join(SOURCE_DIR, translatedName), 'utf8');
  fs.writeFileSync(targetPath, translatedHtml);
  console.log(`🔄 补同步翻译版: articles/${y}/${m}/${translatedName}`);
  syncedTranslated++;
}
if (syncedTranslated > 0) {
  console.log(`✅ 补同步了 ${syncedTranslated} 个翻译版文件\n`);
}

const newArticles = [];

// ========== 新格式：直接是 YYYY-MM-DD_001.clean.html / .annotated.html ==========
const newCleanFiles = allFiles.filter(f => /^\d{4}-\d{2}-\d{2}_\d{3}\.clean\.html$/.test(f));
for (const cleanFile of newCleanFiles) {
  const fileKey = cleanFile.replace('.clean.html', '');
  if (existingArticles.includes(fileKey)) {
    console.log(`⏭  跳过（已处理）: ${cleanFile}`);
    continue;
  }
  const annotatedFile = cleanFile.replace('.clean.html', '.annotated.html');
  if (!allFiles.includes(annotatedFile)) {
    console.log(`⚠️  缺少批注版，跳过: ${cleanFile}`);
    continue;
  }
  
  console.log(`📄 处理新文章（成品格式）: ${fileKey}`);
  const [dateStr] = [fileKey.split('_')[0]];
  const [y, m] = dateStr.split('-');
  const targetDir = path.join(ARTICLES_DIR, y, m);
  fs.mkdirSync(targetDir, { recursive: true });
  
  const cleanHtml = fs.readFileSync(path.join(SOURCE_DIR, cleanFile), 'utf8');
  const annotatedHtml = fs.readFileSync(path.join(SOURCE_DIR, annotatedFile), 'utf8');
  
  fs.writeFileSync(path.join(targetDir, cleanFile), cleanHtml);
  fs.writeFileSync(path.join(targetDir, annotatedFile), annotatedHtml);

  // 同步翻译版文件（如果存在）
  const translatedFile = cleanFile.replace('.clean.html', '.translated.html');
  if (allFiles.includes(translatedFile)) {
    const translatedHtml = fs.readFileSync(path.join(SOURCE_DIR, translatedFile), 'utf8');
    fs.writeFileSync(path.join(targetDir, translatedFile), translatedHtml);
    console.log(`   ✅ 已写入: articles/${y}/${m}/${translatedFile}`);
  }

  const plainText = extractPlainText(path.join(SOURCE_DIR, cleanFile));
  const vocabs = extractVocabs(annotatedHtml);
  const titleMatch = cleanHtml.match(/<h1[^>]*>([\s\S]*?)<\/h1>/) || cleanHtml.match(/<h2[^>]*>([\s\S]*?)<\/h2>/);
  const title = titleMatch ? titleMatch[1].replace(/<[^>]+>/g, '').trim() : fileKey;
  
  console.log(`   ✅ 已写入: articles/${y}/${m}/${cleanFile}`);
  console.log(`   📝 标题: ${title.substring(0, 60)}...`);
  console.log(`   🔤 生词数: ${vocabs.length}\n`);
  
  newArticles.push({
    title, publishDate: dateStr, fileKey,
    source: 'The Economist',
    cleanPath: `/outward-reading/articles/${y}/${m}/${cleanFile}`,
    annotatedPath: `/outward-reading/articles/${y}/${m}/${annotatedFile}`,
    plainText, vocabs
  });
}

// ========== 旧格式：261011_XXX_plain.html + 261011_XXX.html ==========
const plainFiles = allFiles.filter(f => f.includes('_plain'));

for (const plainFile of plainFiles) {
  const dateStr = dateFromFilename(plainFile);
  if (!dateStr) continue;
  
  const fileKey = `${dateStr}_001`;
  if (existingArticles.includes(fileKey)) {
    console.log(`⏭  跳过（已处理）: ${plainFile}`);
    continue;
  }
  
  // 找对应的 annotated 文件
  const baseName = plainFile.replace('_plain.html', '.html');
  const annotatedFile = allFiles.find(f => f === baseName);
  
  if (!annotatedFile) {
    console.log(`⚠️  缺少批注版，跳过: ${plainFile}`);
    continue;
  }
  
  console.log(`📄 处理新文章: ${plainFile}`);
  console.log(`   日期: ${dateStr}`);
  
  const plainPath = path.join(SOURCE_DIR, plainFile);
  const annotatedPath = path.join(SOURCE_DIR, annotatedFile);
  
  // 生成 clean HTML
  let cleanHtml = fs.readFileSync(plainPath, 'utf8');
  cleanHtml = ensureViewport(cleanHtml);
  
  // 生成 annotated HTML
  let annotatedHtml = fs.readFileSync(annotatedPath, 'utf8');
  annotatedHtml = ensureViewport(annotatedHtml);
  
  // 创建目标目录
  const [y, m] = dateStr.split('-');
  const targetDir = path.join(ARTICLES_DIR, y, m);
  fs.mkdirSync(targetDir, { recursive: true });
  
  const cleanName = `${fileKey}.clean.html`;
  const annotatedName = `${fileKey}.annotated.html`;
  
  fs.writeFileSync(path.join(targetDir, cleanName), cleanHtml);
  fs.writeFileSync(path.join(targetDir, annotatedName), annotatedHtml);
  console.log(`   ✅ 已写入: articles/${y}/${m}/${cleanName}`);
  console.log(`   ✅ 已写入: articles/${y}/${m}/${annotatedName}`);

  // 同步翻译版文件（如果存在）
  const translatedName = `${fileKey}.translated.html`;
  if (allFiles.includes(translatedName)) {
    const translatedHtml = fs.readFileSync(path.join(SOURCE_DIR, translatedName), 'utf8');
    fs.writeFileSync(path.join(targetDir, translatedName), translatedHtml);
    console.log(`   ✅ 已写入: articles/${y}/${m}/${translatedName}`);
  }
  
  // 提取正文和生词
  const plainText = extractPlainText(plainPath);
  const vocabs = extractVocabs(annotatedHtml);
  
  // 提取标题（支持 h1/h2/title）
  let title = '';
  const h1Match = cleanHtml.match(/<h1[^>]*>([\s\S]*?)<\/h1>/);
  const h2Match = cleanHtml.match(/<h2[^>]*>([\s\S]*?)<\/h2>/);
  if (h1Match) title = h1Match[1].replace(/<[^>]+>/g, '').trim();
  else if (h2Match) title = h2Match[1].replace(/<[^>]+>/g, '').trim();
  else {
    const t = cleanHtml.match(/<title>([\s\S]*?)<\/title>/);
    if (t) title = t[1].replace(/\s*—\s*\d{4}\/\d{2}\/\d{2}/, '').trim();
  }
  if (!title) title = fileKey;
  
  console.log(`   📝 标题: ${title.substring(0, 60)}...`);
  console.log(`   📖 正文字数: ${plainText.length}`);
  console.log(`   🔤 生词数: ${vocabs.length}`);
  
  newArticles.push({
    title,
    publishDate: dateStr,
    fileKey,
    source: 'The Economist',
    cleanPath: `/outward-reading/articles/${y}/${m}/${cleanName}`,
    annotatedPath: `/outward-reading/articles/${y}/${m}/${annotatedName}`,
    plainText,
    vocabs
  });
  
  console.log('');
}

if (newArticles.length === 0) {
  console.log('✅ 没有新文章需要处理。');
  process.exit(0);
}

// ========== 更新 index.html ==========

console.log(`\n📝 更新 index.html，添加 ${newArticles.length} 篇新文章...`);

let indexHtml = fs.readFileSync(INDEX_HTML, 'utf8');

// 构建新文章的 JS 对象
const newEntries = newArticles.map(art => {
  const vocabsJson = art.vocabs.map(v => `{word:${JSON.stringify(v.word)},phonetic:${JSON.stringify(v.phonetic)},definition:${JSON.stringify(v.definition)}}`).join(',\n          ');
  return `      {
        title: ${JSON.stringify(art.title)},
        publishDate: ${JSON.stringify(art.publishDate)},
        fileKey: ${JSON.stringify(art.fileKey)},
        source: ${JSON.stringify(art.source)},
        cleanPath: ${JSON.stringify(art.cleanPath)},
        annotatedPath: ${JSON.stringify(art.annotatedPath)},
        plainText: ${JSON.stringify(art.plainText)},
        vocabs: [
          ${vocabsJson}
        ]
      }`;
}).join(',\n');

// 在 ARTICLES 数组开头插入新文章
indexHtml = indexHtml.replace(
  /const ARTICLES = \[\n/,
  `const ARTICLES = [\n${newEntries},\n`
);

fs.writeFileSync(INDEX_HTML, indexHtml);
console.log('✅ index.html 已更新');

// ========== Git push ==========

console.log('\n🚀 执行 git push...');
try {
  execSync('git add -A', { cwd: REPO_DIR, stdio: 'inherit' });
  execSync(`git commit -m "新增 ${newArticles.length} 篇文章: ${newArticles.map(a=>a.publishDate).join(', ')}"`, { cwd: REPO_DIR, stdio: 'inherit' });
  execSync('git push', { cwd: REPO_DIR, stdio: 'inherit' });
  console.log('\n✅ 全部完成！网站将在1分钟内自动更新。');
} catch (e) {
  console.log('\n⚠️  git push 失败，请手动执行:');
  console.log('   cd ~/outward-reading && git add -A && git commit -m "新增文章" && git push');
}
